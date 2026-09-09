"""
Yetenek yordamı damıtma döngüsü.

Bu modül, bir yeteneğin birikmiş raporlarından "bu iş nasıl yapılır" yordamını
AGY CLI üzerinden çıkarır ve playbook olarak kalıcılaştırır. Doğrudan model
çağrısı yapmaz; prompt'u üretir, köprüye verir, dönen çıktıyı kaydeder.

Döngü şudur:

    araştırma yapılır  ->  rapor kasaya yazılır  ->  yeterince rapor birikince
    yordam damıtılır   ->  playbook her yeni işte enjekte edilir  ->  iş daha
    isabetli yapılır   ->  yeni rapor ...

Kritik nokta maliyet: raporların tamamı hiçbir zaman prompt'a girmez. Damıtma
sırasında rapor başına sınırlı bir alıntı okunur ve bu iş yalnızca yeni raporlar
biriktiğinde tekrarlanır. Sonraki tüm turlarda maliyet, playbook'un sabit
boyutundan ibarettir.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from entropy.memory.playbook import (
    CHARS_PER_TOKEN,
    DISTILL_EXCERPT_CHARS,
    PLAYBOOK_MAX_CHARS,
    PROCEDURAL_EXCERPT_CHARS,
    DegenerateDistillation,
    PlaybookStore,
    SkillPlaybook,
    build_distillation_prompt,
    estimate_tokens,
    ingest_distilled,
    select_representatives,
)

logger = logging.getLogger(__name__)

# Tek damıtma turunda okunacak azami rapor. Daha fazlası bir AGY turuna sığmaz;
# fazlası varsa raporlar gruplara bölünüp yordam kademeli olarak zenginleştirilir.
MAX_SOURCES_PER_PASS = 24

# Büyük arşiv modu ("sıkıştırılmış tur"). Rapor başına alıntı ham 2500 karakter
# yerine yordam taşıyan ~900 karaktere indiğinde, bir tura yaklaşık aynı prompt
# boyutuyla (64 × 900 ≈ 57 bin karakter ≈ 24 × 2500) üç kat fazla rapor sığar.
# Maliyet tur sayısı × tur boyutu olduğundan, tur sayısı düşünce her turda
# yeniden gönderilen mevcut yordamın (~2000 token) toplam yükü de düşer.
COMPACT_SOURCES_PER_PASS = 64
COMPACT_EXCERPT_CHARS = PROCEDURAL_EXCERPT_CHARS

# Sıkıştırma bu eşiğin altında açılmaz. Dört klasik tura (4 × 24) sığan bir arşiv
# zaten ucuzdur; orada ham ve daha uzun alıntı, daha yüksek doğruluk demektir.
# Küçük arşivlerde davranış bilerek değişmez.
COMPACT_MIN_SOURCES = 4 * MAX_SOURCES_PER_PASS

# Alıntılar dışında her prompt'ta sabit duran kısım (kurallar, başlık listesi,
# görev tanımı) — tahmine dahil edilmezse tur sayısı arttıkça hata büyür.
PROMPT_OVERHEAD_TOKENS = 400


def pass_shape(total_sources: int) -> Dict[str, Any]:
    """Bu arşiv büyüklüğünde tur başına kaç rapor ve rapor başına kaç karakter."""
    if total_sources >= COMPACT_MIN_SOURCES:
        return {
            "compact": True,
            "per_pass": COMPACT_SOURCES_PER_PASS,
            "excerpt_chars": COMPACT_EXCERPT_CHARS,
        }
    return {
        "compact": False,
        "per_pass": MAX_SOURCES_PER_PASS,
        "excerpt_chars": DISTILL_EXCERPT_CHARS,
    }


def estimate_chain_cost(
    remaining: int,
    per_pass: int,
    excerpt_chars: int,
    procedure_tokens: int,
) -> Dict[str, int]:
    """
    Zincirin tamamının gerçekçi maliyeti: tur sayısı × tur boyutu.

    Önceki tahmin yalnızca SIRADAKİ turun alıntı boyutunu veriyordu; kullanıcı
    513 raporluk bir arşivde 15 bin token görüp 20 tur × ~17 bin token ödüyordu.
    Burada kuyruk birleştirme kuralı da dahil olmak üzere tüm turlar sayılır ve
    her turda yeniden gönderilen mevcut yordam maliyete eklenir.
    """
    passes = 0
    total = 0
    left = max(0, remaining)
    while left > 0:
        end = min(per_pass, left)
        if 0 < left - end <= per_pass // 6:
            end = left
        passes += 1
        # +40: her alıntının "### Kaynak: <ad>" başlığı. Sayılmazsa tahmin 64
        # kaynaklı turlarda ~%6 iyimser çıkıyordu (ölçüldü).
        total += (end * (excerpt_chars + 40)) // CHARS_PER_TOKEN + procedure_tokens + PROMPT_OVERHEAD_TOKENS
        left -= end
    return {"passes": passes, "tokens": total}


# Süreç genelinde paylaşılan durdurma/izleme durumu: zincirlenen turlar farklı
# PlaybookDistiller örneklerinden başlatılabilir; iptal bayrağı ve aktif görev
# kimliği yetenek adına göre burada tutulur ki /distill stop her yerden çalışsın.
_CANCELLED: set = set()
_ACTIVE_TASKS: Dict[str, str] = {}
_RETRIES: Dict[str, int] = {}

# Tazeleme turlarında arşivin neresinde kalındığı. Disk sayacı tazelemede zaten
# toplamda durduğundan (aksi hâlde rozet geri düşerdi) ilerleme buradan izlenir.
# Zincir arşivin sonuna varınca kayıt silinir: bir sonraki tazeleme baştan başlar.
_REFRESH_CURSOR: Dict[str, int] = {}


def refresh_cursor(skill_name: str, total: int) -> int:
    """Tazeleme zincirinin bu yetenekte kaldığı yer (0 ≤ imleç < toplam)."""
    cur = _REFRESH_CURSOR.get(skill_name, 0)
    if cur < 0 or cur >= total:
        return 0
    return cur


def refresh_batch_bounds(cursor: int, total: int, per_pass: int) -> tuple:
    """Tazeleme turunun [başlangıç, bitiş) sınırları; küçük kuyruk bu tura katılır."""
    end = min(cursor + per_pass, total)
    if 0 < total - end <= per_pass // 6:
        end = total
    return cursor, end


# agy'nin damıtma için kullandığı alt ajan. Ajan tanımları çalışma dizinine göre
# keşfedilir (.agents/agents/<ad>/agent.md); arka plan görevi etkin proje dizininde
# koştuğu için dosya orada bulunmalıdır. Yoksa bu şablondan yazılır: hafif model,
# araçsız, tek yanıtlı metin sentezi — plan/keşif döngüsüne girmez.
DISTILL_AGENT_NAME = "distiller"
DISTILL_AGENT_MD = """---
name: distiller
description: Araç kullanmayan metin sentezi alt ajanı; rapor alıntılarından çalışma yordamı damıtır.
subagent: true
mainAgent: true
model: flash
inheritCustomizations: false
---

