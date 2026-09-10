"""
Beceri sentezi döngüsü v1 (Faz 12-C) — SKILLFOUNDRY şeması.

Girdi iki yerden gelir:

1. **Bir yetenek**: damıtılmış playbook (`PLAYBOOK.md`) + wiki sayfaları +
   kaynak raporlar.
2. **"Tekrarlayan iş" sinyali**: aynı konuda ≥ `MIN_RECURRENCE` rapor/kart
   birikmişse (`recurring_signals`) o konu bir beceri paketine adaydır.

Çıktı **aday**tır, etkin beceri değildir:
`<kasa>/Entropy/Skills/_candidates/<ad>/{SKILL.md, scripts/<ad>.py,
tests/test_<ad>.py, CANDIDATE.json}`.

Kota: iskelet üretimi **kotasızdır** (playbook bölümlerinden türetilir).
`send_prompt` verilirse **tek tur** zenginleştirme yapılır
(`core/bridge_prompt.make_send_prompt` sözleşmesi: eşzamanlı
`send_prompt(prompt) -> str`). Bu modül köprüyü tanımaz, kendi başına tur açmaz.

Öz-doğrulama kotasızdır (`validate_candidate`): şema tamlığı, kaynak
(provenance) varlığı, adımların test edilebilirliği ve marka/Entropy sızıntısı
denetlenir. Sonuç `CANDIDATE.json` içindeki `status` alanına yazılır:
`draft | validated | approved | rejected`.

**Onaysız etkinleşmez:** aday ancak `promote_skill(ad)` ile
`<kasa>/Skills/<ad>/` altına kopyalanır (çalışma anı keşif kökü);
`reject_skill(ad)` adayı reddeder (dosya silinmez). Arayüz kural onay paneliyle
aynı yüzeyde `list_candidates()` çıktısını gösterir; bu modül sinyal yaymaz.
"""

from __future__ import annotations

import datetime
import json
import logging
import re
import shutil
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

#: Aday paketlerin kasa içindeki kökü (kullanıcı okuyup düzeltebilsin diye kasada).
CANDIDATES_SUBDIR = "Entropy/Skills/_candidates"
#: Onaylanan becerinin gideceği çalışma anı keşif kökü (`skills/manager.py`).
PROMOTED_SUBDIR = "Skills"

CANDIDATE_STATE_FILENAME = "CANDIDATE.json"
SCHEMA_VERSION = 1

STATUS_DRAFT = "draft"
STATUS_VALIDATED = "validated"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
VALID_STATUSES = (STATUS_DRAFT, STATUS_VALIDATED, STATUS_APPROVED, STATUS_REJECTED)

#: SKILLFOUNDRY paket şeması: bu yedi bölüm zorunludur (dördü bizde yeni:
#: ortam varsayımları, provenance, sonlandırma ölçütü, testler).
REQUIRED_SECTIONS = (
    "Ne zaman kullanılır",
    "Ortam varsayımları",
    "Girdiler",
    "Çıktılar",
    "Adımlar",
    "Sonlandırma ölçütü",
    "Kaynaklar",
)

#: "Tekrarlayan iş" eşiği: aynı konuda bu kadar rapor/kart varsa beceri adayı.
MIN_RECURRENCE = 3
#: Kaynak listesinde en fazla kaç rapor adı yazılır (SKILL.md okunabilir kalsın).
MAX_PROVENANCE_ITEMS = 8
#: Zenginleştirme isteminin taşıdığı azami playbook karakteri.
PROMPT_PROCEDURE_CHARS = 4000
#: Model gövdesinin azami kabul boyu.
MAX_BODY_CHARS = 6000

#: Marka kuralı: ticari referans ürünün adı hiçbir dosyaya yazılmaz. Sabit
#: parçalı yazılır ki literal bu dosyada da geçmesin.
_FORBIDDEN_BRAND = "".join(("mur", "atify"))
#: Beceri paketi kullanıcının kasasına ve CLI'lara gider: uygulamanın kendi
#: kimliği oraya sızmamalı.
_INTERNAL_NEEDLE = "entropy"


