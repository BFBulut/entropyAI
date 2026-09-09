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

import contextlib
import datetime
import hashlib
import json
import logging
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from entropy.core.config import config

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Rapor dosyası içerik önbelleği
# --------------------------------------------------------------------------
# PlaybookStore.status() her yenilemede aynı raporları üç kez okuyordu: bir kez
# `skill:` etiketi için baş kısmını, bir kez parmak izi için, bir kez de işlenmiş
# kümesinin içerik özeti için (104 kaynak x 3 = ~300 dosya okuması, ~98-150 ms).
# İçerik değişmediyse okumanın anlamı yok; anahtar (yol, boyut, mtime) olduğundan
# OneDrive mtime'a dokunsa bile sonuç değişmez: yalnızca önbellek ıskalar ve
# dosya yeniden okunur. Karar ölçütleri (parmak izi, içerik özeti) eskisi gibi
# içerikten üretilir; mtime hiçbir karara girmez.
_FILE_FACTS_CACHE: Dict[Tuple[str, int, int], Tuple[int, bytes, str]] = {}
_FILE_FACTS_LIMIT = 4000
_HEAD_CHARS = 1200


# Tek bir status() çağrısı aynı raporu üç kez soruyor (etiket başı, parmak izi,
# içerik özeti). Dosya sistemi OneDrive üzerinde olduğu için stat() pahalı;
# çağrı süresince stat sonuçları hatırlanır. İş parçacığına özel: eşzamanlı
# çağrılar birbirinin belleğini görmez.
_STAT_MEMO = threading.local()


@contextlib.contextmanager
def _stat_memo():
    """Blok süresince path.stat() sonuçlarını hatırlar."""
    outer = getattr(_STAT_MEMO, "memo", None)
    if outer is None:
        _STAT_MEMO.memo = {}
    try:
        yield
    finally:
        _STAT_MEMO.memo = outer


def _stat(path: Path):
    memo = getattr(_STAT_MEMO, "memo", None)
    if memo is None:
        return path.stat()
    key = str(path)
    hit = memo.get(key, _MISSING)
    if hit is _MISSING:
        try:
            hit = path.stat()
        except OSError as exc:
            hit = exc
        memo[key] = hit
    if isinstance(hit, OSError):
        raise hit
    return hit


_MISSING = object()

# resolve() Windows'ta _getfinalpathname çağırır ve indeksteki her yol için
# yeniden çalıştırılıyordu (çağrı başına ~246 çözümleme, ~30 ms). Yol->çözülmüş
# eşlemesi süreç ömrü boyunca sabittir.
_RESOLVE_CACHE: Dict[str, Optional[Path]] = {}


def _resolved(path: Path) -> Optional[Path]:
    key = str(path)
    if key in _RESOLVE_CACHE:
        return _RESOLVE_CACHE[key]
    try:
        value = path.resolve()
    except OSError:
        value = None
    if len(_RESOLVE_CACHE) > _FILE_FACTS_LIMIT:
        _RESOLVE_CACHE.clear()
    _RESOLVE_CACHE[key] = value
    return value


def _file_facts(path: Path) -> Optional[Tuple[int, bytes, str]]:
    """(boyut, sha1 özeti, küçük harfli baş kısım); dosya okunamazsa None."""
    try:
        st = _stat(path)
    except OSError:
        return None
    key = (str(path), st.st_size, st.st_mtime_ns)
    cached = _FILE_FACTS_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        data = path.read_bytes()
    except OSError:
        return None
    facts = (
        len(data),
        hashlib.sha1(data).digest(),
        data.decode("utf-8", errors="ignore")[:_HEAD_CHARS].lower(),
    )
    if len(_FILE_FACTS_CACHE) > _FILE_FACTS_LIMIT:
        _FILE_FACTS_CACHE.clear()
    _FILE_FACTS_CACHE[key] = facts
    return facts


def clear_file_facts_cache() -> None:
    """Testler ve kasa değişimi için önbellekleri boşaltır."""
    _FILE_FACTS_CACHE.clear()
    _RESOLVE_CACHE.clear()

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

