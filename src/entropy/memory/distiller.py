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
    DISTILL_EXCERPT_CHARS,
    DegenerateDistillation,
    PlaybookStore,
    SkillPlaybook,
    build_distillation_prompt,
    estimate_tokens,
    ingest_distilled,
)

logger = logging.getLogger(__name__)

# Tek damıtma turunda okunacak azami rapor. Daha fazlası bir AGY turuna sığmaz;
# fazlası varsa raporlar gruplara bölünüp yordam kademeli olarak zenginleştirilir.
MAX_SOURCES_PER_PASS = 24


# Süreç genelinde paylaşılan durdurma/izleme durumu: zincirlenen turlar farklı
# PlaybookDistiller örneklerinden başlatılabilir; iptal bayrağı ve aktif görev
# kimliği yetenek adına göre burada tutulur ki /distill stop her yerden çalışsın.
_CANCELLED: set = set()
_ACTIVE_TASKS: Dict[str, str] = {}
_RETRIES: Dict[str, int] = {}


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

    def _skip_batch(self, skill_name: str, prepared: Dict[str, Any]) -> int:
        """Reddedilen grubu işlenmiş sayıp ilerler; mevcut yordam değişmez."""
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
        batch = [p for p in sources if p.name not in done][:MAX_SOURCES_PER_PASS]

        return {
            **status,
            "sources_total": len(sources),
            "sources_this_pass": len(batch),
            "batch_start": start,
            "estimated_prompt_tokens": estimate_tokens("x" * (len(batch) * DISTILL_EXCERPT_CHARS)),
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

    def prepare(self, skill_name: str, description: str = "") -> Optional[Dict[str, Any]]:
        """
        Damıtma prompt'unu hazırlar.

        None dönerse damıtacak kaynak yoktur. Dönen sözlükteki `prompt` AGY'ye
        gönderilir, çıktısı `complete()`'e verilir.
        """
        sources = self.store.source_reports(skill_name)
        if not sources:
            logger.info("'%s' için kaynak rapor yok; damıtma atlandı.", skill_name)
            return None

        done = self._processed(skill_name, sources)
        start = len(done)
        unprocessed = [p for p in sources if p.name not in done]
        existing = self.store.load(skill_name)

        # Tüm kaynaklar işlenmişse açık bir istek "tazeleme" turudur: ilk grup,
        # mevcut yordamla birlikte yeniden verilir ve model onu iyileştirir.
        # Reddetmek yerine bunu yapmak, kullanıcının 📘 / "/distill x" ile bilinçli
        # olarak yeniden damıtma isteyebilmesini sağlar; otomatik listede
        # (pending) böyle bir yetenek zaten görünmez.
        # Tazeleme tek turdur ve sayacı sıfırlamaz: en yeni raporlar mevcut yordamla
        # birlikte verilir, işlenen sayısı toplamda kalır. (Önceden sayaç 0'a dönüp
        # tüm arşiv beş turda yeniden okunuyordu — hem kafa karıştırıcı hem pahalı.)
        refresh = not unprocessed
        if refresh:
            batch = sources[-MAX_SOURCES_PER_PASS:]
            start = len(sources) - len(batch)
        else:
            end = MAX_SOURCES_PER_PASS
            # Küçük bir kuyruk (ör. 123 raporda son 3) tek başına tur olunca model
            # yalnızca o birkaç raporun özetini döndürüyor, çıktı mevcut yordamdan
            # kısa kalıp reddediliyordu. Kuyruk küçükse bu tura katılır.
            if 0 < len(unprocessed) - end <= MAX_SOURCES_PER_PASS // 6:
                end = len(unprocessed)
            batch = unprocessed[:end]

        existing_text = existing.procedure if (existing and (start > 0 or refresh)) else ""
        prompt = build_distillation_prompt(
            skill_name, batch, description=description, existing_procedure=existing_text
        )
        return {
            "skill": skill_name,
            "prompt": prompt,
            "sources": batch,
            "all_sources": sources,
            "batch_start": start,
            "processed_after": len(sources) if refresh else start + len(batch),
            "processed_names": (set(p.name for p in sources) if refresh else (done | {p.name for p in batch})),
            "processed_entries": {p.name: self.store.content_sha(p) for p in (sources if refresh else [q for q in sources if q.name in done] + batch)},
            "refresh": refresh,
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

        prepared = self.prepare(skill_name, description=description)
        if not prepared:
            return None

        total = len(prepared["all_sources"])
        refresh = bool(prepared.get("refresh"))
        bus.distill_progress.emit(skill_name, total if refresh else prepared["batch_start"], total)

        task_id = f"distill-{skill_name}-{int(__import__('time').time())}"
        if refresh:
            task_name = f"Yordam Damıtma: {skill_name} [tazeleme {len(prepared['sources'])}/{total}]"
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
                    self.run_via_bridge(bridge, skill_name, description=description, auto_continue=True, agent=agent)
                elif auto_continue:
                    _RETRIES.pop(skill_name, None)
                    skipped = self._skip_batch(skill_name, prepared)
                    total_n = len(prepared["all_sources"])
                    # Sayaç diskte ilerledi; kart ve rozet de görsün (aksi hâlde son grup
                    # atlandığında sayaç turuncu kalıyordu).
                    bus.playbook_updated.emit(skill_name)
                    bus.distill_progress.emit(skill_name, skipped, total_n)
                    if skipped < total_n and skill_name not in _CANCELLED:
                        bus.terminal_output_received.emit(
                            f"[Damıtma] '{skill_name}' grup atlandı ({skipped}/{total_n}); zincir sürüyor.\n"
                        )
                        self.run_via_bridge(bridge, skill_name, description=description, auto_continue=True, agent=agent)
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

            if auto_continue and pb.processed_count < pb.source_count and skill_name not in _CANCELLED:
                bus.terminal_output_received.emit(
                    f"[Damıtma] '{skill_name}' sıradaki tur başlatılıyor "
                    f"({pb.processed_count}/{pb.source_count}). Durdurmak için: /distill stop {skill_name}\n"
                )
                self.run_via_bridge(bridge, skill_name, description=description, auto_continue=True, agent=agent)

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