# ---------------------------------------------------------------------------
# yollar
# ---------------------------------------------------------------------------


def _vault(vault_path: Optional[Path] = None) -> Path:
    from entropy.core.paths import vault_root

    return vault_root(vault_path)


def slugify(name: str) -> str:
    """Dosya sistemi güvenli beceri adı (küçük harf, tire)."""
    text = (name or "").strip().lower()
    text = re.sub(r"[^a-z0-9çğıöşü _-]+", "", text)
    text = re.sub(r"[\s_]+", "-", text).strip("-")
    return text or "beceri"


def candidates_root(vault_path: Optional[Path] = None) -> Path:
    return _vault(vault_path) / CANDIDATES_SUBDIR


def candidate_dir(name: str, vault_path: Optional[Path] = None) -> Path:
    return candidates_root(vault_path) / slugify(name)


def candidate_state_path(name: str, vault_path: Optional[Path] = None) -> Path:
    return candidate_dir(name, vault_path) / CANDIDATE_STATE_FILENAME


def promoted_root(vault_path: Optional[Path] = None) -> Path:
    return _vault(vault_path) / PROMOTED_SUBDIR


# ---------------------------------------------------------------------------
# durum dosyası
# ---------------------------------------------------------------------------


def load_state(name: str, vault_path: Optional[Path] = None) -> Dict[str, Any]:
    path = candidate_state_path(name, vault_path)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("CANDIDATE.json okunamadı (%s): %s", name, exc)
        return {}