# Büyük arşivlerde rapor başına okunan karakter. Ham ön ek yerine yordam taşıyan
# bloklar seçildiği için daha az karakter aynı sinyali taşır; böylece bir tura
# aynı prompt boyutuyla çok daha fazla rapor sığar ve tur sayısı düşer.
# Ölçüm (2026-09-08, gerçek kasa): raporların %98'i zaten markdown-yapılı olduğu
# için "yalnızca yapısal blokları al" tek başına hiçbir tasarruf üretmiyor
# (%98 of mevcut); tasarruf blok SEÇİMİNDEN ve tavanın düşmesinden geliyor.
PROCEDURAL_EXCERPT_CHARS = 900

# Yakın-kopya eşiği: iki raporun 5'li sözcük parmakları arasındaki kapsama oranı
# (küçük kümeye göre) bu değeri aşarsa ikincisi temsilciye bağlanır ve okunmaz.
# Ölçüm: autonomous-agent 513 rapor → 297 temsilci (%42 eleme); financial-auditor
# 104 → 100 (%4). Yani eleme, gerçekten tekrar eden arşivlerde işe yarıyor.
NEAR_DUPLICATE_CONTAINMENT = 0.5

# Parmak izi çıkarılırken raporun ilk bu kadar karakteri okunur; bir raporun
# kimliği baş kısmında belirir ve tüm arşivi tam okumak kümeleme maliyetini
# gereksiz büyütür.
_SIGNATURE_CHARS = 6000
_SHINGLE_SIZE = 5

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
# Oturum aktarım sayfaları (Sessions/) bilerek dışarıda: bunlar yordam değil OLAY
# kaydıdır ("şu oturumda şunu yaptık"). Damıtmaya girerlerse playbook, tekrar
# edilebilir bir yöntem yerine geçmişin günlüğüne dönüşür. Bağlam kurucu ve geri
# çağırma onları ayrıca görür (bkz. memory/handoff.py).
# Tasks/, Agents/ ve wiki/ de aynı gerekçeyle dışarıda: görev kuyruğu, ajan
# belleği ve sorgu sayfaları olay/durum kaydıdır, tekrar edilebilir yordam değil.
# Bağlam kurucu ve geri çağırma onları ayrıca görür (wiki.py, agent_memory.py).
# Offices/ de dışarıda: ofis klasöründeki dosyalar ya ofis belleği ya da wiki
# sayfasına giden kısa bir işaretçi özettir. Tam metin zaten wiki sorgu
# sayfasındadır ve o da damıtma kaynağı değildir; özeti kaynak saysaydık aynı
# turun kırpılmış kopyası yordam gibi damıtılırdı.
_NON_REPORT_DIRS = {
    "dailynotes", "agentdesk", "pendinginbox", "templates", ".obsidian",
    "sessions", "tasks", "agents", "wiki", "queries", "offices",
}
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

    def all_paths(self) -> Set[str]:
        """İndekste geçen tüm rapor yolları (artımlı güncellemede 'yeni mi' testi)."""
        out: Set[str] = set()
        for paths in self.load().values():
            out.update(paths)
        return out

    def add(self, skill: str, path: Path, save: bool = True) -> bool:
        """
        Tek raporu indekse ekler; gerçekten eklendiyse True.

        Tam yeniden tarama (rebuild) 800+ dosya okur ve OneDrive'da saniyeler
        sürer. Rapor yazıldığı anda yalnızca o dosyayı eklemek, kartın sayacının
        anında artması için yeterlidir.
        """
        if not skill:
            return False
        key = str(path)
        self.load()
        bucket = self._map.setdefault(skill, [])
        if key in bucket:
            return False
        bucket.append(key)
        if save:
            self.save()
        return True

    def add_many(self, pairs: List[Tuple[str, Path]]) -> int:
        """Birden çok (yetenek, yol) çiftini tek yazımla ekler; eklenen sayısı döner."""
        added = 0
        for skill, path in pairs:
            if self.add(skill, path, save=False):
                added += 1
        if added:
            self.save()
        return added

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

    def tag_scan_dirs(self) -> List[Path]:
        """
        `skill:` etiketi aranacak rapor klasörleri.

        Düz Reports/ ve her projenin Reports/ klasörü. Yetenek-kapsamlı klasörler
        buraya girmez: onlar zaten doğrudan okunuyor.
        """
        entropy_dir = self.vault_path / "Entropy"
        dirs: List[Path] = []
        flat = entropy_dir / "Reports"
        if flat.is_dir():
            dirs.append(flat)
        projects = entropy_dir / "Projects"
        if projects.is_dir():
            try:
                for child in sorted(projects.iterdir()):
                    rep = child / "Reports"
                    if rep.is_dir():
                        dirs.append(rep)
            except OSError:
                pass
        return dirs

    def tagged_reports(self, skill: str) -> List[Path]:
        """`skill:<ad>` etiketi taşıyan raporlar (düz + proje kapsamlı klasörler)."""
        needle = f"skill:{self._safe(skill)}".lower()
        alt = f"skill:{skill}".lower()
        out: List[Path] = []
        for d in self.tag_scan_dirs():
            for p in sorted(d.glob("*.md")):
                if p.stem.strip().lower() in _NON_REPORT_STEMS:
                    continue
                facts = _file_facts(p)
                if facts is None:
                    continue
                head = facts[2]
                if needle in head or alt in head:
                    out.append(p)
        return out

    # -- kaynak raporlar ------------------------------------------------

    def source_reports(self, skill: str) -> List[Path]:
        """
        Yeteneğe ait raporlar.

        Üç kaynaktan toplanır:
          1. Yetenek-kapsamlı klasör (yeni yazılan raporlar buraya gider)
          2. Etiketli raporlar: düz Reports/ VE Projects/<proje>/Reports/ içinde
             `skill:<ad>` etiketi taşıyanlar
          3. Yetenek-rapor indeksi (etiketsiz eski raporlar için)

        Üçüncüsü gerekli, çünkü kasadaki mevcut raporlar yetenek ayrımı
        yapılmadan önce yazılmıştı ve dosyalarına dokunmadan eşlenmeleri gerekiyor.
        """
        found: Dict[Path, None] = {}

        scoped = self.reports_dir(skill)
        if scoped.is_dir():
            for p in sorted(scoped.glob("*.md")):
                found[p] = None

        # Etiketli raporlar. Düz Reports/ TEK BAŞINA yetmiyor: köprü, etkin bir
        # proje varsa raporu Projects/<proje>/Reports/ altına yazıyor ve yetenek
        # yalnızca `skill:` etiketi olarak kalıyor. Ölçüm (gerçek kasa, 2026-09-09):
        # düz Reports/ altında etiketli 0 rapor, Projects/*/Reports/ altında 77
        # (autonomous-agent 26, permissioned-github 27, financial-auditor 13,
        # google-flow 3). Yalnızca düz klasör tarandığı için bu raporların hiçbiri
        # kaynak sayılmıyor, google-flow gibi yeni yetenekler "kaynak yok" görünüyordu.
        for p in self.tagged_reports(skill):
            found.setdefault(p, None)

        # İndeks süreç genelinde tek dosyadır; başka bir kasaya ait girdiler
        # aktif kasanın sonuçlarına karışmamalı (kasa değiştirildiğinde ya da
        # izole bir kasayla çalışılırken yanlış raporlar bağlama girerdi).
        vault_root = self.vault_path.resolve()
        for p in self.index.paths_for(skill):
            # Eski indeksler PLAYBOOK.md'yi rapor sanmış olabilir; burada da elenir.
            if p.stem.strip().lower() in _NON_REPORT_STEMS:
                continue
            # Eski indeksler Sessions/, Tasks/, Agents/, wiki/ dosyalarını da
            # kaynak saymış olabilir: dizin kuralı burada da uygulanır.
            if {part.lower() for part in p.parts} & _NON_REPORT_DIRS:
                continue
            resolved = _resolved(p)
            if resolved is None or vault_root not in resolved.parents:
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
                return (_stat(p).st_mtime_ns, p.name.lower())
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
            facts = _file_facts(p)
            if facts is None:
                continue
            h.update(str(facts[0]).encode("ascii"))
            h.update(facts[1])
        return h.hexdigest()[:16]

    # -- işlenmiş rapor kümesi (yan dosya) --------------------------------

    def state_path(self, skill: str) -> Path:
        return self.playbook_path(skill).parent / "PLAYBOOK.state.json"

    @staticmethod
    def content_sha(path: Path) -> str:
        """Raporun içerik özeti; ad aynı kalıp gövdesi değişen rapor yeniden okunsun diye."""
        facts = _file_facts(path)
        if facts is None:
            return ""
        return facts[1].hex()[:16]

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
        with _stat_memo():
            return self._status_inner(skill)

    def _status_inner(self, skill: str) -> Dict[str, Any]:
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


