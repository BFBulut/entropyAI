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
tek dosya düzenler, derleme iki biçimi de üretir. **Kökler biçime göre ayrıdır
(Faz 11-C):** agy biçimi etkin proje kökü + nötr çalışma alanına yazılır (agy
ajanı yalnızca sürecin çalışma dizininden keşfediyor), claude biçimi ise
YALNIZCA nötr çalışma alanına (`claude_compile_root`) — proje kökündeki
`.claude/agents` kullanıcının kendi Claude Code oturumuna sızıyordu ve saf kip
o dosyaları zaten okumuyor (kadro `--agents <json>` ile taşınır).

Kaynak değişmemişse dosyaya dokunulmaz: her açılışta ve her proje değişiminde
derleme koşuyor; içerik aynıyken yazmak dosya izleyicileri (SkillWatcher,
AgentsWatcher, agy'nin kendi keşfi) için sonsuz bir olay döngüsü üretirdi.
"""

from __future__ import annotations

import re
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


# Serbest metin model adları (kullanıcı OFFICE.md'ye "fable 5.1 high effort"
# yazıyor) sağlayıcıya verilebilir bir kimliğe çevrilir. Sıra ÖNEMLİ: "fable"
# önce bakılır, aksi hâlde "claude-fable-5-1" içindeki başka bir ipucu kazanır.
_CLAUDE_TEXT_RULES = (
    ("fable", "fable"),
    ("opus", "claude-opus-5"),
    ("sonnet", "claude-sonnet-5"),
    ("haiku", "claude-haiku-4-5-20251001"),
)
_AGY_TEXT_RULES = (
    ("flash", "gemini-3.8-flash-high"),
    ("pro", "gemini-3.1-pro-high"),
    ("gemini", "gemini-3.8-flash-high"),
)

# Efor sözcükleri; metinde tek başına geçen ilki alınır.
_EFFORT_WORDS = ("low", "medium", "high", "xhigh", "max")

# Tam kimliğe açılacak çıplak takma adlar ("fable" hariç: onun tam karşılığı
# zaten takma adın kendisi).
_BARE_ALIASES = ("opus", "sonnet", "haiku")


def normalize_model_text(text: str, provider: str) -> tuple:
    """
    Serbest metin model tanımını `(model, effort|None)` ikilisine çevirir.

    Neden: ofis `default_model` alanını kullanıcı elle yazıyor ("fable 5.1 high
    effort") ve bu dizge doğrudan `--model` argümanına geçince CLI
    `unrecognized_model` ile ölüyordu. Metin küçük harfe indirilip
    boşluk/nokta/tire farkları yok sayılarak sağlayıcının bildiği bir kimliğe
    eşlenir; tanınmayan metin sağlayıcının güvenli varsayılanına düşer.
    """
    provider = (provider or "").strip().lower()
    raw = (text or "").strip()
    fallback = CLAUDE_FALLBACK_MODEL if provider == "claude" else (
        AGY_FALLBACK_MODEL if provider == "agy" else "")
    if not raw:
        return ("", None)

    low = raw.lower()
    tokens = [t for t in re.split(r"[^a-z0-9]+", low) if t]
    effort = next((t for t in tokens if t in _EFFORT_WORDS), None)

    # Zaten geçerli bir TAM kimlikse dokunulmaz (yeni model adları beyaz listeye
    # eklenmeden de çalışsın diye). Çıplak takma adlar (`opus`) bunun dışında:
    # CLI onları kabul etse de kart/ofis kayıtlarında tam kimlik istiyoruz ki
    # kayıt hangi modeli koştuğunu belgelesin.
    if low not in _BARE_ALIASES:
        try:
            from entropy.core.config import is_valid_model_for

            if is_valid_model_for(provider, raw):
                return (raw, effort)
        except Exception:
            pass

    rules = _CLAUDE_TEXT_RULES if provider == "claude" else (
        _AGY_TEXT_RULES if provider == "agy" else ())
    for needle, model in rules:
        if needle in low:
            return (model, effort)
    return (fallback, effort)


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
    if not model or provider not in ("claude", "agy"):
        return model
    # Serbest metin ("fable 5.1 high effort") ve yabancı ad (gemini-* bir Claude
    # koşusunda) aynı kapıdan geçer: sağlayıcıya verilebilir bir kimlik değilse
    # normalize edilir. Eskiden yalnızca YABANCI ad yakalanıyordu; kullanıcının
    # elle yazdığı metin olduğu gibi `--model`e gidiyordu.
    try:
        from entropy.core.config import is_valid_model_for

        if is_valid_model_for(provider, model):
            return model
    except Exception:
        return model
    normalized, _ = normalize_model_text(model, provider)
    return normalized or model

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
        # NOT (Faz 11-C): izole kipte bu satır ETKİSİZDİR — `--setting-sources ""`
        # derlenmiş ajan dosyalarını okutmuyor. Silinmedi çünkü izolasyon
        # kapatılırsa (config.claude_isolated=False) yeniden işe yarar; efor
        # bugün `--effort` bayrağı ve `--agents` yüküyle taşınır.
        front["effort"] = spec.effort
    # Orkestratörde politika alanı ne yazarsa yazsın araç listesi salt-okunur:
    # yazma/komut aracı ofis sözleşmesinde alt ajanlara ait.
    policy = "read-only" if is_orchestrator(spec) else (spec.tools_policy or "").lower()
    tools = _TOOLS_BY_POLICY.get(policy)
    if tools:
        front["tools"] = tools
    return f"{render_frontmatter(front)}\n\n{_claude_body(spec)}\n"


def _claude_body(spec: AgentSpec) -> str:
    """Claude tarafındaki ajan gövdesi: istem + kural bloğu."""
    body = (spec.prompt or "").strip()
    rules = _rules_lines(spec)
    if rules:
        # Claude ön bilgisinde `rules` alanı yok; kurallar gövdeye eklenir.
        body = body + "\n\n## Kurallar\n" + "\n".join(f"- {r}" for r in rules)
    return body.strip()


def claude_tools_list(spec: AgentSpec) -> List[str]:
    """Ajanın Claude araç listesi (politika + orkestratör yasağı)."""
    policy = "read-only" if is_orchestrator(spec) else (spec.tools_policy or "").lower()
    tools = _TOOLS_BY_POLICY.get(policy, "")
    return [t.strip() for t in tools.split(",") if t.strip()]


def claude_agents_json(vault_path: Optional[Path | str] = None,
                       default_effort: str = "") -> str:
    """
    `claude --agents <json>` yükü: Entropy'nin KENDİ kadrosu.

    İzole kipte CLI kullanıcının `.claude/agents` klasörünü okumaz
    (`--setting-sources ""`), yani derlenmiş dosyalar görünmez olur; kadro o
    turda yalnızca bu bayrakla taşınabilir.

    Desk ofis ajanları ASLA girmez: kadro yalnızca `AgentRegistry.list()`ten
    gelir ve o da kasadaki `Desk` kökünü (bağlantı/junction dâhil)
    ayıklar. Bir ofis ajanının Entropy'nin turunda seçilebilmesi, "Entropy'yi
    bilmeyen" bir ajanın Entropy adına konuşması demekti. Künyedeki `office`
    alanına BAKILMAZ: Entropy'nin kendi tohum ajanları da bir ofis adı taşıyor.

    Kadro boşsa `"{}"` değil BOŞ DİZE döner: çağıranlar bayrağı hiç eklemesin.
    """
    import json

    from entropy.agents.registry import AgentRegistry

    try:
        specs = AgentRegistry(vault_path=vault_path).list()
    except Exception:
        return ""
    payload: Dict[str, dict] = {}
    for spec in specs:
        name = (spec.name or "").strip()
        if not name:
            continue
        entry = {
            "description": " ".join((spec.description or spec.role or name).split()),
            "prompt": _claude_body(spec),
            "tools": claude_tools_list(spec),
        }
        model = resolve_model(spec, "claude")
        if model:
            entry["model"] = model
        # Faz 11-C.4: efor künyeye girer. Derlenmiş `.claude/agents/<ad>.md`
        # dosyasındaki `effort` ön bilgisi izole kipte ETKİSİZDİR
        # (`--setting-sources ""` o dosyaları okutmuyor), yani eforun tek
        # taşıyıcısı bu yük ve `--effort` bayrağıdır.
        effort = (getattr(spec, "effort", "") or default_effort or "").strip().lower()
        if effort:
            entry["effort"] = effort
        payload[name] = entry
    if not payload:
        return ""
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


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
    Derlemenin yazılacağı kökler: istenen proje kökü + etkin proje + nötr çalışma dizini.

    Aynı yol iki kez dönmez.

    **APP_ROOT neden listede değil (Faz 11-A):** kaynaktan koşarken APP_ROOT
    deponun kendisidir; oraya yazmak Entropy'nin kendi kadrosunu (`analist`,
    `arastirmaci`, `degerlendirici`, `orkestrator`, `yazar`) deponun
    `.claude/agents/` ve `.agents/agents/` klasörlerine düşürüyordu. Sonuç:
    kullanıcının kendi CLI oturumunda Entropy'nin iç ajanları alt ajan olarak
    görünüyor, üretilmiş dosyalar sürüm denetimine sızıyordu. Paketlenmiş
    sürümde ise APP_ROOT .exe klasörüdür ve oraya yazmanın hiçbir faydası yok
    (ajanlar gerçek proje kökünden ve nötr çalışma dizininden keşfediliyor).
    `default_project_path`, `project_dir` verilse bile listeye eklenir
    (erken çıkış yok).
    """
    from entropy.core.config import config

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

    _add(project_dir)
    _add(getattr(config, "default_project_path", None))
    _add(claude_compile_root())
    return roots


def claude_compile_root() -> Optional[Path]:
    """
    Claude biçiminin (`.claude/agents/*.md`) yazılabileceği TEK kök: nötr çalışma alanı.

    **Neden proje kökü değil (Faz 11-C):** derlenen dosyalar kullanıcının kendi
    Claude Code oturumuna alt ajan olarak sızıyordu — depoda `.claude/agents/`
    altında Entropy'nin kadrosu (`analist`, `arastirmaci`, `degerlendirici`,
    `orkestrator`, `yazar`) yeniden beliriyor, kullanıcının geliştirme
    ajanlarıyla karışıyordu. Entropy'nin KENDİ turunda bu dosyalara zaten
    ihtiyaç yok: saf kip `--setting-sources ""` ile onları okumuyor, kadro
    `--agents <json>` yüküyle taşınıyor (`claude_agents_json`). agy tarafı
    farklı: orada ajan yalnızca sürecin çalışma dizinindeki `.agents/agents`
    ağacından keşfediliyor, o yüzden agy biçimi proje köklerine yazılmayı
    sürdürür.
    """
    try:
        from entropy.core.config import claude_workspace_path

        path = Path(claude_workspace_path())
        path.mkdir(parents=True, exist_ok=True)
        return path.resolve()
    except Exception:
        return None


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

    Dönüş: {"agy": <yol>, "claude": <yol>} — ilk kökteki agy yolu ve nötr
    çalışma alanındaki claude yolu.

    **Biçimlerin kökleri AYRI (Faz 11-C):** agy her köke (`compile_roots`)
    yazılır çünkü ajanı yalnızca sürecin çalışma dizininden keşfediyor; claude
    biçimi YALNIZCA `claude_compile_root()` altına yazılır (bkz. o fonksiyonun
    gerekçesi: proje kökündeki `.claude/agents` kullanıcının kendi CLI
    oturumuna sızıyordu).
    """
    agy_text = render_agy_agent(spec)
    claude_text = render_claude_agent(spec)
    out: Dict[str, Path] = {}
    for root in compile_roots(project_dir):
        agy_path = _write_if_changed(root / ".agents" / "agents" / spec.name / "agent.md", agy_text)
        if not out:
            out = {"agy": agy_path}
    claude_root = claude_compile_root()
    if claude_root is not None:
        out["claude"] = _write_if_changed(
            claude_root / ".claude" / "agents" / f"{spec.name}.md", claude_text
        )
    return out
