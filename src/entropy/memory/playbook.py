"""
Yetenek Oyun Kitabı (Skill Playbook) — damıtılmış yordamsal bellek.

Amaç
----
Bir yetenek kullanıldığında, o yeteneğin birikmiş araştırma raporlarının tamamını
prompt'a taşımak yerine, onlardan bir kez damıtılmış "bu iş nasıl yapılır" yordamını
enjekte etmek.

Neden
-----
Ham depo çok büyük: kasada ~7,8 milyon karakter (~1,95 milyon token) rapor var.
Hiçbir bağlam penceresine sığmaz ve her turda taranması da anlamsız. Buna karşılık
"bir medya ajansı web sitesini nasıl analiz eder" sorusunun cevabı birkaç bin
karakterlik sabit bir yordamdır ve nadiren değişir.

Bu yüzden bilgi iki katmana ayrılır:

  1. PLAYBOOK (yordamsal, küçük, her kullanımda enjekte edilir)
     Yetenek nasıl çalıştırılır: adımlar, sıralama, kontrol listeleri, tuzaklar.
     Raporlardan bir kez damıtılır, yeni rapor biriktikçe tazelenir.

  2. RAPOR ALINTILARI (olgusal, büyük, yalnızca sorguyla ilgili olanlar)
     Somut veriler ve örnekler. Hibrit recall ile sorgu başına 2-3 tanesi seçilir.

Böylece tur başına maliyet, deponun büyüklüğünden bağımsız olarak sabit kalır:
playbook + birkaç alıntı. Depo 100 rapordan 1000 rapora çıktığında prompt büyümez,
yalnızca playbook zenginleşir.

Damıtma AGY CLI üzerinden yapılır; bu modül doğrudan model çağırmaz. Modül,
damıtma prompt'unu üretir ve dönen çıktıyı kalıcılaştırır.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from entropy.core.config import config

logger = logging.getLogger(__name__)

# Karakter/token oranı: Türkçe-İngilizce karışık teknik metinde ~4 karakter ≈ 1 token.
CHARS_PER_TOKEN = 4

# Diskteki playbook'un üst sınırı. Enjekte edilen kısım context_builder'da ayrıca
# token bütçesiyle (bölüm önceliğine göre) kırpılır; bu yüzden dosya, bağlama
# girenden daha uzun olabilir. 6000'de 111 raporluk damıtmanın son üç bölümü
# (karar ölçütleri, tuzaklar, çıktı biçimi) tamamen düşüyordu.
PLAYBOOK_MAX_CHARS = 9000

# Damıtmaya girecek her raporun katkısı. Map aşamasında rapor başına bu kadar
# karakter okunur; tamamı değil, çünkü amaç yordam çıkarmak, içeriği kopyalamak değil.
DISTILL_EXCERPT_CHARS = 2500

# Playbook kaç yeni rapordan sonra bayatlamış sayılır.
STALENESS_REPORT_DELTA = 10


class DegenerateDistillation(ValueError):
    """Model çıktısı mevcut yordamdan belirgin biçimde kötü; kaydedilmedi."""


def estimate_tokens(text: str) -> int:
    """Metnin kabaca kaç token tuttuğunu verir."""
    return max(0, len(text or "")) // CHARS_PER_TOKEN


@dataclass
class SkillPlaybook:
    """Bir yetenek için damıtılmış çalışma yordamı."""

    skill: str
    procedure: str
    source_count: int = 0
    source_digest: str = ""
    updated_at: str = ""
    version: int = 1
    # Kaynak listesinin kaçıncı raporuna kadar okunduğu. Damıtma tek turda en
    # fazla MAX_SOURCES_PER_PASS rapor okur; bu sayaç sonraki turun kaldığı
    # yerden devam etmesini ve playbook'un "kısmi" sayılmasını sağlar.
    processed_count: int = 0
    # İşlenmiş ön ekin (sources[:processed_count]) parmak izi. Kaynak kümesine yeni
    # rapor eklendiğinde tüm küme parmak izi değişir; bu alan sayesinde okunmuş
    # kısım aynıysa baştan başlamak yerine kalınan yerden sürülür.
    processed_digest: str = ""

    def to_markdown(self) -> str:
        return (
            "---\n"
            f'skill: "{self.skill}"\n'
            f"kind: playbook\n"
            f"version: {self.version}\n"
            f"source_count: {self.source_count}\n"
            f"processed_count: {self.processed_count}\n"
            f'source_digest: "{self.source_digest}"\n'
            f'processed_digest: "{self.processed_digest}"\n'
            f"updated_at: {self.updated_at or datetime.datetime.now().isoformat(timespec='seconds')}\n"
            "---\n\n"
            f"# 📘 {self.skill} — Çalışma Yordamı\n\n"
            f"{self.procedure.strip()}\n"
        )

    @classmethod
    def from_markdown(cls, text: str, skill_fallback: str = "") -> Optional["SkillPlaybook"]:
        if not text or not text.strip():
            return None
        fm: Dict[str, str] = {}
        body = text
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
        if m:
            for line in m.group(1).splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    fm[k.strip().lower()] = v.strip().strip('"').strip("'")
            body = m.group(2)

        # Başlık satırını gövdeden düşür; yordam metni istenen kısımdır.
        body = re.sub(r"^#\s+.*\n+", "", body.strip(), count=1)

        def _int(key: str, default: int) -> int:
            try:
                return int(fm.get(key, default))
            except (TypeError, ValueError):
                return default

        return cls(
            skill=fm.get("skill") or skill_fallback,
            procedure=body.strip(),
            source_count=_int("source_count", 0),
            source_digest=fm.get("source_digest", ""),
            updated_at=fm.get("updated_at", ""),
            version=_int("version", 1),
            # Eski dosyalarda alan yok: hepsi okunmuş varsayılır (source_count).
            processed_count=_int("processed_count", _int("source_count", 0)),
            processed_digest=fm.get("processed_digest", ""),
        )


# Kasada rapor sayılmayacak dosyalar. Bunlar günlük/dizin/kimlik dosyalarıdır;
# yordam damıtmak için kaynak değildirler ve indekse girerlerse yeteneklere
# alakasız içerik bağlarlar.
_NON_REPORT_STEMS = {
    "memory", "bellek_haritasi", "bellek haritasi",
    "map of content", "moc", "index", "readme", "home",
    # Damıtılmış yordamın kendisi kaynak değildir: indekse girince kendi
    # damıtmasına giriyor ve her turda değiştiği için "1 okunmamış" kalıyordu.
    "playbook",
}
_NON_REPORT_DIRS = {"dailynotes", "agentdesk", "pendinginbox", "templates", ".obsidian"}
_DAILY_NOTE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def discover_reports(vault_path: Optional[Path] = None) -> List[Path]:
    """
    Kasadaki gerçek araştırma raporlarını bulur.

    Günlük notlar, MEMORY.md, içerik haritaları ve AgentDesk çalışma dosyaları
    elenir: bunlar bilgi kaynağı değil, defter ve dizin dosyalarıdır.
    """
    root = Path(vault_path) if vault_path else Path(config.obsidian_vault_path)
    entropy_dir = root / "Entropy"
    if not entropy_dir.is_dir():
        return []

    out: List[Path] = []
    for p in sorted(entropy_dir.rglob("*.md")):
        parts_low = {part.lower() for part in p.parts}
        if parts_low & _NON_REPORT_DIRS:
            continue
        stem_low = p.stem.strip().lower()
        if stem_low in _NON_REPORT_STEMS or _DAILY_NOTE_RE.match(stem_low):
            continue
        try:
            if p.stat().st_size < 400:  # boş/iskelet dosyalar yordam taşımaz
                continue
        except OSError:
            continue
        out.append(p)
    return out


class SkillReportIndex:
    """
    Rapor → yetenek eşlemesini uygulamanın kendi durum dizininde tutar.

    Neden kasada değil: kasadaki 400'ü aşkın rapor kullanıcının kendi Obsidian
    notları. Her birinin frontmatter'ına `skill:` etiketi yazmak, kullanıcının
    dosyalarını toplu değiştirmek olurdu. İndeks dışarıda tutulduğunda kasa
    olduğu gibi kalır, eşleme her zaman yeniden üretilebilir ve yanlış bir
    sınıflandırma tek bir dosyayı silmekle geri alınır.
    """

    def __init__(self, index_path: Optional[Path] = None):
        from entropy.core.config import STATE_DIR

        self.index_path = Path(index_path) if index_path else (STATE_DIR / "skill_report_index.json")
        self._map: Dict[str, List[str]] = {}
        self._loaded = False

    def load(self) -> Dict[str, List[str]]:
        if self._loaded:
            return self._map
        try:
            if self.index_path.is_file():
                data = json.loads(self.index_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._map = {str(k): [str(p) for p in v] for k, v in data.items() if isinstance(v, list)}
        except (OSError, ValueError) as e:
            logger.warning("Yetenek-rapor indeksi okunamadı (%s): %s", self.index_path, e)
            self._map = {}
        self._loaded = True
        return self._map

    def save(self) -> Path:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(json.dumps(self._map, indent=2, ensure_ascii=False), encoding="utf-8")
        return self.index_path

    def paths_for(self, skill: str) -> List[Path]:
        return [Path(p) for p in self.load().get(skill, []) if Path(p).is_file()]

    def rebuild(self, reports: List[Path], classify) -> Dict[str, int]:
        """
        Raporları verilen sınıflandırıcıyla yeteneklere dağıtır.

        `classify(title, body) -> Optional[str]` biçiminde bir çağrılabilir bekler;
        böylece sınıflandırma mantığı (SkillManager) burada tekrarlanmaz.
        """
        new_map: Dict[str, List[str]] = {}
        for p in reports:
            try:
                raw = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            head = raw[:4000]
            skill = classify(p.stem, head)
            if not skill:
                continue
            new_map.setdefault(skill, []).append(str(p))

        self._map = new_map
        self._loaded = True
        self.save()
        return {k: len(v) for k, v in sorted(new_map.items(), key=lambda kv: -len(kv[1]))}


class PlaybookStore:
    """
    Playbook'ları Obsidian kasasında saklar.

    Konum: <vault>/Entropy/Skills/<yetenek>/PLAYBOOK.md
    Kasada tutulur çünkü kullanıcının okuyup elle düzeltebilmesi gerekir —
    öğrenilen yordam denetlenebilir olmalı, opak bir gömme yığını değil.
    """

    def __init__(self, vault_path: Optional[Path] = None, index: Optional["SkillReportIndex"] = None):
        self.vault_path = Path(vault_path) if vault_path else Path(config.obsidian_vault_path)
        self.skills_dir = self.vault_path / "Entropy" / "Skills"
        self.index = index if index is not None else SkillReportIndex()

    # -- yollar ---------------------------------------------------------

    @staticmethod
    def _safe(name: str) -> str:
        cleaned = "".join(c if c.isalnum() or c in " -_" else "_" for c in (name or "")).strip()
        return cleaned or "skill"

    def skill_dir(self, skill: str) -> Path:
        return self.skills_dir / self._safe(skill)

    def playbook_path(self, skill: str) -> Path:
        return self.skill_dir(skill) / "PLAYBOOK.md"

    def reports_dir(self, skill: str) -> Path:
        return self.skill_dir(skill) / "Reports"

    # -- kaynak raporlar ------------------------------------------------

    def source_reports(self, skill: str) -> List[Path]:
        """
        Yeteneğe ait raporlar.

        Üç kaynaktan toplanır:
          1. Yetenek-kapsamlı klasör (yeni yazılan raporlar buraya gider)
          2. Düz Reports/ içinde `skill:<ad>` etiketi taşıyanlar
          3. Yetenek-rapor indeksi (etiketsiz eski raporlar için)

        Üçüncüsü gerekli, çünkü kasadaki mevcut raporlar yetenek ayrımı
        yapılmadan önce yazılmıştı ve dosyalarına dokunmadan eşlenmeleri gerekiyor.
        """
        found: Dict[Path, None] = {}

        scoped = self.reports_dir(skill)
        if scoped.is_dir():
            for p in sorted(scoped.glob("*.md")):
                found[p] = None

        flat = self.vault_path / "Entropy" / "Reports"
        if flat.is_dir():
            needle = f"skill:{self._safe(skill)}".lower()
            alt = f"skill:{skill}".lower()
            for p in sorted(flat.glob("*.md")):
                if p in found:
                    continue
                try:
                    head = p.read_text(encoding="utf-8", errors="ignore")[:1200].lower()
                except OSError:
                    continue
                if needle in head or alt in head:
                    found[p] = None

        # İndeks süreç genelinde tek dosyadır; başka bir kasaya ait girdiler
        # aktif kasanın sonuçlarına karışmamalı (kasa değiştirildiğinde ya da
        # izole bir kasayla çalışılırken yanlış raporlar bağlama girerdi).
        vault_root = self.vault_path.resolve()
        for p in self.index.paths_for(skill):
            # Eski indeksler PLAYBOOK.md'yi rapor sanmış olabilir; burada da elenir.
            if p.stem.strip().lower() in _NON_REPORT_STEMS:
                continue
            try:
                if vault_root not in p.resolve().parents:
                    continue
            except OSError:
                continue
            found.setdefault(p, None)

        # Aynı ad birden fazla klasörde olabilir (rapor hem yetenek klasörüne hem
        # düz Reports/ altına yazılmış): aynı rapor iki kez damıtılıyor ve işlenmiş
        # kümesinde ad çakışması yaratıyordu (123 kaynak, 105 benzersiz ad). İlk
        # görülen (yetenek-kapsamlı klasör) kalır.
        seen_names: set = set()
        unique: Dict[Path, None] = {}
        for p in found:
            key = p.name.lower()
            if key in seen_names:
                continue
            seen_names.add(key)
            unique[p] = None
        found = unique

        # Zaman sırası: yeni raporlar listenin sonuna eklenir; böylece damıtma
        # sayacı (kaçıncı rapora kadar okundu) yeni rapor gelince anlamını yitirmez.
        def _order(p: Path):
            try:
                return (p.stat().st_mtime_ns, p.name.lower())
            except OSError:
                return (0, p.name.lower())

        return sorted(found, key=_order)

    @staticmethod
    def digest_of(paths: List[Path]) -> str:
        """Kaynak kümesinin parmak izi; playbook'un bayatlayıp bayatlamadığını anlamak için."""
        # İçerik tabanlı: ad + boyut + gövde özeti. Değişiklik zamanı (mtime)
        # kullanılmaz; kasa OneDrive'da ve senkron dosyalara dokununca mtime
        # değişiyordu — playbook 123/123'te "hafif-degisim"e düşüyor, damıtma
        # da işlenmiş ön eki tanımayıp 0'dan başlıyordu.
        h = hashlib.sha256()
        for p in sorted(paths, key=lambda x: x.name.lower()):
            h.update(p.name.encode("utf-8", errors="ignore"))
            try:
                data = p.read_bytes()
            except OSError:
                continue
            h.update(str(len(data)).encode("ascii"))
            h.update(hashlib.sha1(data).digest())
        return h.hexdigest()[:16]

    # -- işlenmiş rapor kümesi (yan dosya) --------------------------------

    def state_path(self, skill: str) -> Path:
        return self.playbook_path(skill).parent / "PLAYBOOK.state.json"

    @staticmethod
    def content_sha(path: Path) -> str:
        """Raporun içerik özeti; ad aynı kalıp gövdesi değişen rapor yeniden okunsun diye."""
        try:
            return hashlib.sha1(path.read_bytes()).hexdigest()[:16]
        except OSError:
            return ""

    def processed_map(self, skill: str) -> Optional[Dict[str, Optional[str]]]:
        """
        Damıtmada okunmuş raporlar: {dosya adı: içerik özeti}; yan dosya yoksa None.

        Sayaç yerine bu küme tutulur: sıra, mtime ya da yeni eklenen bir rapor
        "kaçıncı rapora kadar okundu" bilgisini bozamaz. Özet None ise (eski biçim)
        içerik denetlenmez. "Güncel" kararı da buradan verilir; kasa OneDrive'da
        olduğu için mtime'a dayanan her ölçüt yanlış alarm üretiyordu.
        """
        path = self.state_path(skill)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        raw = data.get("processed", [])
        if isinstance(raw, dict):
            return {str(k): (str(v) if v else None) for k, v in raw.items()}
        return {str(x): None for x in raw}

    def processed_names(self, skill: str) -> Optional[Set[str]]:
        m = self.processed_map(skill)
        return None if m is None else set(m)

    def processed_among(self, skill: str, sources: List[Path]) -> Optional[Set[str]]:
        """Mevcut kaynaklardan okunmuş VE içeriği değişmemiş olanların adları; yan dosya yoksa None."""
        m = self.processed_map(skill)
        if m is None:
            return None
        out: Set[str] = set()
        for p in sources:
            h = m.get(p.name, "__yok__")
            if h == "__yok__":
                continue
            if h is None or h == self.content_sha(p):
                out.add(p.name)
        return out

    def save_processed(self, skill: str, entries: Dict[str, Optional[str]]) -> None:
        path = self.state_path(skill)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"skill": skill, "processed": dict(sorted(entries.items())),
                   "updated_at": datetime.datetime.now().isoformat(timespec="seconds")}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    def save_processed_names(self, skill: str, names: Set[str]) -> None:
        """Geriye uyumluluk: yalnızca adlar (içerik özeti yok)."""
        self.save_processed(skill, {n: None for n in names})

    # -- okuma / yazma --------------------------------------------------

    def load(self, skill: str) -> Optional[SkillPlaybook]:
        path = self.playbook_path(skill)
        if not path.is_file():
            return None
        try:
            return SkillPlaybook.from_markdown(path.read_text(encoding="utf-8", errors="ignore"), skill)
        except OSError as e:
            logger.warning("Playbook okunamadı (%s): %s", path, e)
            return None

    def save(self, playbook: SkillPlaybook) -> Path:
        path = self.playbook_path(playbook.skill)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not playbook.updated_at:
            playbook.updated_at = datetime.datetime.now().isoformat(timespec="seconds")
        path.write_text(playbook.to_markdown(), encoding="utf-8")
        return path

    def status(self, skill: str) -> Dict[str, Any]:
        """Playbook'un mevcut durumu: var mı, kaç kaynaktan, bayat mı."""
        sources = self.source_reports(skill)
        pb = self.load(skill)
        digest = self.digest_of(sources)

        done = self.processed_among(skill, sources) if pb is not None else None
        if pb is None:
            processed = 0
        elif done is not None:
            processed = len(done)
        else:
            processed = min(pb.processed_count, len(sources))
        if pb is None:
            stale_reason = "yok" if sources else "kaynak-yok"
        elif processed < len(sources):
            # Henüz hepsi okunmadı (yeni ya da içeriği değişmiş rapor var):
            # sonraki tur yalnızca onları alır.
            stale_reason = "kismi"
        elif done is not None:
            # Yan dosya varsa karar tamamen ondan: her mevcut rapor okunmuş ve
            # içeriği aynı. Parmak izi yalnızca eski (yan dosyasız) playbook'lar için.
            stale_reason = "guncel"
        elif pb.source_digest != digest:
            delta = abs(len(sources) - pb.source_count)
            stale_reason = "bayat" if delta >= STALENESS_REPORT_DELTA else "hafif-degisim"
        else:
            stale_reason = "guncel"

        return {
            "skill": skill,
            "exists": pb is not None,
            "source_count": len(sources),
            "distilled_from": processed,
            "digest": digest,
            "state": stale_reason,
            "needs_build": pb is None and bool(sources),
            "needs_refresh": pb is not None and stale_reason in ("bayat", "kismi"),
            "path": str(self.playbook_path(skill)),
        }


