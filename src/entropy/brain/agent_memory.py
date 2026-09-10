"""
Ajan başına kalıcı bellek: `<kasa>/Entropy/Agents/<ajan>/MEMORY.md`.
Ofis başına kalıcı bellek: `<kasa>/Desk/Offices/<ofis>/MEMORY.md` (aynı motor,
`append_office_memory` / `load_office_memory`).

Neyi çözüyor
------------
Bir alt ajan (researcher, code-architect, distiller…) her görevde sıfırdan
başlıyor: geçen sefer neyi denediği, neyin işe yaramadığı bir sonraki turda
kayıp. Playbook "bu iş nasıl yapılır"ı tutar (yetenek başına, damıtılmış);
burası "bu ajan ne yaptı ve ne öğrendi"yi tutar (ajan başına, olay kaydı).

Neden LLM'siz
-------------
Konsolidasyon AGY/model kotası harcamaz: tekrar eden görev başlıkları ve
ölçütler sayılır, en eski girdiler "Arşiv" bölümüne katlanır. Böylece dosya
büyümesi sınırlıdır (hedef ≤ 6000 karakter, MEMORY_MAX_CHARS) ve her turda ücretsizdir.

Dosya kasadadır çünkü kullanıcının okuyup elle düzeltebilmesi gerekir. Elle
yazılan satırlar korunur: otomatik özet yalnızca kendi işaretli bloğunu
(`<!-- auto:ozet -->`) değiştirir — "çapalı artımlı" özet budur.
"""

from __future__ import annotations

import datetime
import logging
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from entropy.core import paths as _paths
from entropy.core.config import config

logger = logging.getLogger(__name__)

# MEMORY.md hedef tavanı. Bağlam kurucuya yalnızca 300 token giriyor; dosyanın
# kendisi de sınırsız büyürse okunamaz hâle gelir ve konsolidasyon anlamsızlaşır.
MEMORY_MAX_CHARS = 6000
# Kaç kayıtta bir konsolidasyon çalışır.
CONSOLIDATE_EVERY = 10
# Konsolidasyondan sonra günlükte kalan en yeni kayıt sayısı.
JOURNAL_KEEP = CONSOLIDATE_EVERY
# Arşivde tutulacak en fazla satır (en yeniler).
ARCHIVE_KEEP = 30
# Öğrenilenler bölümünde tutulacak en fazla (otomatik özet dışı) satır.
LEARNED_KEEP = 15

JOURNAL_TITLE = "Görev günlüğü"
LEARNED_TITLE = "Öğrenilenler"
ARCHIVE_TITLE = "Arşiv"

AUTO_MARKER = "<!-- auto:ozet -->"
AUTO_END = "<!-- /auto:ozet -->"