_SKILL_TAG_RE = re.compile(r"skill:\s*([A-Za-z0-9 _\-]+)")


def skill_tag_of(head_text: str) -> Optional[str]:
    """Rapor başlığındaki `skill:<ad>` etiketi; yoksa None."""
    m = _SKILL_TAG_RE.search(head_text or "")
    if not m:
        return None
    name = m.group(1).strip().strip("]").strip()
    return name or None


def classify_report(path: Path, known_skills: Set[str], classify=None) -> Optional[str]:
    """
    Tek bir raporun yeteneği: önce `skill:` etiketi, sonra anlamsal sınıflandırıcı.

    Etiket varsa model/anlamsal iş yapılmaz — etiket zaten üreten tarafın kesin
    beyanıdır ve tek dosya için sınıflandırıcı çağırmak gereksiz maliyettir.
    """
    facts = _file_facts(path)
    if facts is None:
        return None
    head = facts[2]
    tagged = skill_tag_of(head)
    if tagged and (not known_skills or tagged in known_skills):
        return tagged
    if classify is None:
        return None
    try:
        hit = classify(path.stem, head)
    except Exception:
        return None
    if hit and (not known_skills or hit in known_skills):
        return hit
    return None


def index_new_reports(
    store: "PlaybookStore",
    known_skills: Optional[Set[str]] = None,
    classify=None,
    limit: int = 200,
) -> Dict[str, int]:
    """
    İndekste bulunmayan raporları artımlı olarak eşler; {yetenek: eklenen} döner.

    `rebuild()` kasadaki her raporu okur (gerçek kasada 800+ dosya, OneDrive'da
    saniyeler). Buradaki geçiş yalnızca indekste HENÜZ OLMAYAN dosyaları okur;
    kararlı durumda hiçbir dosya okunmaz, tek bir dizin taraması yapılır.
    `limit` tek geçişte eşlenecek dosya tavanıdır: ilk kurulumda bin dosyalık bir
    kasa arayüzü kilitlemesin, sonraki geçişler kaldığı yerden sürsün.
    """
    index = store.index
    known = index.all_paths()
    skills = set(known_skills or ())
    pairs: List[Tuple[str, Path]] = []
    for p in discover_reports(store.vault_path):
        if len(pairs) >= limit:
            break
        if str(p) in known:
            continue
        # Yetenek-kapsamlı klasördeki rapor zaten doğrudan okunuyor; indekste
        # ikinci kez durması gereksiz.
        if "Skills" in p.parts and "Reports" in p.parts:
            continue
        skill = classify_report(p, skills, classify)
        if skill:
            pairs.append((skill, p))
    if not pairs:
        return {}
    index.add_many(pairs)
    out: Dict[str, int] = {}
    for skill, _p in pairs:
        out[skill] = out.get(skill, 0) + 1
    return out