# ---------------------------------------------------------------------------
# Damıtma (AGY üzerinden)
# ---------------------------------------------------------------------------


def _strip_frontmatter(text: str) -> str:
    m = re.match(r"^---\s*\n.*?\n---\s*\n(.*)$", text, re.DOTALL)
    return (m.group(1) if m else text).strip()


def build_distillation_prompt(
    skill: str,
    sources: List[Path],
    description: str = "",
    existing_procedure: str = "",
) -> str:
    """
    Raporlardan yordam çıkarması için AGY'ye verilecek prompt'u üretir.

    Raporların tamamı değil, her birinden bir alıntı gönderilir. Amaç içeriği
    özetlemek değil — yeniden kullanılabilir bir çalışma yordamı çıkarmaktır.

    existing_procedure verilirse (ikinci ve sonraki turlar) model sıfırdan
    yazmaz; mevcut yordamı yeni raporlarla birleştirip zenginleştirir. Böylece
    111 raporluk bir arşiv 24'lük turlarla, her turda bilgi kaybetmeden işlenir.
    """
    chunks: List[str] = []
    for p in sources:
        try:
            body = _strip_frontmatter(p.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
        if not body:
            continue
        chunks.append(f"### Kaynak: {p.stem}\n{body[:DISTILL_EXCERPT_CHARS]}")

    joined = "\n\n".join(chunks)
    desc_line = f"\nYeteneğin tanımı: {description}\n" if description else ""

    if existing_procedure.strip():
        task_line = (
            f"Aşağıda '{skill}' yeteneğinin MEVCUT çalışma yordamı ve ardından henüz işlenmemiş "
            f"{len(chunks)} yeni araştırma raporundan alıntılar var.\n"
            "Mevcut yordamı yeni raporlarla BİRLEŞTİR ve zenginleştir: doğrulanan adımları koru, "
            "yeni raporların kattığı yöntem, ölçüt ve tuzakları ekle, çelişenleri raporlar lehine düzelt. "
            "Sıfırdan yazma; mevcut bilgiyi kaybetme.\n\n"
            f"### MEVCUT YORDAM\n{existing_procedure.strip()}\n\n### YENİ RAPORLAR\n"
        )
    else:
        task_line = (
            f"Aşağıda '{skill}' yeteneğine ait {len(chunks)} araştırma raporundan alıntılar var.\n"
            "Bunlardan, bu yeteneğin BUNDAN SONRAKİ her işinde izleyeceği kalıcı bir "
            "ÇALIŞMA YORDAMI çıkar.\n\n"
        )

    # Bölüm bütçeleri: model 111 raporda adımları uzatıp son bölümleri düşürüyordu.
    # Uzunluğu bölüm başına sınırlamak, en değerli kısımların (ölçüt, tuzak) her
    # zaman yazılmasını sağlar.
    steps_budget = int(PLAYBOOK_MAX_CHARS * 0.45)
    return (
        f"[GÖREV: YETENEK YORDAMI DAMITMA — {skill}]\n"
        f"{desc_line}\n"
        f"{task_line}"
        "Kurallar:\n"
        "1. Rapor içeriğini ÖZETLEME. Olgu değil, YÖNTEM çıkar: bu iş nasıl yapılır?\n"
        "2. Çıktı uygulanabilir olsun: sıralı adımlar, her adımda neye bakılacağı, "
        "hangi ölçütle karar verileceği.\n"
        "3. Raporlarda tekrar eden yaklaşımları yordama al; tek seferlik ayrıntıları alma.\n"
        "4. Bilinen tuzakları ve sık yapılan hataları ayrı bir başlıkta topla.\n"
        f"5. Toplam {PLAYBOOK_MAX_CHARS} karakteri AŞMA; 'Çalışma Adımları' bölümü tek başına "
        f"{steps_budget} karakteri aşmasın. Beş başlığın HEPSİ mutlaka yazılsın.\n"
        "6. Yalnızca markdown gövdesi üret; frontmatter veya açıklama ekleme.\n"
        "7. BU BİR METİN SENTEZİ GÖREVİDİR: hiçbir araç kullanma, dosya okuma/yazma, "
        "komut çalıştırma, arama ya da alt görev başlatma. Gereken her şey aşağıda; "
        "doğrudan tek bir yanıtta yordamı yaz. Araç kullanımı bu görevi 50 kat "
        "pahalılaştırır ve sonucu bozar.\n\n"
        "İstenen başlıklar (bu sırayla):\n"
        "## Ne Zaman Kullanılır\n"
        "## Çalışma Adımları\n"
        "## Karar Ölçütleri\n"
        "## Bilinen Tuzaklar\n"
        "## Çıktı Biçimi\n\n"
        "---\n\n"
        f"{joined}\n"
    )


def ingest_distilled(
    skill: str,
    agy_output: str,
    sources: List[Path],
    store: PlaybookStore,
    processed_count: Optional[int] = None,
) -> SkillPlaybook:
    """
    AGY'den dönen damıtma çıktısını playbook olarak kalıcılaştırır.

    processed_count: kaynak listesinin kaçıncı raporuna kadar işlendiği; verilmezse
    tüm kaynaklar işlenmiş sayılır (tek turluk küçük yetenekler).
    """
    procedure = (agy_output or "").strip()

    # Model bazen frontmatter veya kod çiti ekliyor; ikisini de temizle.
    procedure = _strip_frontmatter(procedure)
    fence = re.match(r"^```[a-zA-Z]*\s*\n(.*?)\n```\s*$", procedure, re.DOTALL)
    if fence:
        procedure = fence.group(1).strip()

    if len(procedure) > PLAYBOOK_MAX_CHARS:
        # Cümle ortasından kesmek yerine tavanın altındaki son paragraf sınırında
        # kes; kesilen yarım madde ajanı yanıltır, eksik bir bölüm yalnızca eksiktir.
        head = procedure[:PLAYBOOK_MAX_CHARS]
        cut = head.rfind("\n\n")
        if cut < PLAYBOOK_MAX_CHARS * 0.6:
            cut = head.rfind("\n")
        if cut < PLAYBOOK_MAX_CHARS * 0.6:
            cut = len(head)
        procedure = head[:cut].rstrip() + "\n\n_(uzunluk sınırında kesildi)_"

    existing = store.load(skill)

    # Bozuk çıktıya karşı koruma: model bazen yordam yerine kısa bir not, özür ya
    # da yarım bir metin döndürüyor. Bu, zenginleştirme turunda 9 KB'lık iyi bir
    # yordamın 1 KB'lık bir taslakla ezilmesine yol açtı. Mevcut yordam varsa,
    # yeni çıktı en az onun yarısı kadar uzun ve bölümlü olmalı; aksi hâlde
    # mevcut korunur ve çağıran tarafa bilgi verilir.
    if existing and existing.procedure.strip():
        # Başlık sayımı her seviyede (##, ###): model bazen bölümleri ### ile
        # yazıyor; yalnızca ## sayılınca sağlam bir çıktı yanlışlıkla reddedildi.
        new_sections = len(re.findall(r"(?m)^#{2,3} ", procedure))
        old_sections = len(re.findall(r"(?m)^#{2,3} ", existing.procedure))
        too_short = len(procedure) < 0.5 * len(existing.procedure)
        # Yapı kaybı ancak metin de belirgin kısaysa reddedilir; uzun ve az
        # başlıklı bir çıktı biçim farkıdır, bilgi kaybı değil.
        lost_structure = (
            old_sections >= 3
            and new_sections < max(2, old_sections // 2)
            and len(procedure) < 0.8 * len(existing.procedure)
        )
        if too_short or lost_structure:
            raise DegenerateDistillation(
                f"'{skill}' için damıtma çıktısı reddedildi: {len(procedure)} karakter / "
                f"{new_sections} bölüm (mevcut {len(existing.procedure)} karakter / {old_sections} bölüm). "
                "Mevcut yordam korundu."
            )

    pb = SkillPlaybook(
        skill=skill,
        procedure=procedure,
        source_count=len(sources),
        source_digest=store.digest_of(sources),
        updated_at=datetime.datetime.now().isoformat(timespec="seconds"),
        version=(existing.version + 1) if existing else 1,
        processed_count=len(sources) if processed_count is None else min(processed_count, len(sources)),
    )
    pb.processed_digest = store.digest_of(sources[: pb.processed_count])
    store.save(pb)
    return pb