_MEASURE_RE = re.compile(
    r"\d[\d.,]*\s*(?:token|tokens?|karakter|char|ms|sn|saniye|dakika|dk|%|kb|mb|gb|"
    r"rapor|dosya|satır|satir|tur|kez|test)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------- yollar


def _safe(name: str) -> str:
    cleaned = "".join(c if c.isalnum() or c in " -_" else "_" for c in (name or "")).strip()
    return cleaned or "agent"


def agent_dir(agent: str, vault_path: Optional[Path] = None) -> Path:
    root = Path(vault_path) if vault_path else Path(config.obsidian_vault_path)
    return root / "Entropy" / "Agents" / _safe(agent)


def memory_path(agent: str, vault_path: Optional[Path] = None) -> Path:
    return agent_dir(agent, vault_path) / "MEMORY.md"


# Ofis belleği ajan belleğiyle AYNI deseni kullanır (günlük + öğrenilenler +
# arşiv, LLM'siz konsolidasyon, 6000 karakter tavanı); yalnızca sahibi bir ajan
# değil bir ofistir. Ayrı bir modül açmak yerine aynı motoru "sahip türü"
# (owner kind) ile parametreleştiriyoruz: iki kopya bakım borcu olurdu.
_OWNER_KINDS = {
    "agent": {"base": "Agents", "label": "Ajan Belleği", "fm_key": "agent", "fallback": "agent", "root": "Entropy"},
    # Faz 6: Desk ayrıldı; Faz 10-B: veri kökü kasa köküne çıktı. Ofis belleği
    # de Desk'in kendi kökünde yaşar (tek kaynak `core.paths.DESK_SUBDIR`);
    # `root` bu yüzden `Entropy/` değil, kasa kökünün kendisidir.
    "office": {"base": _paths.DESK_SUBDIR, "label": "Ofis Belleği", "fm_key": "office", "fallback": "office", "root": ""},
}


def _owner_dir(name: str, kind: str, vault_path: Optional[Path] = None) -> Path:
    root = Path(vault_path) if vault_path else Path(config.obsidian_vault_path)
    spec = _OWNER_KINDS[kind]
    cleaned = _safe(name)
    if cleaned == "agent" and spec["fallback"] != "agent":
        cleaned = spec["fallback"]
    base = root / spec["root"] if spec.get("root") else root
    return base / spec["base"] / cleaned


def office_dir(office: str, vault_path: Optional[Path] = None) -> Path:
    return _owner_dir(office, "office", vault_path)


def office_memory_path(office: str, vault_path: Optional[Path] = None) -> Path:
    return office_dir(office, vault_path) / "MEMORY.md"


def _memory_path(name: str, kind: str, vault_path: Optional[Path] = None) -> Path:
    if kind == "agent":
        return memory_path(name, vault_path)
    return office_memory_path(name, vault_path)


# ------------------------------------------------------- ayrıştır / kur


def _split_sections(text: str) -> Tuple[str, Dict[str, List[str]], List[str]]:
    """
    Metni (ön bilgi + başlık, bölüm -> satırlar, bölüm sırası) olarak ayırır.

    Bilinmeyen bölümler korunur: kullanıcı kendi başlığını eklerse silinmemeli.
    """
    head_lines: List[str] = []
    sections: Dict[str, List[str]] = {}
    order: List[str] = []
    current: Optional[str] = None
    for line in (text or "").splitlines():
        m = re.match(r"^##\s+(.*?)\s*$", line)
        if m:
            current = m.group(1)
            if current not in sections:
                sections[current] = []
                order.append(current)
            continue
        if current is None:
            head_lines.append(line)
        else:
            sections[current].append(line)
    return "\n".join(head_lines).rstrip(), sections, order


def _render(
    agent: str,
    head: str,
    sections: Dict[str, List[str]],
    order: List[str],
    count: int,
    kind: str = "agent",
) -> str:
    spec = _OWNER_KINDS[kind]
    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    fm = (
        "---\n"
        f"{spec['fm_key']}: {agent}\n"
        f"entries: {count}\n"
        f"updated: {stamp}\n"
        "---\n\n"
        f"# {agent} — {spec['label']}\n"
    )
    body: List[str] = [fm.rstrip("\n"), ""]
    for title in order:
        lines = [ln for ln in sections.get(title, [])]
        while lines and not lines[-1].strip():
            lines.pop()
        while lines and not lines[0].strip():
            lines.pop(0)
        body += [f"## {title}", ""] + lines + [""]
    return "\n".join(body).rstrip() + "\n"


def _read(
    agent: str, vault_path: Optional[Path] = None, kind: str = "agent"
) -> Tuple[str, Dict[str, List[str]], List[str], int]:
    path = _memory_path(agent, kind, vault_path)
    if not path.is_file():
        sections = {JOURNAL_TITLE: [], LEARNED_TITLE: []}
        return "", sections, [JOURNAL_TITLE, LEARNED_TITLE], 0
    text = path.read_text(encoding="utf-8", errors="ignore")
    head, sections, order = _split_sections(text)
    m = re.search(r"(?m)^entries:\s*(\d+)\s*$", text)
    count = int(m.group(1)) if m else len([l for l in sections.get(JOURNAL_TITLE, []) if l.strip().startswith("-")])
    for t in (JOURNAL_TITLE, LEARNED_TITLE):
        if t not in sections:
            sections[t] = []
            order.append(t)
    return head, sections, order, count


def _wikilink(value: Any) -> str:
    s = str(value or "").strip()
    if not s:
        return ""
    if s.startswith("[["):
        return s
    stem = Path(s).stem if ("/" in s or "\\" in s or s.lower().endswith(".md")) else s
    return f"[[{stem}]]"


def _entry_line(entry: Dict[str, Any]) -> str:
    date = str(entry.get("date") or datetime.date.today().isoformat())[:10]
    title = re.sub(r"\s+", " ", str(entry.get("title") or entry.get("task") or "görev")).strip()[:120]
    result = re.sub(r"\s+", " ", str(entry.get("result") or entry.get("outcome") or "")).strip()[:160]
    output = entry.get("output_path") or entry.get("output") or ""
    if not output:
        paths = entry.get("output_paths") or []
        output = paths[0] if paths else ""
    parts = [f"- [{date}] {title}"]
    if result:
        parts.append(f"sonuç: {result}")
    # Ofis kayıtlarında not ve alt kart sayısı ölçüttür: "iddia etme, ölç"
    # kuralı gereği özet bunları sayabilsin diye satıra yazılır.
    grade = entry.get("grade")
    if grade is not None and str(grade).strip() != "":
        try:
            parts.append(f"not: {float(grade):.2f}")
        except (TypeError, ValueError):
            parts.append(f"not: {str(grade).strip()[:20]}")
    children = entry.get("children_count")
    if children is not None and str(children).strip() != "":
        try:
            parts.append(f"{int(children)} alt kart")
        except (TypeError, ValueError):
            pass
    link = _wikilink(output)
    if link:
        parts.append(link)
    return " — ".join(parts)


# ------------------------------------------------------------- API


def append_agent_memory(agent: str, entry: dict) -> Path:
    """
    Ajanın MEMORY.md'sine bir görev kaydı ekler ve dosya yolunu döndürür.

    `entry` anahtarları: title/task, result/outcome, output_path(s), date,
    learning(s) (Öğrenilenler'e eklenecek satır(lar)), vault_path.
    Her CONSOLIDATE_EVERY kayıtta konsolidasyon çalışır.
    """
    return _append_memory(agent, entry, kind="agent")


def append_office_memory(office: str, entry: dict) -> Path:
    """
    Ofisin MEMORY.md'sine bir kart kaydı ekler ve dosya yolunu döndürür.

    `entry` anahtarları: title, result, grade (0–1), children_count,
    output_paths, learnings/learning, date, vault_path. Ajan belleğiyle aynı
    motor: 10 kayıtta LLM'siz konsolidasyon, ≤ MEMORY_MAX_CHARS.
    """
    return _append_memory(office, entry, kind="office")


def _append_memory(agent: str, entry: dict, kind: str = "agent") -> Path:
    entry = dict(entry or {})
    vault_path = entry.get("vault_path")
    head, sections, order, count = _read(agent, vault_path, kind)

    journal = sections[JOURNAL_TITLE]
    while journal and not journal[-1].strip():
        journal.pop()
    journal.append(_entry_line(entry))

    learnings = entry.get("learnings") or ([entry["learning"]] if entry.get("learning") else [])
    existing = {l.strip().lower() for l in sections[LEARNED_TITLE]}
    for l in learnings:
        line = "- " + re.sub(r"\s+", " ", str(l)).strip()[:200]
        if line.strip().lower() in existing or line.strip() == "-":
            continue
        existing.add(line.strip().lower())
        # Otomatik özet bloğu her zaman en altta kalır: elle/kayıttan gelen
        # satırlar onun üstüne eklenir, yoksa özet metnin ortasına gömülürdü.
        if AUTO_MARKER in sections[LEARNED_TITLE]:
            sections[LEARNED_TITLE].insert(sections[LEARNED_TITLE].index(AUTO_MARKER), line)
        else:
            sections[LEARNED_TITLE].append(line)

    count += 1
    path = _memory_path(agent, kind, vault_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_render(agent, head, sections, order, count, kind), encoding="utf-8")

    if count % CONSOLIDATE_EVERY == 0:
        try:
            _consolidate_memory(agent, vault_path=vault_path, kind=kind)
        except Exception as exc:  # pragma: no cover - konsolidasyon kaydı düşürmemeli
            logger.warning("Bellek konsolide edilemedi (%s/%s): %s", kind, agent, exc)
    return path


def _auto_summary(journal: List[str]) -> List[str]:
    """LLM'siz özet: tekrar eden başlıklar ve geçen ölçütler sayılır."""
    titles = Counter()
    measures = Counter()
    results = Counter()
    for line in journal:
        if not line.strip().startswith("-"):
            continue
        body = re.sub(r"^-\s*\[[^\]]*\]\s*", "", line.strip())
        pieces = [p.strip() for p in body.split(" — ")]
        if pieces:
            titles[pieces[0][:80].lower()] += 1
        for p in pieces[1:]:
            if p.lower().startswith("sonuç:"):
                results[p.split(":", 1)[1].strip()[:60].lower()] += 1
        for m in _MEASURE_RE.findall(body):
            measures[m.strip().lower()] += 1

    out: List[str] = []
    repeated = [(t, c) for t, c in titles.most_common(5) if c > 1]
    if repeated:
        out.append("- Tekrar eden görevler: " + ", ".join(f"{t} ×{c}" for t, c in repeated))
    if results:
        out.append("- Sonuç dağılımı: " + ", ".join(f"{r} ×{c}" for r, c in results.most_common(3)))
    if measures:
        out.append("- Sık geçen ölçütler: " + ", ".join(f"{m} ×{c}" for m, c in measures.most_common(3)))
    out.append(f"- Toplam kayıt (bu özetin kapsadığı): {sum(titles.values())}")
    return out


def _replace_auto_block(lines: List[str], summary: List[str]) -> List[str]:
    """Elle yazılan satırlara dokunmadan otomatik özet bloğunu değiştirir."""
    block = [AUTO_MARKER] + summary + [AUTO_END]
    try:
        start = lines.index(AUTO_MARKER)
        end = lines.index(AUTO_END)
        return lines[:start] + block + lines[end + 1 :]
    except ValueError:
        return [l for l in lines if l.strip()] + block


def consolidate_agent_memory(agent: str, vault_path: Optional[Path] = None) -> Path:
    """
    Günlüğü küçültür, özeti tazeler, taşanı Arşiv'e katlar (model çağrısı yok).

    Sonuç dosyası MEMORY_MAX_CHARS'ı aşarsa önce arşiv, sonra günlük satırları
    en eskiden başlayarak düşürülür: tavan bir hedef değil, garantidir.
    """
    return _consolidate_memory(agent, vault_path=vault_path, kind="agent")


def consolidate_office_memory(office: str, vault_path: Optional[Path] = None) -> Path:
    """Ofis belleğinin konsolidasyonu (ajan belleğiyle aynı kural, model çağrısı yok)."""
    return _consolidate_memory(office, vault_path=vault_path, kind="office")


def _consolidate_memory(agent: str, vault_path: Optional[Path] = None, kind: str = "agent") -> Path:
    head, sections, order, count = _read(agent, vault_path, kind)
    journal = [l for l in sections.get(JOURNAL_TITLE, []) if l.strip().startswith("-")]

    summary = _auto_summary(journal)
    learned = sections.get(LEARNED_TITLE, [])
    # Öğrenilenler de sınırsız büyümemeli: otomatik blok dışındaki satırlardan
    # yalnızca en yeni LEARNED_KEEP tanesi kalır.
    try:
        auto_start = learned.index(AUTO_MARKER)
        auto_end = learned.index(AUTO_END)
        manual = learned[:auto_start] + learned[auto_end + 1 :]
    except ValueError:
        manual = list(learned)
    manual = [l for l in manual if l.strip()][-LEARNED_KEEP:]
    sections[LEARNED_TITLE] = _replace_auto_block(manual, summary)

    keep = journal[-JOURNAL_KEEP:] if len(journal) > JOURNAL_KEEP else journal
    folded = journal[: len(journal) - len(keep)]
    if folded:
        if ARCHIVE_TITLE not in sections:
            sections[ARCHIVE_TITLE] = []
            order.append(ARCHIVE_TITLE)
        archive = [l for l in sections[ARCHIVE_TITLE] if l.strip().startswith("-")]
        archive.extend(folded)
        sections[ARCHIVE_TITLE] = archive[-ARCHIVE_KEEP:]
    sections[JOURNAL_TITLE] = keep

    path = _memory_path(agent, kind, vault_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = _render(agent, head, sections, order, count, kind)

    # Tavanı aşarsa: önce arşiv en eskiden kırpılır, yetmezse günlük.
    while len(text) > MEMORY_MAX_CHARS and sections.get(ARCHIVE_TITLE):
        sections[ARCHIVE_TITLE] = sections[ARCHIVE_TITLE][1:]
        text = _render(agent, head, sections, order, count, kind)
    while len(text) > MEMORY_MAX_CHARS and len(sections.get(JOURNAL_TITLE, [])) > 1:
        sections[JOURNAL_TITLE] = sections[JOURNAL_TITLE][1:]
        text = _render(agent, head, sections, order, count, kind)
    if len(text) > MEMORY_MAX_CHARS:
        text = text[: MEMORY_MAX_CHARS - 1].rstrip() + "…\n"

    path.write_text(text, encoding="utf-8")
    return path


def load_agent_memory(agent: str, budget_tokens: int = 300, vault_path: Optional[Path] = None) -> str:
    """
    Bağlam kurucu için ajan belleğinin bütçeye sığan özeti.

    Öncelik: Öğrenilenler (tekrar edilebilir bilgi) > günlüğün en yeni satırları
    (ne yapıldı). Arşiv hiç girmez: en eski ve en az ilgili kısımdır.
    """
    return _load_memory(agent, budget_tokens=budget_tokens, vault_path=vault_path, kind="agent")


def load_office_memory(office: str, budget_tokens: int = 300, vault_path: Optional[Path] = None) -> str:
    """Bağlam kurucu için ofis belleğinin bütçeye sığan özeti (varsayılan 300 token)."""
    return _load_memory(office, budget_tokens=budget_tokens, vault_path=vault_path, kind="office")


def _load_memory(
    agent: str, budget_tokens: int = 300, vault_path: Optional[Path] = None, kind: str = "agent"
) -> str:
    if budget_tokens <= 0:
        return ""
    _head, sections, _order, _count = _read(agent, vault_path, kind)
    learned = [l for l in sections.get(LEARNED_TITLE, []) if l.strip() and not l.strip().startswith("<!--")]
    journal = [l for l in sections.get(JOURNAL_TITLE, []) if l.strip().startswith("-")]

    budget_chars = budget_tokens * 4
    parts: List[str] = []
    used = 0
    if learned:
        parts.append(f"{LEARNED_TITLE}:")
        used += len(LEARNED_TITLE) + 2
    for line in learned:
        if used + len(line) + 1 > budget_chars:
            break
        parts.append(line)
        used += len(line) + 1
    recent = list(reversed(journal[-5:]))
    if recent and used + 20 < budget_chars:
        parts.append(f"{JOURNAL_TITLE} (son):")
        used += len(JOURNAL_TITLE) + 8
        for line in recent:
            if used + len(line) + 1 > budget_chars:
                break
            parts.append(line)
            used += len(line) + 1
    return "\n".join(parts).strip()