# ---------------------------------------------------------------------------
# Damıtma (AGY üzerinden)
# ---------------------------------------------------------------------------


def _strip_frontmatter(text: str) -> str:
    m = re.match(r"^---\s*\n.*?\n---\s*\n(.*)$", text, re.DOTALL)
    return (m.group(1) if m else text).strip()


# ---------------------------------------------------------------------------
# Yordam taşıyan alıntı seçimi
# ---------------------------------------------------------------------------

_WORD_RE = re.compile(r"\w+", re.UNICODE)

# Yordam sinyali taşıyan sözcükler. Bir blokta geçiyorsa o blok "bu iş nasıl
# yapılır" bilgisi taşıyor demektir; olgu tabloları ve anlatı paragrafları değil.
_PROCEDURAL_TERMS = (
    "adım", "adim", "yöntem", "yontem", "kontrol", "tuzak", "ölçüt", "olcut",
    "kural", "süreç", "surec", "aşama", "asama", "kriter", "doğrula", "dogrula",
    "önce", "sonra", "eşik", "esik", "checklist", "step", "method", "process",
    "pitfall", "criteria", "workflow", "verify", "rule", "threshold",
)

# Yapısal blok: başlık, numaralı adım ya da madde imi ile başlayan blok.
_STRUCTURAL_RE = re.compile(r"^\s*(#{1,4}\s|\d+[\.\)]\s|[-*+]\s)")
# Olgu yığını: tablo satırı ya da ağırlıklı olarak sayı/bağlantı içeren blok.
_TABLE_RE = re.compile(r"(?m)^\s*\|")
_URL_RE = re.compile(r"https?://")


