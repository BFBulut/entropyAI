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

# Yabancı model adının işareti: bir sağlayıcının derlemesine diğerinin model adı
# sızarsa CLI 404 veriyor (Claude Code, `gemini-3.8-flash-high` için). Kaynak
# tanımında tek bir `model` alanı olduğu için bu sızıntı sessizce oluyordu.
_GEMINI_MARKERS = ("gemini", "flash", "pro", "gpt")
_CLAUDE_MARKERS = ("claude", "opus", "sonnet", "haiku")

# Yabancı ad görülünce kullanılacak karşılıklar.
CLAUDE_FALLBACK_MODEL = "inherit"          # Claude derlemesi: oturumun modelini miras al
AGY_FALLBACK_MODEL = "gemini-3.8-flash-high"  # agy derlemesi: güvenli varsayılan


def resolve_model(spec: AgentSpec, provider: str) -> str:
    """
    Bir ajanın verilen sağlayıcıda kullanacağı ham model adı.

    Sıra: (1) `models.<sağlayıcı>` açık geçersiz kılma, (2) `model` alanı o
    sağlayıcıya aitse doğrudan, (3) yabancı adsa sağlayıcının karşılığı.
    """
    provider = (provider or "").strip().lower()
    explicit = spec.model_for(provider)
    if explicit:
        return explicit
    model = (spec.model or "").strip()
    low = model.lower()
    if provider == "claude":
        if any(m in low for m in _CLAUDE_MARKERS):
            return model
        if any(m in low for m in _GEMINI_MARKERS):
            return CLAUDE_FALLBACK_MODEL
        return model
    if provider == "agy":
        if any(m in low for m in _CLAUDE_MARKERS):
            return AGY_FALLBACK_MODEL
        return model
    return model

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
    model = _short_model(resolve_model(spec, "agy"), _AGY_MODEL_HINTS)
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
    model = _short_model(resolve_model(spec, "claude"), _CLAUDE_MODEL_HINTS)
    if model:
        front["model"] = model
    if spec.effort:
        front["effort"] = spec.effort
    # Orkestratörde politika alanı ne yazarsa yazsın araç listesi salt-okunur:
    # yazma/komut aracı ofis sözleşmesinde alt ajanlara ait.
    policy = "read-only" if is_orchestrator(spec) else (spec.tools_policy or "").lower()
    tools = _TOOLS_BY_POLICY.get(policy)
    if tools:
        front["tools"] = tools
    body = (spec.prompt or "").strip()
    rules = _rules_lines(spec)
    if rules:
        # Claude ön bilgisinde `rules` alanı yok; kurallar gövdeye eklenir.
        body = body + "\n\n## Kurallar\n" + "\n".join(f"- {r}" for r in rules)
    return f"{render_frontmatter(front)}\n\n{body.strip()}\n"


# Orkestratör derlemesine düşen sert yasaklar. agy'nin ön bilgi şemasında araç
# listesi alanı yok (`tools` yalnızca Claude tarafında); bu yüzden yasak agy
# tarafında `rules` satırları, Claude tarafında hem `tools` listesi hem de
# gövdedeki kural bloğu olarak iki kez ifade edilir. Tek yerde kalsaydı
# sağlayıcılardan birinde orkestratör dosya yazabiliyordu.
# Satırlarda VİRGÜL ve ": " yok: `render_frontmatter` listeyi YAML akış dizisi
# (`[a, b]`) olarak yazıyor ve virgül içeren bir kural üç ayrı kurala bölünüyor,
# iki nokta içeren kural ise eşleme sanılıyordu — yani yasak sessizce bozuluyordu.
ORCHESTRATOR_RULES = (
    "Kod yazmak ve dosya oluşturmak/değiştirmek yasak; yalnızca oku ve araştır.",
    "Kabuk komutu ya da betik çalıştırmak yasak.",
    "İşi kendin yapma; alt görevlere böl ve alt ajanlara ata.",
)


def is_orchestrator(spec: AgentSpec) -> bool:
    """Ajan bir ofisin orkestratörü mü (rol alanına göre)."""
    return spec.office_role == "orchestrator"


def _rules_lines(spec: AgentSpec) -> List[str]:
    """Ön bilgi alanlarından türeyen, gövdede tekrarlanmayan kısa kurallar."""
    rules: List[str] = []
    if spec.skills:
        rules.append("Şu yetenekleri kullan: " + ", ".join(spec.skills))
    if is_orchestrator(spec):
        rules.extend(ORCHESTRATOR_RULES)
        if spec.memory_path:
            # "->" kasıtlı: iki nokta akış dizisinde eşleme başlatıyor.
            rules.append(f"Kalıcı notların -> {spec.memory_path}")
        return rules
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


def compile_agent_to(spec: AgentSpec, root: Path | str) -> Dict[str, Path]:
    """
    Bir ajanı TEK bir köke derler (Desk ofisleri için).

    `compile_agent`ten ayrı: Entropy'nin kendi ajanları uygulama kökü + etkin
    proje köküne yazılır, Desk ajanları ise yalnızca kendi ofislerinin çalışma
    dizinine. Ofis ajanının uygulama köküne sızması, Entropy'nin kendi
    çağrılarında "Entropy" bilmeyen bir ajanın seçilebilmesi demekti.
    """
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    return {
        "agy": _write_if_changed(
            root / ".agents" / "agents" / spec.name / "agent.md", render_agy_agent(spec)
        ),
        "claude": _write_if_changed(
            root / ".claude" / "agents" / f"{spec.name}.md", render_claude_agent(spec)
        ),
    }


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