def save_state(name: str, state: Dict[str, Any], vault_path: Optional[Path] = None) -> Optional[Path]:
    path = candidate_state_path(name, vault_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        state["updated"] = _now()
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        return path
    except OSError as exc:
        logger.warning("CANDIDATE.json yazılamadı (%s): %s", name, exc)
        return None


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# 1. tekrarlayan iş sinyali
# ---------------------------------------------------------------------------


def recurring_signals(
    vault_path: Optional[Path] = None,
    store: Any = None,
    min_reports: int = MIN_RECURRENCE,
) -> List[Dict[str, Any]]:
    """
    Aynı konuda ≥ `min_reports` rapor birikmiş yetenekleri döndürür.

    Kotasız: yalnızca rapor indeksi okunur. Dönen satır:
    `{skill, reports, has_playbook, candidate_status}`.
    """
    from entropy.memory.playbook import PlaybookStore

    store = store or PlaybookStore(vault_path=vault_path)
    vault_path = vault_path if vault_path is not None else store.vault_path
    out: List[Dict[str, Any]] = []
    skills_dir = Path(getattr(store, "skills_dir", Path(vault_path) / "Entropy" / "Skills"))
    names: List[str] = []
    if skills_dir.is_dir():
        for child in sorted(skills_dir.iterdir()):
            if child.is_dir() and not child.name.startswith("_"):
                names.append(child.name)
    try:
        names += [s for s in (store.index.load() or {}).keys() if s not in names]
    except Exception:  # pragma: no cover - indeks yoksa yetenek klasörleri yeter
        pass
    for skill in names:
        try:
            count = len(store.source_reports(skill))
        except Exception as exc:  # pragma: no cover
            logger.warning("Kaynak raporlar sayılamadı (%s): %s", skill, exc)
            continue
        if count < max(1, int(min_reports)):
            continue
        out.append({
            "skill": skill,
            "reports": count,
            "has_playbook": store.playbook_path(skill).is_file(),
            "candidate_status": str(load_state(skill, vault_path).get("status") or ""),
        })
    out.sort(key=lambda r: r["reports"], reverse=True)
    return out


# ---------------------------------------------------------------------------
# 2. iskelet üretimi (kotasız)
# ---------------------------------------------------------------------------


def _sections_from_playbook(procedure: str) -> Dict[str, str]:
    """Playbook bölümlerini şema bölümlerine kabaca eşler (LLM'siz)."""
    try:
        from entropy.memory.wiki import split_playbook_sections

        chunks = [text for _title, text in split_playbook_sections(procedure or "")]
    except Exception:  # pragma: no cover
        chunks = [c for c in (procedure or "").split("\n\n") if c.strip()]
    steps: List[str] = []
    for chunk in chunks:
        for line in chunk.splitlines():
            stripped = line.strip()
            if re.match(r"^([-*+]|\d+[.)])\s+", stripped):
                steps.append(re.sub(r"^([-*+]|\d+[.)])\s+", "", stripped))
    return {
        "steps": "\n".join(f"{i}. {s}" for i, s in enumerate(steps[:12], 1)),
        "first": (chunks[0].strip() if chunks else ""),
    }


def _provenance_lines(skill: str, store: Any, vault_path: Optional[Path]) -> List[str]:
    lines: List[str] = []
    pb_path = store.playbook_path(skill)
    if pb_path.is_file():
        lines.append(f"- Playbook: `{pb_path.name}` (yetenek: {skill})")
    try:
        reports = list(store.source_reports(skill))
    except Exception:  # pragma: no cover
        reports = []
    for path in reports[:MAX_PROVENANCE_ITEMS]:
        lines.append(f"- Rapor: `{path.stem}`")
    if len(reports) > MAX_PROVENANCE_ITEMS:
        lines.append(f"- … ve {len(reports) - MAX_PROVENANCE_ITEMS} rapor daha")
    try:
        from entropy.memory.wiki import wiki_dir

        index = wiki_dir(skill, vault_path) / "INDEX.md"
        if index.is_file():
            lines.append(f"- Wiki indeksi: `{index.name}`")
    except Exception:  # pragma: no cover
        pass
    return lines


def render_skill_md(
    name: str,
    skill: str,
    sections: Dict[str, str],
    provenance: List[str],
    version: int = 1,
) -> str:
    """SKILLFOUNDRY şemasıyla `SKILL.md` metni (ön bilgi + yedi bölüm)."""
    body = [
        "---",
        f"name: {name}",
        f'description: "{sections.get("summary", "").strip()[:180]}"',
        f"version: {version}",
        f"schema_version: {SCHEMA_VERSION}",
        f'source_skill: "{skill}"',
        "---",
        "",
        f"# {name}",
        "",
    ]
    for title in REQUIRED_SECTIONS:
        body.append(f"## {title}")
        body.append("")
        if title == "Kaynaklar":
            body.extend(provenance or ["- (kaynak yok)"])
        else:
            body.append(sections.get(title, "").strip() or "- (doldurulacak)")
        body.append("")
    return "\n".join(body).rstrip() + "\n"


def _skeleton_sections(skill: str, playbook: Any, report_count: int) -> Dict[str, str]:
    parts = _sections_from_playbook(getattr(playbook, "procedure", "") or "")
    summary = (parts["first"].splitlines() or [""])[0].strip("#- ").strip()
    steps = parts["steps"] or "1. (adım yok: playbook boş)"
    return {
        "summary": summary or f"{skill} yordamının paketlenmiş hâli",
        "Ne zaman kullanılır": (
            f"- {skill} konusunda tekrarlayan bir iş geldiğinde "
            f"({report_count} rapor bu konuda birikti).\n"
            f"- Tek seferlik araştırmalarda kullanma; yordam tekrar ediyorsa kullan."
        ),
        "Ortam varsayımları": (
            "- Python 3.13, çevrimdışı çalışabilir.\n"
            "- Girdi dosyaları yerel diskte okunabilir.\n"
            "- Ağ erişimi gerekiyorsa adımda açıkça belirtilir."
        ),
        "Girdiler": "- (girdi tanımı doldurulacak)",
        "Çıktılar": "- (çıktı tanımı doldurulacak)",
        "Adımlar": steps,
        "Sonlandırma ölçütü": (
            f"- `tests/test_{slugify(skill)}.py` yeşil.\n"
            "- Çıktı dosyası üretildi ve boş değil."
        ),
    }


def _script_skeleton(name: str, skill: str) -> str:
    return (
        '"""\n'
        f"{name} — beceri iskeleti (aday).\n\n"
        f"Kaynak yetenek: {skill}. Adımlar SKILL.md'de; bu dosya onların\n"
        "çalıştırılabilir karşılığıdır. Onaylanmadan etkinleşmez.\n"
        '"""\n\n'
        "from __future__ import annotations\n\n"
        "import argparse\n"
        "import json\n"
        "import sys\n\n\n"
        "def run(payload: dict) -> dict:\n"
        '    """Beceri adımlarını uygular; SKILL.md \'Çıktılar\' bölümünü döndürür."""\n'
        '    return {"ok": False, "reason": "iskelet: adımlar henüz uygulanmadı",\n'
        '            "input": dict(payload or {})}\n\n\n'
        "def main(argv=None) -> int:\n"
        "    ap = argparse.ArgumentParser(description=__doc__)\n"
        '    ap.add_argument("--input", default="{}", help="JSON girdi")\n'
        "    args = ap.parse_args(argv)\n"
        "    result = run(json.loads(args.input or \"{}\"))\n"
        "    print(json.dumps(result, ensure_ascii=False, indent=2))\n"
        '    return 0 if result.get("ok") else 1\n\n\n'
        'if __name__ == "__main__":\n'
        "    sys.exit(main())\n"
    )


def _test_skeleton(name: str) -> str:
    module = slugify(name).replace("-", "_")
    return (
        '"""\n'
        f"{name} beceri iskeletinin sonlandırma ölçütü.\n\n"
        "Kanıtla kapat: bu dosya yeşil olmadan beceri onaya sunulmaz.\n"
        '"""\n\n'
        "from pathlib import Path\n\n"
        "SKILL_MD = Path(__file__).resolve().parents[1] / \"SKILL.md\"\n\n"
        "REQUIRED = " + repr(list(REQUIRED_SECTIONS)) + "\n\n\n"
        "def test_skill_md_schema_is_complete():\n"
        '    text = SKILL_MD.read_text(encoding="utf-8")\n'
        "    for title in REQUIRED:\n"
        '        assert f"## {title}" in text, f"eksik bölüm: {title}"\n\n\n'
        f"def test_{module}_run_returns_dict():\n"
        "    import importlib.util\n\n"
        f'    path = Path(__file__).resolve().parents[1] / "scripts" / "{slugify(name)}.py"\n'
        '    spec = importlib.util.spec_from_file_location("candidate_skill", path)\n'
        "    mod = importlib.util.module_from_spec(spec)\n"
        "    spec.loader.exec_module(mod)\n"
        "    assert isinstance(mod.run({}), dict)\n"
    )


# ---------------------------------------------------------------------------
# 3. tek turluk zenginleştirme (isteğe bağlı, kota harcar)
# ---------------------------------------------------------------------------


def build_synthesis_prompt(skill: str, name: str, procedure: str, provenance: List[str]) -> str:
    """Tek turluk zenginleştirme istemi (çağıran turu sayar, modül saymaz)."""
    heads = "\n".join(f"## {t}" for t in REQUIRED_SECTIONS)
    return (
        "[GÖREV: BECERİ PAKETİ TASLAĞI]\n\n"
        f"Beceri adı: {name}\nKaynak yordam: {skill}\n\n"
        "Aşağıdaki çalışma yordamını, yeniden kullanılabilir bir beceri paketine "
        "dönüştür. YALNIZCA markdown gövde yaz; ön bilgi (frontmatter) ve başlık "
        "satırı EKLEME. Bölüm başlıkları AYNEN şunlar ve bu sırada olsun:\n"
        f"{heads}\n\n"
        "Kurallar:\n"
        "- Adımlar test edilebilir olsun: her adım tek bir doğrulanabilir iş.\n"
        "- 'Sonlandırma ölçütü' bir komut ya da ölçülebilir çıktı içersin.\n"
        "- 'Kaynaklar' bölümüne aşağıdaki kaynak listesini aynen taşı; kaynak UYDURMA.\n"
        "- Uygulama adı, marka adı ya da iç mimari adı yazma; beceri bağımsız olsun.\n"
        "- En fazla 4000 karakter.\n\n"
        "--- KAYNAKLAR ---\n"
        + "\n".join(provenance or ["- (kaynak yok)"])
        + "\n\n--- YORDAM ---\n"
        + (procedure or "")[:PROMPT_PROCEDURE_CHARS]
        + "\n"
    )


def parse_enriched_body(text: str) -> Dict[str, str]:
    """Model gövdesini bölüm sözlüğüne ayırır; eksik bölüm sessizce atlanır."""
    out: Dict[str, str] = {}
    if not text or not text.strip():
        return out
    current: Optional[str] = None
    buf: List[str] = []
    for line in text[:MAX_BODY_CHARS].splitlines():
        m = re.match(r"^#{1,3}\s+(.+?)\s*$", line)
        if m:
            if current:
                out[current] = "\n".join(buf).strip()
            title = m.group(1).strip()
            current = title if title in REQUIRED_SECTIONS else None
            buf = []
            continue
        if current:
            buf.append(line)
    if current:
        out[current] = "\n".join(buf).strip()
    return {k: v for k, v in out.items() if v.strip()}


# ---------------------------------------------------------------------------
# 4. sentez
# ---------------------------------------------------------------------------


def synthesize_skill(
    skill: str,
    name: Optional[str] = None,
    send_prompt: Optional[Callable[[str], str]] = None,
    vault_path: Optional[Path] = None,
    store: Any = None,
) -> Dict[str, Any]:
    """
    Bir yetenekten beceri adayı üretir.

    `send_prompt` verilmezse **hiç model çağrılmaz** (`turns = 0`): paket
    playbook bölümlerinden türetilir. Verilirse **tek tur** harcanır ve dönen
    bölümler iskeletin üzerine yazılır (ayrıştırılamayan yanıt iskeleti bozmaz).

    Dönen: `{name, skill, dir, status, turns, checks, findings, files, reason}`.
    """
    from entropy.memory.playbook import PlaybookStore

    store = store or PlaybookStore(vault_path=vault_path)
    vault_path = vault_path if vault_path is not None else store.vault_path
    slug = slugify(name or skill)
    target = candidate_dir(slug, vault_path)

    playbook = store.load(skill)
    try:
        report_count = len(store.source_reports(skill))
    except Exception:  # pragma: no cover
        report_count = 0
    provenance = _provenance_lines(skill, store, vault_path)
    sections = _skeleton_sections(skill, playbook, report_count)

    turns = 0
    reason = "kotasız iskelet (playbook bölümlerinden)"
    if send_prompt is not None:
        prompt = build_synthesis_prompt(
            skill, slug, getattr(playbook, "procedure", "") or "", provenance
        )
        try:
            out = send_prompt(prompt)
            turns = 1
        except Exception as exc:
            out = ""
            reason = f"zenginleştirme turu başarısız: {exc}"
            logger.warning("Beceri sentezi turu başarısız (%s): %s", slug, exc)
        enriched = parse_enriched_body(out or "")
        if enriched:
            sections.update({k: v for k, v in enriched.items() if k != "Kaynaklar"})
            reason = f"tek tur zenginleştirme ({len(enriched)} bölüm)"
        elif turns:
            reason = "yanıt ayrıştırılamadı: iskelet korundu"

    (target / "scripts").mkdir(parents=True, exist_ok=True)
    (target / "tests").mkdir(parents=True, exist_ok=True)
    skill_md = target / "SKILL.md"
    version = int(load_state(slug, vault_path).get("version") or 0) + 1
    skill_md.write_text(
        render_skill_md(slug, skill, sections, provenance, version=version),
        encoding="utf-8",
    )
    script = target / "scripts" / f"{slug}.py"
    if not script.exists():
        script.write_text(_script_skeleton(slug, skill), encoding="utf-8")
    test_file = target / "tests" / f"test_{slug}.py"
    if not test_file.exists():
        test_file.write_text(_test_skeleton(slug), encoding="utf-8")

    state = load_state(slug, vault_path) or {}
    state.update({
        "name": slug,
        "skill": skill,
        "schema_version": SCHEMA_VERSION,
        "version": version,
        "status": STATUS_DRAFT,
        "created": state.get("created") or _now(),
        "turns": turns,
        "reason": reason,
        "sources": [line.lstrip("- ").strip() for line in provenance],
        "reports": report_count,
    })
    save_state(slug, state, vault_path)

    result = validate_candidate(slug, vault_path=vault_path)
    result.update({"turns": turns, "reason": reason, "skill": skill})
    result["files"] = [str(skill_md), str(script), str(test_file)]
    return result


# ---------------------------------------------------------------------------
# 5. öz-doğrulama (kotasız kontrol listesi)
# ---------------------------------------------------------------------------


def _split_sections(text: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    current: Optional[str] = None
    buf: List[str] = []
    for line in (text or "").splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            if current:
                out[current] = "\n".join(buf).strip()
            current = m.group(1).strip()
            buf = []
            continue
        if current:
            buf.append(line)
    if current:
        out[current] = "\n".join(buf).strip()
    return out


def leak_findings(text: str) -> List[str]:
    """Marka ve iç kimlik sızıntısı bulguları (boş liste = temiz)."""
    low = (text or "").lower()
    found: List[str] = []
    if _FORBIDDEN_BRAND in low:
        found.append("marka sızıntısı: ticari referans ürün adı geçiyor")
    if _INTERNAL_NEEDLE in low:
        found.append("iç kimlik sızıntısı: uygulama adı beceri paketinde geçiyor")
    return found


def validate_candidate(name: str, vault_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Kotasız kontrol listesi; `CANDIDATE.json` `status` alanını günceller.

    Kontroller: `schema_complete`, `has_provenance`, `steps_testable`,
    `no_leak`, `has_script`, `has_test`. Hepsi geçerse `validated`, aksi hâlde
    `draft`. Reddedilmiş aday yeniden doğrulanmaz (kararı insan verir).
    """
    slug = slugify(name)
    target = candidate_dir(slug, vault_path)
    skill_md = target / "SKILL.md"
    findings: List[str] = []
    checks: Dict[str, bool] = {}

    text = skill_md.read_text(encoding="utf-8") if skill_md.is_file() else ""
    sections = _split_sections(text)

    missing = [
        t for t in REQUIRED_SECTIONS
        if not sections.get(t) or "doldurulacak" in sections.get(t, "")
    ]
    checks["schema_complete"] = not missing and bool(text)
    if missing:
        findings.append("eksik/boş bölüm: " + ", ".join(missing))

    prov = sections.get("Kaynaklar", "")
    prov_items = [l for l in prov.splitlines() if l.strip().startswith("-")
                  and "(kaynak yok)" not in l]
    checks["has_provenance"] = bool(prov_items)
    if not prov_items:
        findings.append("kaynak (provenance) yok: SKILLFOUNDRY şeması kaynak zorunlu kılar")

    steps = sections.get("Adımlar", "")
    step_lines = [l for l in steps.splitlines()
                  if re.match(r"^\s*([-*+]|\d+[.)])\s+\S", l)]
    finish = sections.get("Sonlandırma ölçütü", "")
    testable = len(step_lines) >= 2 and bool(finish.strip()) and bool(
        re.search(r"(test|pytest|komut|`|çıktı)", finish, re.IGNORECASE)
    )
    checks["steps_testable"] = testable
    if not testable:
        findings.append(
            "adımlar test edilebilir değil: en az 2 adım ve ölçülebilir "
            "sonlandırma ölçütü gerekir"
        )

    leaks = leak_findings(text)
    checks["no_leak"] = not leaks
    findings.extend(leaks)

    checks["has_script"] = (target / "scripts" / f"{slug}.py").is_file()
    checks["has_test"] = (target / "tests" / f"test_{slug}.py").is_file()
    if not checks["has_script"]:
        findings.append("betik iskeleti yok")
    if not checks["has_test"]:
        findings.append("test iskeleti yok")

    state = load_state(slug, vault_path) or {"name": slug, "created": _now()}
    if state.get("status") not in (STATUS_REJECTED, STATUS_APPROVED):
        state["status"] = STATUS_VALIDATED if all(checks.values()) else STATUS_DRAFT
    state["checks"] = checks
    state["findings"] = findings
    save_state(slug, state, vault_path)
    return {
        "name": slug,
        "dir": str(target),
        "status": state.get("status"),
        "checks": checks,
        "findings": findings,
    }


# ---------------------------------------------------------------------------
# 6. onay / ret / listeleme
# ---------------------------------------------------------------------------


def list_candidates(vault_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Onay paneli için aday listesi (en son güncellenen önce)."""
    root = candidates_root(vault_path)
    out: List[Dict[str, Any]] = []
    if not root.is_dir():
        return out
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        state = load_state(child.name, vault_path)
        out.append({
            "name": child.name,
            "dir": str(child),
            "skill": state.get("skill", ""),
            "status": state.get("status") or STATUS_DRAFT,
            "checks": state.get("checks") or {},
            "findings": state.get("findings") or [],
            "turns": int(state.get("turns") or 0),
            "updated": state.get("updated") or "",
            "promoted_path": state.get("promoted_path") or "",
        })
    out.sort(key=lambda r: r.get("updated") or "", reverse=True)
    return out


def promote_skill(
    name: str,
    vault_path: Optional[Path] = None,
    target_root: Optional[Path] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Adayı çalışma anı keşif köküne kopyalar (**insan onayı**).

    Hedef `<kasa>/Skills/<ad>/`; `target_root` verilirse oraya. Doğrulamadan
    geçmemiş aday `force=True` olmadan yükseltilmez — onaysız etkinleşmez
    kuralının kod karşılığı budur.
    """
    slug = slugify(name)
    src = candidate_dir(slug, vault_path)
    if not (src / "SKILL.md").is_file():
        return {"name": slug, "ok": False, "reason": "aday bulunamadı"}
    state = load_state(slug, vault_path)
    if state.get("status") == STATUS_REJECTED and not force:
        return {"name": slug, "ok": False, "reason": "aday reddedilmiş"}
    if state.get("status") != STATUS_VALIDATED and not force:
        check = validate_candidate(slug, vault_path=vault_path)
        if check["status"] != STATUS_VALIDATED:
            return {
                "name": slug, "ok": False,
                "reason": "doğrulamadan geçmedi",
                "findings": check["findings"],
            }
        state = load_state(slug, vault_path)
    dst = Path(target_root) / slug if target_root else promoted_root(vault_path) / slug
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(CANDIDATE_STATE_FILENAME))
    state.update({"status": STATUS_APPROVED, "promoted_path": str(dst)})
    save_state(slug, state, vault_path)
    return {"name": slug, "ok": True, "path": str(dst), "status": STATUS_APPROVED}


def reject_skill(name: str, reason: str = "", vault_path: Optional[Path] = None) -> Dict[str, Any]:
    """Adayı reddeder. **Dosya silinmez**: kullanıcı düzeltip yeniden sunabilir."""
    slug = slugify(name)
    if not (candidate_dir(slug, vault_path) / "SKILL.md").is_file():
        return {"name": slug, "ok": False, "reason": "aday bulunamadı"}
    state = load_state(slug, vault_path)
    state.update({"status": STATUS_REJECTED, "reject_reason": reason})
    save_state(slug, state, vault_path)
    return {"name": slug, "ok": True, "status": STATUS_REJECTED, "reason": reason}


__all__ = [
    "CANDIDATES_SUBDIR", "MIN_RECURRENCE", "PROMOTED_SUBDIR", "REQUIRED_SECTIONS",
    "SCHEMA_VERSION", "STATUS_APPROVED", "STATUS_DRAFT", "STATUS_REJECTED",
    "STATUS_VALIDATED", "build_synthesis_prompt", "candidate_dir",
    "candidate_state_path", "candidates_root", "leak_findings", "list_candidates",
    "load_state", "parse_enriched_body", "promote_skill", "promoted_root",
    "recurring_signals", "reject_skill", "render_skill_md", "save_state",
    "slugify", "synthesize_skill", "validate_candidate",
]