def _words(text: str) -> List[str]:
    return [w.lower() for w in _WORD_RE.findall(text or "") if len(w) > 2]


def _shingles(text: str, n: int = _SHINGLE_SIZE) -> Set[int]:
    """Metnin n'li sözcük parmak izi kümesi; yakın-kopya ve yenilik ölçümü için."""
    ws = _words(text)
    if len(ws) < n:
        return set()
    return {hash(tuple(ws[i : i + n])) for i in range(len(ws) - n + 1)}


def procedural_excerpt(body: str, max_chars: int, known_shingles: Optional[Set[int]] = None) -> str:
    """
    Rapordan yordam taşıyan blokları seçer; ham ön ek yerine bunlar gönderilir.

    Ham ilk N karakter, çoğu raporda başlık tekrarı ve giriş anlatısıdır. Burada
    bloklar puanlanır: başlık ve numaralı adımlar artı, yordam sözcükleri artı,
    tablo/bağlantı yığınları eksi. `known_shingles` verilirse (mevcut yordamın
    parmak izi) zaten bilinen içerik puan kaybeder — turun bütçesi yeni bilgiye
    ayrılır.

    Bloklar puana göre seçilir ama belge sırasında yazılır; sıra bozulursa
    adımların birbirini izlediği bilgisi kaybolur.
    """
    if not body:
        return ""
    if len(body) <= max_chars:
        return body

    blocks = [b.strip() for b in re.split(r"\n\s*\n", body) if b.strip()]
    if not blocks:
        return body[:max_chars]

    scored: List[Tuple[float, int]] = []
    for idx, blk in enumerate(blocks):
        low = blk.lower()
        score = 0.0
        if _STRUCTURAL_RE.match(blk):
            score += 3.0
        # Gövdesiz başlık (yalnızca "## 1. Giriş") alıntıda yer kaplar, yordam
        # taşımaz: yapısal puanı geri alınır.
        if "\n" not in blk and blk.lstrip().startswith("#"):
            score -= 3.0
        score += min(6.0, 2.0 * sum(1 for t in _PROCEDURAL_TERMS if t in low))
        if _TABLE_RE.search(blk):
            score -= 3.0
        if len(_URL_RE.findall(blk)) >= 3:
            score -= 2.0
        digits = sum(1 for c in blk if c.isdigit())
        if len(blk) > 80 and digits / len(blk) > 0.25:
            score -= 2.0
        if known_shingles:
            sh = _shingles(blk)
            if sh:
                novelty = len(sh - known_shingles) / len(sh)
                score += 2.0 * novelty - 1.0
        # Belge başındaki blok küçük bir öncelik alır: bağlamı o kurar.
        if idx == 0:
            score += 1.0
        scored.append((score, idx))

    scored.sort(key=lambda x: (-x[0], x[1]))

    chosen: Set[int] = set()
    used = 0
    for score, idx in scored:
        if score <= 0 and chosen:
            break
        blk = blocks[idx]
        if used + len(blk) > max_chars:
            if chosen:
                continue
            blk = blk[:max_chars]
        chosen.add(idx)
        used += len(blk)
        if used >= max_chars:
            break

    if not chosen:
        return body[:max_chars]

    out: List[str] = []
    total = 0
    for idx in sorted(chosen):
        blk = blocks[idx]
        if total + len(blk) > max_chars:
            blk = blk[: max(0, max_chars - total)]
        if not blk:
            break
        out.append(blk)
        total += len(blk)
    return "\n\n".join(out).strip()


# Parmak izi önbelleği: aynı zincirde her tur tüm işlenmemiş kümeyi yeniden
# kümelendiriyor; dosya değişmediyse yeniden okumanın anlamı yok.
_SIG_CACHE: Dict[Tuple[str, int, int], Set[int]] = {}