# Distiller

Sen Entropy AI'ın yordam damıtma ajanısın. Verilen rapor alıntılarından yeniden kullanılabilir bir çalışma yordamı çıkarırsın.

Kurallar: hiçbir araç kullanma (dosya, komut, arama, alt görev, plan dosyası yok); soru sorma, onay isteme; tek yanıtta, istenen başlıklarla, yalnızca markdown gövdesi üret; istekteki karakter sınırlarına uy.
"""


def ensure_distill_agent(project_dir: Optional[Path]) -> Optional[str]:
    """
    Damıtma alt ajanının tanımını proje dizininde hazır eder; ajan adını döndürür.

    Dosya zaten aynı içerikle varsa dokunulmaz. Proje dizini yoksa ya da yazılamıyorsa
    None döner ve damıtma varsayılan ajanla (prompt içi araç yasağıyla) sürer.
    """
    if not project_dir:
        return None
    try:
        target = Path(project_dir) / ".agents" / "agents" / DISTILL_AGENT_NAME / "agent.md"
        if not target.is_file() or target.read_text(encoding="utf-8") != DISTILL_AGENT_MD:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(DISTILL_AGENT_MD, encoding="utf-8")
        return DISTILL_AGENT_NAME
    except OSError as exc:
        logger.warning("Damıtma ajanı yazılamadı (%s); varsayılan ajanla devam: %s", project_dir, exc)
        return None


class PlaybookDistiller:
    """Yetenek playbook'larının kurulmasını ve tazelenmesini yönetir."""

    def __init__(self, store: Optional[PlaybookStore] = None):
        self.store = store or PlaybookStore()

    # -- iptal ------------------------------------------------------------

    @staticmethod
    def cancel(skill_name: str, bridge: Any = None) -> bool:
        """
        Zinciri durdurur: bir sonraki tur başlatılmaz ve süren agy görevi sonlandırılır.

        Zincir otomatik ilerlediği için (468 rapor ≈ 19 tur ≈ 1M token) kullanıcının
        istediği an frenleyebilmesi gerekir. Döndürülen değer: süren bir görev
        gerçekten sonlandırıldı mı.
        """
        _CANCELLED.add(skill_name)
        task_id = _ACTIVE_TASKS.pop(skill_name, None)
        if task_id and bridge is not None and hasattr(bridge, "terminate_background_task"):
            try:
                bridge.terminate_background_task(task_id)
                return True
            except Exception:
                return False
        return False

    @staticmethod
    def advance_refresh(prepared: Dict[str, Any]) -> None:
        """Tazeleme imlecini bu turun sonuna taşır; arşiv bitince kaydı siler."""
        if not prepared or not prepared.get("refresh"):
            return
        skill = prepared.get("skill")
        end = int(prepared.get("refresh_end") or 0)
        total = int(prepared.get("refresh_total") or 0)
        if end >= total:
            _REFRESH_CURSOR.pop(skill, None)
        else:
            _REFRESH_CURSOR[skill] = end

    @staticmethod
    def refresh_remaining(prepared: Dict[str, Any]) -> int:
        """Tazeleme zincirinde bu turdan sonra kalan rapor sayısı."""
        if not prepared or not prepared.get("refresh"):
            return 0
        return max(0, int(prepared.get("refresh_total") or 0) - int(prepared.get("refresh_end") or 0))

    def _skip_batch(self, skill_name: str, prepared: Dict[str, Any]) -> int:
        """Reddedilen grubu işlenmiş sayıp ilerler; mevcut yordam değişmez."""
        self.advance_refresh(prepared)
        pb = self.store.load(skill_name)
        if pb is None:
            return 0
        entries = prepared.get("processed_entries")
        if entries is not None:
            self.store.save_processed(skill_name, dict(entries))
        pb.processed_count = min(prepared.get("processed_after", pb.processed_count), pb.source_count)
        self.store.save(pb)
        return pb.processed_count

    @staticmethod
    def is_cancelled(skill_name: str) -> bool:
        return skill_name in _CANCELLED

    @staticmethod
    def active_skills() -> List[str]:
        return sorted(_ACTIVE_TASKS)

    # -- planlama -------------------------------------------------------

    def plan(self, skill_name: str) -> Dict[str, Any]:
        """
        Bu yetenek için damıtmanın gerekip gerekmediğini ve maliyetini bildirir.

        Kullanıcıya iş başlamadan önce ne kadar okunacağını göstermek için ayrı
        tutulur; damıtma pahalı olan tek adımdır.
        """
        status = self.store.status(skill_name)
        sources = self.store.source_reports(skill_name)
        done = self._processed(skill_name, sources)
        start = len(done)
        unprocessed = [p for p in sources if p.name not in done]

        shape = pass_shape(len(sources))
        per_pass = shape["per_pass"]
        excerpt_chars = shape["excerpt_chars"]

        duplicates = 0
        if shape["compact"] and unprocessed:
            reps, followers = select_representatives(unprocessed)
            duplicates = sum(len(v) for v in followers.values())
            unprocessed = reps

        pb = self.store.load(skill_name)
        # Tazeleme: işlenmemiş kaynak yok ama kullanıcı yine de damıtmak isterse
        # tüm arşiv zincirlenerek yeniden okunur. Maliyet tahmini bunu saymazsa
        # 104 raporluk bir tazeleme "0 token" görünüyordu.
        refresh = bool(sources) and not unprocessed
        if refresh:
            cursor = refresh_cursor(skill_name, len(sources))
            r_start, r_end = refresh_batch_bounds(cursor, len(sources), per_pass)
            batch = sources[r_start:r_end]
            remaining = len(sources) - cursor
        else:
            r_start = r_end = 0
            end = min(per_pass, len(unprocessed))
            if 0 < len(unprocessed) - end <= per_pass // 6:
                end = len(unprocessed)
            batch = unprocessed[:end]
            remaining = len(unprocessed)

        # Her tur mevcut yordamı da taşır; henüz yordam yoksa zincirin ilerleyen
        # turlarında oluşacağı varsayılır (tavanın yarısı, gerçekçi bir orta değer).
        procedure_tokens = estimate_tokens(pb.procedure) if pb else (PLAYBOOK_MAX_CHARS // (2 * CHARS_PER_TOKEN))
        cost = estimate_chain_cost(remaining, per_pass, excerpt_chars, procedure_tokens)

        return {
            "refresh": refresh,
            "refresh_start": r_start,
            "refresh_end": r_end,
            "refresh_total": len(sources) if refresh else 0,
            **status,
            "sources_total": len(sources),
            # Okunmamış rapor sayısı: arayüzdeki "Damıt (yeni N)" etiketi ve
            # "tazeleme mi, artımlı mı" kararı buradan okunur.
            "unread": len(sources) - start if not refresh else 0,
            "sources_this_pass": len(batch),
            "batch_start": start,
            "estimated_prompt_tokens": estimate_tokens("x" * (len(batch) * excerpt_chars)),
            # Zincirin tamamı: kullanıcı başlamadan önce toplam faturayı görsün.
            "compact": shape["compact"],
            "excerpt_chars": excerpt_chars,
            "sources_per_pass": per_pass,
            "duplicates_skipped": duplicates,
            "effective_sources": len(unprocessed),
            "estimated_total_passes": cost["passes"],
            "estimated_total_tokens": cost["tokens"],
            "should_run": status["needs_build"] or status["needs_refresh"],
        }

    def _processed(self, skill_name: str, sources: List[Path]) -> Set[str]:
        """
        Mevcut kaynaklar içinde okunmuş olanların adları.

        Yan dosya yoksa (eski playbook) tek seferlik geçiş: playbook'un sayacı
        kadar rapor, mevcut sırayla okunmuş sayılır ve yan dosya yazılır. Sonrası
        sıradan/mtime'dan bağımsızdır: yeni rapor gelirse yalnızca o okunur, bir
        rapor silinirse sayaç bir düşer; hiçbir durumda 0'a dönülmez.
        """
        done = self.store.processed_among(skill_name, sources)
        if done is None:
            pb = self.store.load(skill_name)
            if pb is None:
                return set()
            head = sources[: min(pb.processed_count, len(sources))]
            self.store.save_processed(skill_name, {p.name: self.store.content_sha(p) for p in head})
            done = {p.name for p in head}
        return done

    def _batch_start(self, skill_name: str, sources: List[Path]) -> int:
        """Okunmuş rapor sayısı (plan/ilerleme gösterimi için)."""
        return len(self._processed(skill_name, sources))

    # -- damıtma --------------------------------------------------------

    def unread_count(self, skill_name: str) -> int:
        """Bu yetenekte henüz damıtılmamış (yeni ya da içeriği değişmiş) rapor sayısı."""
        sources = self.store.source_reports(skill_name)
        if not sources:
            return 0
        done = self._processed(skill_name, sources)
        return sum(1 for p in sources if p.name not in done)

    def prepare(
        self,
        skill_name: str,
        description: str = "",
        allow_refresh: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        Damıtma prompt'unu hazırlar.

        None dönerse damıtacak kaynak yoktur. Dönen sözlükteki `prompt` AGY'ye
        gönderilir, çıktısı `complete()`'e verilir.

        allow_refresh=False: yalnızca OKUNMAMIŞ raporlar işlenir; hepsi okunmuşsa
        None döner. "Damıt" düğmesi bunu kullanır — kullanıcı yeni raporları
        işletmek isterken sessizce tüm arşivin yeniden okunmasına (513 rapor,
        ~20 tur) razı olmuş sayılmamalı. Tazeleme ayrı ve açık bir eylemdir.
        """
        sources = self.store.source_reports(skill_name)
        if not sources:
            logger.info("'%s' için kaynak rapor yok; damıtma atlandı.", skill_name)
            return None

        done = self._processed(skill_name, sources)
        start = len(done)
        unprocessed = [p for p in sources if p.name not in done]
        if not unprocessed and not allow_refresh:
            logger.info("'%s' için okunmamış rapor yok; tazeleme istenmedi.", skill_name)
            return None
        existing = self.store.load(skill_name)

        shape = pass_shape(len(sources))
        compact = shape["compact"]
        per_pass = shape["per_pass"]

        # Yakın-kopya eleme: aynı işin tekrarlanan koşumları arşive neredeyse
        # aynı raporu birden çok kez yazıyor. Temsilci okunur, bağlı olanlar
        # okunmadan işlenmiş sayılır — yoksa zincir hiç bitmez.
        followers: Dict[str, List[str]] = {}
        if compact and unprocessed:
            unprocessed, followers = select_representatives(unprocessed)

        # Tüm kaynaklar işlenmişse açık bir istek "tazeleme" turudur: ilk grup,
        # mevcut yordamla birlikte yeniden verilir ve model onu iyileştirir.
        # Reddetmek yerine bunu yapmak, kullanıcının 📘 / "/distill x" ile bilinçli
        # olarak yeniden damıtma isteyebilmesini sağlar; otomatik listede
        # (pending) böyle bir yetenek zaten görünmez.
        # Tazeleme tek turdur ve sayacı sıfırlamaz: en yeni raporlar mevcut yordamla
        # birlikte verilir, işlenen sayısı toplamda kalır. (Önceden sayaç 0'a dönüp
        # tüm arşiv beş turda yeniden okunuyordu — hem kafa karıştırıcı hem pahalı.)
        refresh = not unprocessed
        r_start = r_end = 0
        if refresh:
            # Tazeleme artık tek tur değil: arşivin tamamı imleç ilerledikçe
            # turlara bölünür ("tazeleme 64/104 → 104/104"). Tek tur olduğunda
            # kullanıcı 104 raporun 64'ünde "tamamlandı" görüyordu.
            cursor = refresh_cursor(skill_name, len(sources))
            r_start, r_end = refresh_batch_bounds(cursor, len(sources), per_pass)
            batch = sources[r_start:r_end]
            start = r_start
        else:
            # Yeni rapor geldiğinde sıradan tur çalışır; yarım kalmış tazeleme
            # imleci burada temizlenir ki sonraki tazeleme baştan başlasın.
            _REFRESH_CURSOR.pop(skill_name, None)
            end = per_pass
            # Küçük bir kuyruk (ör. 123 raporda son 3) tek başına tur olunca model
            # yalnızca o birkaç raporun özetini döndürüyor, çıktı mevcut yordamdan
            # kısa kalıp reddediliyordu. Kuyruk küçükse bu tura katılır.
            if 0 < len(unprocessed) - end <= per_pass // 6:
                end = len(unprocessed)
            batch = unprocessed[:end]

        # Bu turda okunan temsilcilere bağlı kopyalar da işlenmiş sayılır.
        covered = {p.name for p in batch}
        for p in batch:
            covered.update(followers.get(p.name, ()))

        existing_text = existing.procedure if (existing and (start > 0 or refresh)) else ""
        prompt = build_distillation_prompt(
            skill_name,
            batch,
            description=description,
            existing_procedure=existing_text,
            excerpt_chars=shape["excerpt_chars"],
            procedural=compact,
        )
        if refresh:
            processed_names = {p.name for p in sources}
            processed_paths = sources
        else:
            processed_names = done | covered
            processed_paths = [q for q in sources if q.name in processed_names]
        return {
            "skill": skill_name,
            "prompt": prompt,
            "sources": batch,
            "all_sources": sources,
            "batch_start": start,
            "processed_after": len(sources) if refresh else min(len(sources), start + len(covered)),
            "processed_names": processed_names,
            "processed_entries": {p.name: self.store.content_sha(p) for p in processed_paths},
            "refresh": refresh,
            "refresh_start": r_start,
            "refresh_end": r_end,
            "refresh_total": len(sources) if refresh else 0,
            "compact": compact,
            "excerpt_chars": shape["excerpt_chars"],
            "duplicates_skipped": sum(len(followers.get(p.name, ())) for p in batch),
            "prompt_tokens": estimate_tokens(prompt),
        }

    def complete(self, prepared: Dict[str, Any], agy_output: str) -> Optional[SkillPlaybook]:
        """AGY çıktısını playbook'a dönüştürüp kaydeder."""
        if not prepared or not (agy_output or "").strip():
            return None
        # Parmak izi tüm kaynak kümesi üzerinden alınır; yalnızca bu turda
        # okunanlar üzerinden alınsaydı, kalan raporlar geldiğinde playbook
        # bayat sayılmaz ve hiç tazelenmezdi.
        pb = ingest_distilled(
            prepared["skill"],
            agy_output,
            prepared.get("all_sources") or prepared["sources"],
            self.store,
            processed_count=prepared.get("processed_after"),
        )
        entries = prepared.get("processed_entries")
        if pb is not None and entries is not None:
            self.store.save_processed(prepared["skill"], dict(entries))
        if pb is not None:
            self.advance_refresh(prepared)
        return pb

    # -- köprü ile uçtan uca --------------------------------------------

    def run_with_bridge(
        self,
        skill_name: str,
        send_prompt: Callable[[str], str],
        description: str = "",
    ) -> Optional[SkillPlaybook]:
        """
        Damıtmayı verilen gönderici üzerinden uçtan uca çalıştırır.

        `send_prompt(prompt) -> str` biçiminde eşzamanlı bir çağrılabilir bekler;
        böylece bu modül AgyProcessBridge'e (ve Qt'ye) bağımlı olmaz ve test
        edilebilir kalır.
        """
        prepared = self.prepare(skill_name, description=description)
        if not prepared:
            return None
        try:
            output = send_prompt(prepared["prompt"])
        except Exception as e:
            logger.warning("'%s' damıtması başarısız: %s", skill_name, e)
            return None
        return self.complete(prepared, output)

    # -- uygulama köprüsü (arka plan görevi) ----------------------------

    def run_via_bridge(
        self,
        bridge: Any,
        skill_name: str,
        description: str = "",
        auto_continue: bool = True,
        agent: Optional[str] = None,
        allow_refresh: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        Damıtmayı AgyProcessBridge'in arka plan görev yolu üzerinden başlatır.

        Bloklamaz: görev ledger'a kaydolur, sohbet kilitlenmez, sonuç geldiğinde
        playbook yazılır ve bus.playbook_updated yayınlanır. Damıtma çıktısı bir
        araştırma raporu değil ara üründür; bu yüzden save_report=False ile kasaya
        rapor olarak yazılmaz (aksi hâlde her damıtma rapor arşivini kirletir ve
        bir sonraki damıtmaya kaynak olarak geri dönerdi).

        auto_continue: bir tur bittiğinde işlenmemiş rapor kaldıysa sıradaki turu
        kendiliğinden başlatır; kullanıcı 111 raporluk bir arşiv için beş kez
        komut vermek zorunda kalmaz. Her turdan sonra bus.distill_progress
        (yetenek, işlenen, toplam) yayınlanır.
        agent: agy --agent adı (araç kullanımı kısıtlı alt ajan); None ise varsayılan.

        Döndürülen sözlük başlatılan işin özetidir; None ise kaynak yoktur.
        """
        from entropy.core.event_bus import bus

        if agent is None:
            agent = ensure_distill_agent(getattr(bridge, "active_project_dir", None))

        # Yeni bir başlatma önceki iptali sıfırlar; iptal yalnızca süren zinciri keser.
        _CANCELLED.discard(skill_name)

        # Aynı yetenek için ikinci bir zincir, aynı grubu iki kez damıtır ve iki
        # sonuç birbirinin üstüne yazar; süren bir zincir varsa yenisi açılmaz.
        running = _ACTIVE_TASKS.get(skill_name)
        if running:
            return {"already_running": True, "skill": skill_name, "task_id": running}

        prepared = self.prepare(skill_name, description=description, allow_refresh=allow_refresh)
        if not prepared:
            return None

        total = len(prepared["all_sources"])
        refresh = bool(prepared.get("refresh"))
        bus.distill_progress.emit(skill_name, total if refresh else prepared["batch_start"], total)

        task_id = f"distill-{skill_name}-{int(__import__('time').time())}"
        if refresh:
            # Etiket kümülatif: "tazeleme 64/104" → "tazeleme 104/104".
            task_name = f"Yordam Damıtma: {skill_name} [tazeleme {prepared['refresh_end']}/{total}]"
        else:
            task_name = f"Yordam Damıtma: {skill_name} [{prepared['batch_start']}→{prepared['processed_after']}/{total}]"

        def _on_result(full_text: str, success: bool):
            # Köprü bunu işçi iş parçacığından çağırır. Playbook yazımı, sinyaller ve
            # sıradaki turun başlatılması ana iş parçacığında yapılır.
            bus.invoke_on_main(lambda: _on_result_main(full_text, success))

        def _on_result_main(full_text: str, success: bool):
            _ACTIVE_TASKS.pop(skill_name, None)
            if skill_name in _CANCELLED:
                bus.terminal_output_received.emit(f"[Damıtma] '{skill_name}' durduruldu; bu tur kaydedilmedi.\n")
                return
            if not success or not (full_text or "").strip():
                bus.terminal_output_received.emit(
                    f"[Damıtma] '{skill_name}' için çıktı alınamadı; playbook değiştirilmedi.\n"
                )
                return
            try:
                pb = self.complete(prepared, full_text)
            except DegenerateDistillation as e:
                bus.terminal_output_received.emit(f"[Damıtma] {e}\n")
                # Reddedilen bir tur zinciri öldürmemeli: aynı grup bir kez daha
                # denenir; ikinci ret de gelirse grup atlanır ve zincir sürer.
                retries = _RETRIES.get(skill_name, 0)
                if auto_continue and retries < 1:
                    _RETRIES[skill_name] = retries + 1
                    bus.terminal_output_received.emit(f"[Damıtma] '{skill_name}' aynı grup yeniden deneniyor.\n")
                    self.run_via_bridge(bridge, skill_name, description=description, auto_continue=True, agent=agent, allow_refresh=allow_refresh)
                elif auto_continue:
                    _RETRIES.pop(skill_name, None)
                    skipped = self._skip_batch(skill_name, prepared)
                    total_n = len(prepared["all_sources"])
                    # Sayaç diskte ilerledi; kart ve rozet de görsün (aksi hâlde son grup
                    # atlandığında sayaç turuncu kalıyordu).
                    bus.playbook_updated.emit(skill_name)
                    bus.distill_progress.emit(skill_name, skipped, total_n)
                    # Tazelemede disk sayacı zaten toplamdadır; zincirin sürüp
                    # sürmeyeceğine tazeleme imleci karar verir.
                    if self.refresh_remaining(prepared) > 0 and skill_name not in _CANCELLED:
                        bus.terminal_output_received.emit(
                            f"[Damıtma] '{skill_name}' tazeleme grubu atlandı "
                            f"({prepared['refresh_end']}/{total_n}); zincir sürüyor.\n"
                        )
                        self.run_via_bridge(bridge, skill_name, description=description, auto_continue=True, agent=agent, allow_refresh=allow_refresh)
                    elif skipped < total_n and skill_name not in _CANCELLED:
                        bus.terminal_output_received.emit(
                            f"[Damıtma] '{skill_name}' grup atlandı ({skipped}/{total_n}); zincir sürüyor.\n"
                        )
                        self.run_via_bridge(bridge, skill_name, description=description, auto_continue=True, agent=agent, allow_refresh=allow_refresh)
                    else:
                        # Önceden burada koşulsuz yeniden çağrılıyordu: son grup atlanınca
                        # prepare() "tazeleme" üretip 0→24'ten yeni bir zincir açıyordu.
                        bus.terminal_output_received.emit(
                            f"[Damıtma] '{skill_name}' tamamlandı ({skipped}/{total_n}); son grup yordamı değiştirmedi.\n"
                        )
                return
            _RETRIES.pop(skill_name, None)
            if pb is None:
                return
            bus.terminal_output_received.emit(
                f"[Damıtma] '{skill_name}' yordamı v{pb.version} kaydedildi "
                f"({pb.processed_count}/{pb.source_count} rapor, ~{estimate_tokens(pb.procedure)} token).\n"
            )
            bus.playbook_updated.emit(skill_name)
            bus.distill_progress.emit(skill_name, pb.processed_count, pb.source_count)

            refresh_left = self.refresh_remaining(prepared)
            if refresh:
                r_end = prepared["refresh_end"]
                r_total = prepared["refresh_total"]
                if refresh_left > 0:
                    bus.terminal_output_received.emit(
                        f"[Damıtma] '{skill_name}' tazeleme {r_end}/{r_total}; sıradaki tur başlatılıyor. "
                        f"Durdurmak için: /distill stop {skill_name}\n"
                    )
                else:
                    bus.terminal_output_received.emit(
                        f"[Damıtma] '{skill_name}' tazeleme tamamlandı ({r_total}/{r_total}).\n"
                    )

            if auto_continue and skill_name not in _CANCELLED and (
                refresh_left > 0 or pb.processed_count < pb.source_count
            ):
                if not refresh:
                    bus.terminal_output_received.emit(
                        f"[Damıtma] '{skill_name}' sıradaki tur başlatılıyor "
                        f"({pb.processed_count}/{pb.source_count}). Durdurmak için: /distill stop {skill_name}\n"
                    )
                self.run_via_bridge(bridge, skill_name, description=description, auto_continue=True, agent=agent, allow_refresh=allow_refresh)

        _ACTIVE_TASKS[skill_name] = task_id

        bridge.send_background_task_async(
            task_id=task_id,
            task_name=task_name,
            prompt=prepared["prompt"],
            # "plan" modu agy'de planlama davranışı tetikliyor: model yordamı yazmak
            # yerine keşif yapıp bir plan dosyası üretiyor ve onay istiyor (200+ adım,
            # ~900k token, çıktı olarak 1 KB'lık bir not). Sohbetle aynı mod kullanılır;
            # araç yasağı prompt'ta açıkça yazılıdır.
            mode="accept-edits",
            on_result=_on_result,
            save_report=False,
            agent=agent,
        )
        return {
            "task_id": task_id,
            "skill": skill_name,
            "sources": len(prepared["sources"]),
            "sources_total": total,
            "batch_start": prepared["batch_start"],
            "prompt_tokens": prepared["prompt_tokens"],
            "auto_continue": auto_continue,
            "refresh": refresh,
            "refresh_end": prepared["refresh_end"],
            "refresh_total": prepared["refresh_total"],
        }

    # -- toplu ----------------------------------------------------------

    def pending(self, skill_names: List[str]) -> List[Dict[str, Any]]:
        """Damıtılması gereken yetenekleri, kaynak sayısına göre sıralı verir."""
        plans = [self.plan(name) for name in skill_names]
        return sorted(
            (p for p in plans if p["should_run"]),
            key=lambda p: p["sources_total"],
            reverse=True,
        )
