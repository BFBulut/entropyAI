"""
Ajan derleyici: kasadaki AGENT.md'yi sağlayıcıların beklediği biçimlere çevirir.

İki CLI de ajanlarını "sürecin çalışma dizinine göre" keşfeder ve biçimleri
birbirini tutmaz:

    agy    -> <kök>/.agents/agents/<ad>/agent.md
              ön bilgi: name, description, model, subagent, mainAgent,
              inheritCustomizations, rules
    claude -> <kök>/.claude/agents/<ad>.md
              ön bilgi: name, description, model, effort, tools

Bu yüzden kaynak tanımı (kasa) türetilmiş tanımlardan ayrı tutulur: kullanıcı
tek dosya düzenler, derleme iki biçimi de üretir. Çıktı İKİ köke yazılır —
uygulama kökü (Entropy'nin kendi süreci oradan koşar) ve etkin proje kökü
(arka plan görevleri proje dizininde koşar). Yalnızca birine yazmak, ajanın
görevlerin yarısında "bulunamadı" olmasına yol açıyordu.

Kaynak değişmemişse dosyaya dokunulmaz: her açılışta ve her proje değişiminde
derleme koşuyor; içerik aynıyken yazmak dosya izleyicileri (SkillWatcher,
AgentsWatcher, agy'nin kendi keşfi) için sonsuz bir olay döngüsü üretirdi.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional

from entropy.agents.registry import AgentSpec, render_frontmatter

# agy ön bilgisi model adını kısa etiketle bekliyor (bkz. .agents/agents/distiller).
_AGY_MODEL_HINTS = (("flash", "flash"), ("pro", "pro"), ("gpt", "gpt"))
_CLAUDE_MODEL_HINTS = (("opus", "opus"), ("sonnet", "sonnet"), ("haiku", "haiku"))

# tools_policy -> Claude `tools` listesi. Politika adı sağlayıcıdan bağımsız
# tutulur ki kasa dosyası tek biçim konuşsun; eşleme burada yapılır.
_TOOLS_BY_POLICY = {
    "read-only": "Read, Glob, Grep, WebFetch, WebSearch",
    "read-write": "Read, Glob, Grep, Edit, Write, Bash",
    "full": "Read, Glob, Grep, Edit, Write, Bash, WebFetch, WebSearch",
    "no-tools": "",
}


def _short_model(model: str, hints: Iterable[tuple]) -> str:
    low = (model or "").lower()
    for needle, label in hints:
        if needle in low:
            return label
    return model or ""


def _write_if_changed(path: Path, content: str) -> Path:
    """İçerik farklıysa yazar; aynıysa dosyaya dokunmaz (mtime korunur)."""
    try:
        if path.is_file() and path.read_text(encoding="utf-8") == content:
            return path
    except OSError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def render_agy_agent(spec: AgentSpec) -> str:
    """agy `agent.md` içeriği."""
    front = {
        "name": spec.name,
        "description": " ".join((spec.description or spec.role or spec.name).split()),
        "subagent": True,
        "mainAgent": True,
        "inheritCustomizations": False,
    }
    model = _short_model(spec.model, _AGY_MODEL_HINTS)
    if model:
        front["model"] = model
    rules = _rules_lines(spec)
    if rules:
        front["rules"] = rules
    body = (spec.prompt or "").strip()
    if not body.startswith("#"):
        body = f"# {spec.name}\n\n{body}".strip()
    return f"{render_frontmatter(front)}\n\n{body}\n"


def render_claude_agent(spec: AgentSpec) -> str:
    """Claude `.claude/agents/<ad>.md` içeriği."""
    front = {
        "name": spec.name,
        "description": " ".join((spec.description or spec.role or spec.name).split()),
    }
    model = _short_model(spec.model, _CLAUDE_MODEL_HINTS)
    if model:
        front["model"] = model
    if spec.effort:
        front["effort"] = spec.effort
    tools = _TOOLS_BY_POLICY.get((spec.tools_policy or "").lower())
    if tools:
        front["tools"] = tools
    body = (spec.prompt or "").strip()
    rules = _rules_lines(spec)
    if rules:
        # Claude ön bilgisinde `rules` alanı yok; kurallar gövdeye eklenir.
        body = body + "\n\n## Kurallar\n" + "\n".join(f"- {r}" for r in rules)
    return f"{render_frontmatter(front)}\n\n{body.strip()}\n"


def _rules_lines(spec: AgentSpec) -> List[str]:
    """Ön bilgi alanlarından türeyen, gövdede tekrarlanmayan kısa kurallar."""
    rules: List[str] = []
    if spec.skills:
        rules.append("Şu yetenekleri kullan: " + ", ".join(spec.skills))
    policy = (spec.tools_policy or "").lower()
    if policy == "read-only":
        rules.append("Dosya değiştirme; yalnızca oku ve rapor et.")
    elif policy == "no-tools":
        rules.append("Hiçbir araç kullanma; tek yanıtta metin üret.")
    if spec.memory_path:
        rules.append(f"Kalıcı notların: {spec.memory_path}")
    return rules


def compile_roots(project_dir: Optional[Path | str] = None) -> List[Path]:
    """
    Derlemenin yazılacağı kökler: uygulama kökü + istenen proje kökü + etkin proje.

    Aynı yol iki kez dönmez; proje kökü uygulama kökünün kendisiyse tek yazım olur.
    Paketlenmiş sürümde APP_ROOT .exe'nin klasörü (ör. `dist/EntropyAI`) olduğu
    için yalnızca ona yazmak, ajanların gerçekte çalışılan proje kökünde
    "bulunamadı" olmasına yol açıyordu; bu yüzden `default_project_path` de
    `project_dir` verilse bile listeye eklenir (erken çıkış yok).
    """
    from entropy.core.config import APP_ROOT, config

    roots: List[Path] = []

    def _add(candidate) -> None:
        if not candidate:
            return
        try:
            p = Path(candidate).resolve()
        except Exception:
            return
        if p not in roots and p.is_dir():
            roots.append(p)

    _add(APP_ROOT)
    _add(project_dir)
    _add(getattr(config, "default_project_path", None))
    return roots


def compile_agent(spec: AgentSpec, project_dir: Optional[Path | str] = None) -> Dict[str, Path]:
    """
    Bir ajanı iki sağlayıcı biçimine derler.

    Dönüş: {"agy": <yol>, "claude": <yol>} — ilk (uygulama) kökündeki yollar.
    Diğer köklere de yazılır ama sözleşme tek yol döndürmeyi gerektirdiği için
    çağıranlar uygulama kökündeki dosyayı görür.
    """
    agy_text = render_agy_agent(spec)
    claude_text = render_claude_agent(spec)
    out: Dict[str, Path] = {}
    for root in compile_roots(project_dir):
        agy_path = _write_if_changed(root / ".agents" / "agents" / spec.name / "agent.md", agy_text)
        claude_path = _write_if_changed(root / ".claude" / "agents" / f"{spec.name}.md", claude_text)
        if not out:
            out = {"agy": agy_path, "claude": claude_path}
    return out