def _cached_signature(path: Path) -> Set[int]:
    st = path.stat()
    key = (str(path), st.st_size, st.st_mtime_ns)
    cached = _SIG_CACHE.get(key)
    if cached is not None:
        return cached
    body = _strip_frontmatter(path.read_text(encoding="utf-8", errors="ignore"))
    sig = _shingles(body[:_SIGNATURE_CHARS])
    if len(_SIG_CACHE) > 4000:
        _SIG_CACHE.clear()
    _SIG_CACHE[key] = sig
    return sig


def select_representatives(
    paths: List[Path],
    threshold: float = NEAR_DUPLICATE_CONTAINMENT,
) -> Tuple[List[Path], Dict[str, List[str]]]:
    """
    Yakın-kopya raporları tek temsilciye indirir.

    Aynı işin tekrarlanan koşumları arşive neredeyse aynı raporu birden çok kez
    yazıyor; hepsini damıtmak aynı yordamı defalarca okumak demek. Burada 5'li
    sözcük parmak izleri üzerinden kapsama oranı ölçülür ve eşiği aşan rapor,
    daha önce görülmüş temsilciye bağlanır.

    Döndürür: (temsilciler, {temsilci adı: [bağlı rapor adları]}). Bağlı raporlar
    okunmaz ama işlenmiş sayılır; aksi hâlde zincir hiç bitmez.

    Parmak izi çıkarılamayan (çok kısa) raporlar her zaman temsilci kalır: eleme
    ancak gerçekten ölçülebilen benzerlikte yapılır.
    """
    reps: List[Path] = []
    rep_sigs: List[Set[int]] = []
    followers: Dict[str, List[str]] = {}

    for p in paths:
        try:
            sig = _cached_signature(p)
        except OSError:
            reps.append(p)
            rep_sigs.append(set())
            continue
        if not sig:
            reps.append(p)
            rep_sigs.append(sig)
            continue
        match = -1
        for i, rsig in enumerate(rep_sigs):
            if not rsig:
                continue
            inter = len(sig & rsig)
            if inter and inter / min(len(sig), len(rsig)) >= threshold:
                match = i
                break
        if match >= 0:
            followers.setdefault(reps[match].name, []).append(p.name)
        else:
            reps.append(p)
            rep_sigs.append(sig)

    return reps, followers


# ---------------------------------------------------------------------------
# Playbook kalite ölçütü
# ---------------------------------------------------------------------------

# İstenen beş başlıktan dördü kararı taşır: adımlar olmadan yordam yoktur,
# ölçüt olmadan karar verilemez, tuzaklar tekrarlanan hataları önler, çıktı
# biçimi sonucun kullanılabilir olmasını sağlar. "Ne Zaman Kullanılır" bunlara
# göre süs olduğu için kapsam hesabına girmez.
QUALITY_SECTIONS: Dict[str, Tuple[str, ...]] = {
    "steps": ("adım", "adim", "step", "workflow", "prosedür", "prosedur"),
    "criteria": ("ölçüt", "olcut", "criteria", "karar", "eşik", "esik", "kriter"),
    "pitfalls": ("tuzak", "pitfall", "hata", "risk"),
    "output": ("çıktı", "cikti", "output", "biçim", "bicim", "rapor biçimi"),
}

_STEP_LINE_RE = re.compile(r"(?m)^\s*(?:\d+[\.\)]\s+|[-*+]\s+)\S")


def playbook_quality(procedure: str) -> Dict[str, Any]:
    """
    Bir yordamın ölçülebilir kalitesi.

    Uzunluk tek başına kalite değildir: 9000 karakterlik tekrar eden bir metin,
    3000 karakterlik dört bölümlü bir yordamdan kötüdür. Bu yüzden dört ölçü
    birleştirilir:

      - bölüm kapsamı  : dört zorunlu başlıktan kaçı var (en ağırlıklı)
      - adım sayısı    : numaralı/madde imli satırlar (12'de doyar)
      - tekrar oranı   : 5'li sözcük parmaklarının ne kadarı yinelenmiş
      - uzunluk yeterliliği: 4000 karakterde doyar

    Döndürülen `score` 0-1 arasıdır ve DegenerateDistillation korumasında
    kullanılır.
    """
    text = (procedure or "").strip()
    headings = [h.strip().lower() for h in re.findall(r"(?m)^#{2,4}\s+(.+)$", text)]
    found = {
        key: any(any(t in h for t in terms) for h in headings)
        for key, terms in QUALITY_SECTIONS.items()
    }
    coverage = sum(1 for v in found.values() if v) / len(QUALITY_SECTIONS)

    step_count = len(_STEP_LINE_RE.findall(text))

    ws = _words(text)
    if len(ws) >= _SHINGLE_SIZE:
        grams = [tuple(ws[i : i + _SHINGLE_SIZE]) for i in range(len(ws) - _SHINGLE_SIZE + 1)]
        repetition = 1.0 - (len(set(grams)) / len(grams))
    else:
        repetition = 0.0

    chars = len(text)
    length_fit = min(1.0, chars / 4000.0)

    score = (
        0.50 * coverage
        + 0.20 * min(1.0, step_count / 12.0)
        + 0.20 * (1.0 - repetition)
        + 0.10 * length_fit
    )

    return {
        "coverage": round(coverage, 3),
        "sections": {k: bool(v) for k, v in found.items()},
        "missing": [k for k, v in found.items() if not v],
        "step_count": step_count,
        "repetition": round(repetition, 3),
        "chars": chars,
        "tokens": estimate_tokens(text),
        "score": round(score, 3),
    }


def build_distillation_prompt(
    skill: str,
    sources: List[Path],
    description: str = "",
    existing_procedure: str = "",
    excerpt_chars: int = DISTILL_EXCERPT_CHARS,
    procedural: bool = False,
) -> str:
    """
    Raporlardan yordam çıkarması için AGY'ye verilecek prompt'u üretir.

    Raporların tamamı değil, her birinden bir alıntı gönderilir. Amaç içeriği
    özetlemek değil — yeniden kullanılabilir bir çalışma yordamı çıkarmaktır.

    existing_procedure verilirse (ikinci ve sonraki turlar) model sıfırdan
    yazmaz; mevcut yordamı yeni raporlarla birleştirip zenginleştirir. Böylece
    111 raporluk bir arşiv 24'lük turlarla, her turda bilgi kaybetmeden işlenir.

    procedural=True verilirse alıntı ham ön ek değil, yordam taşıyan bloklardan
    seçilir ve mevcut yordamda zaten geçen içerik puan kaybeder. Büyük arşivlerde
    böylece rapor başına ~3 kat az karakterle aynı sinyal taşınır; tur başına
    daha çok rapor sığar, tur sayısı ve toplam maliyet düşer.
    """
    known = _shingles(existing_procedure) if (procedural and existing_procedure.strip()) else None
    chunks: List[str] = []
    for p in sources:
        try:
            body = _strip_frontmatter(p.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
        if not body:
            continue
        excerpt = procedural_excerpt(body, excerpt_chars, known) if procedural else body[:excerpt_chars]
        if not excerpt:
            continue
        chunks.append(f"### Kaynak: {p.stem}\n{excerpt}")

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
        # Uzunluk ve başlık sayısı kaba ölçülerdir: 9000 karakterlik tekrar eden
        # bir metin ikisini de geçer. Olgun bir yordam (dört zorunlu başlıktan
        # en az üçü) varsa karar kalite ölçütüne bırakılır; bölüm kaybeden ve
        # puanı belirgin düşen çıktı, uzun olsa bile reddedilir.
        old_q = playbook_quality(existing.procedure)
        new_q = playbook_quality(procedure)
        quality_regression = (
            old_q["coverage"] >= 0.75
            and new_q["coverage"] < old_q["coverage"]
            and new_q["score"] < 0.75 * old_q["score"]
        )
        if too_short or lost_structure or quality_regression:
            raise DegenerateDistillation(
                f"'{skill}' için damıtma çıktısı reddedildi: {len(procedure)} karakter / "
                f"{new_sections} bölüm / kalite {new_q['score']} "
                f"(mevcut {len(existing.procedure)} karakter / {old_sections} bölüm / "
                f"kalite {old_q['score']}). Mevcut yordam korundu."
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
