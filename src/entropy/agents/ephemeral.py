"""
Geçici (kendini silen) ajan döngüsü — Faz 14-C.

Kullanıcının bağlayıcı tanımı (ARCHITECTURE §6.4, STATE §2.15): bir yetenek
koşulacaksa Entropy `SKILL.md`'yi alır, **o iş için** bir `agent.md` üretir,
ajana beyinden ilgili bağlamı verir, seçili motorla **ayrı bir CLI oturumu**
açar, akışı anlık gösterir, raporu alır ve **ajan kendini siler**. Hafızaya
girecek bilgiyi alt ajanın kendisi (`[HAFIZA]` bloğu) üretir; Entropy yazmaz,
yalnız kapıdan geçirir.

Yaşam döngüsü — tek yerde, Qt'siz, saf Python:

    prepare → spawn → stream → report → memory → cleanup

`prepare` dışarıdan da çağrılabilir (test ve `--dry-run` için): hiçbir süreç
açmaz, yalnız `EphemeralSpec` üretir.

Neden kalıcı kadro yolu KULLANILMIYOR: kalıcı ajanın `AGENT.md`si, `session.json`u
ve devir bütçesi vardı; kullanıcı bunların hiçbirini istemedi. Kadro kodu
**silinmez** (Desk ve pano ona bağlı), yalnız varsayılan yol artık burasıdır.

İki sağlayıcı, iki taşıma (araştırma B §3.2):

- **claude:** tanım `--agents '{"<slug>": {...}}'` ile **argv'de** taşınır, diske
  hiçbir ajan dosyası yazılmaz — silinecek bir şey kalmaz. Ayrıca
  `--no-session-persistence` ile CLI tarafında oturum kaydı da oluşmaz.
- **agy:** `--agents` yoktur; tanım `<workdir>/.agents/agents/<slug>/agent.md`
  dosyasına yazılır ve koşu bitince **dizin silinir**.

Kalanlar (silinmeyenler): ledger satırı (`run_type="ephemeral"`), rapor dosyası,
olay günlüğü satırları, kapıdan geçen hafıza düğümleri.
"""

from __future__ import annotations

import datetime
import json
import logging
import re
import shutil
import tempfile
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

#: Yetenek `SKILL.md` ön bilgisinde `max_steps` yoksa geçerli adım tavanı.
#: Kartlardaki 20'lik tavan (`tasks.MAX_STEPS_PER_CARD`) canlı araştırmada
#: 21. adımda kartı öldürüyordu (A notu); araştırma turu daha uzun sürer.
DEFAULT_MAX_STEPS = 60

#: Bağlam bütçesi (ARCHITECTURE §6.4 adım 1).
CONTEXT_TOKEN_BUDGET = 4000

#: Geçici ajanın araç sözleşmesi. Proje kökü argv'ye HİÇ girmediği için
#: `Write`/`Bash` yalnızca izole çalışma dizininde iş görür; ayrıca 14-B onay
#: yüzeyi her çağrıyı kullanıcıya sorar.
DEFAULT_TOOLS = ("Read", "Glob", "Grep", "WebSearch", "WebFetch", "Write", "Bash")

#: `[AJAN run] {json} [/AJAN]` — Entropy'nin kendi kararıyla geçici ajan açması.
AGENT_BLOCK_OPEN_RE = re.compile(r"\[AJAN\s+run\]", re.IGNORECASE)
AGENT_BLOCK_CLOSE = "[/AJAN]"

#: Bildirim satırının öneki (arayüz ve testler bunu arar).
NOTIFY_PREFIX = "Ajan"

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_TR_FOLD = str.maketrans("ıİşŞğĞüÜöÖçÇâÂîÎûÛ", "iisSgGuUoOcCaAiIuU")


def slugify(text: str, fallback: str = "gecici-ajan") -> str:
    """Ada güvenli, küçük harfli slug (CLI ajan adı ve dizin adı olur)."""
    folded = str(text or "").translate(_TR_FOLD).lower()
    slug = _SLUG_RE.sub("-", folded).strip("-")
    return slug[:40] or fallback


# ---------------------------------------------------------------------------
# agent.md üretimi
# ---------------------------------------------------------------------------


@dataclass
class EphemeralSpec:
    """Bir koşunun tam künyesi. `prepare` üretir, `spawn` tüketir."""

    slug: str
    skill: str
    goal: str
    description: str
    agent_md: str
    provider: str = "claude"
    model: str = ""
    effort: str = ""
    tools: List[str] = field(default_factory=lambda: list(DEFAULT_TOOLS))
    max_steps: int = DEFAULT_MAX_STEPS
    run_id: str = ""
    session_id: str = ""
    workdir: Optional[Path] = None
    context_tokens: int = 0

    def agents_json(self) -> str:
        """`claude --agents` yükü: TEK ajan, koşu başına üretilmiş."""
        entry: Dict[str, Any] = {
            "description": " ".join(self.description.split())[:400],
            "prompt": self.agent_md,
            "tools": list(self.tools),
        }
        if self.model:
            entry["model"] = self.model
        return json.dumps({self.slug: entry}, ensure_ascii=False)

    def user_message(self) -> str:
        """
        Kullanıcı mesajı: alt ajanı AÇIKÇA çağırır.

        `--agents` bir tanım bildirir, çağırmaz; "Use the <slug> subagent" satırı
        olmadan ana oturum işi kendisi yapardı ve "ayrı oturum" sözleşmesi
        kâğıt üstünde kalırdı.
        """
        return (
            f"Use the {self.slug} subagent to do the following task, then return "
            f"its full report verbatim as your answer.\n\n{self.goal}"
        )


def _skill_max_steps(skill_def: Any) -> int:
    """
    Yeteneğin `SKILL.md` ön bilgisindeki `max_steps`; yoksa `DEFAULT_MAX_STEPS`.

    `SkillDefinition` ön bilgiyi alan olarak taşımadığı için dosya doğrudan
    okunur (küçük ve yalnız bir kez).
    """
    path = str(getattr(skill_def, "path", "") or "")
    if not path:
        return DEFAULT_MAX_STEPS
    try:
        raw = Path(path).read_text(encoding="utf-8", errors="ignore")[:4000]
    except Exception:
        return DEFAULT_MAX_STEPS
    m = re.search(r"^\s*max_steps\s*:\s*(\d+)\s*$", raw, re.MULTILINE)
    if not m:
        return DEFAULT_MAX_STEPS
    try:
        value = int(m.group(1))
    except ValueError:
        return DEFAULT_MAX_STEPS
    return value if 1 <= value <= 500 else DEFAULT_MAX_STEPS


def build_agent_md(
    *,
    slug: str,
    skill_name: str,
    skill_instructions: str,
    goal: str,
    brain_context: str = "",
    max_steps: int = DEFAULT_MAX_STEPS,
) -> str:
    """
    `agent.md` gövdesi (küçük saf Python betiği — kullanıcının istediği gibi).

    Rapor şablonunun ilk satırı **`# H1`**: `core/report_title.derive_report_title`
    başlığı gövdenin ilk H1'inden türetir; şablon bunu zorlamazsa başlık istemden
    türer ve ARCHITECTURE §6.3'teki "sohbet turu rapor sanıldı" hatası geri gelir.
    """
    context_block = (brain_context or "").strip() or "(beyinde bu işe ait kayıt yok)"
    instructions = (skill_instructions or "").strip() or "(yetenek yordamı boş)"
    return "\n".join([
        f"# {slug}",
        "",
        "## Görev",
        goal.strip() or "(görev metni boş)",
        "",
        f"### Yetenek yordamı: {skill_name or '(yeteneksiz)'}",
        instructions,
        "",
        "## Bağlam (beyinden)",
        context_block,
        "",
        "## Kabul ölçütleri",
        "- Bulguların her biri KAYNAKLI olacak (URL ya da dosya yolu).",
        "- Beyinden gelen bağlam araştırmanın YERİNE geçmez; doğrulanmadan",
        "  yazılmaz.",
        f"- En çok {int(max_steps)} araç adımı kullan; ölçütleri karşıladığında dur.",
        "- Sonuç raporu tek mesajda, aşağıdaki şablonla dönecek.",
        "",
        "## Rapor şablonu",
        "```",
        "# <Raporun başlığı — tek satır, konuyu söyler>",
        "",
        "## Özet",
        "<3-6 madde>",
        "",
        "## Bulgular",
        "<kaynaklı bulgular>",
        "",
        "## Kaynaklar",
        "- <url ya da dosya yolu>",
        "```",
        "",
        "## Hafıza",
        "Raporun EN SONUNA, kalıcı olmayı hak eden bilgiyi şu blokla ekle",
        "(en çok 8 madde, her maddede kaynak ZORUNLU; yoksa bloğu hiç yazma):",
        "",
        "```",
        "[HAFIZA]",
        '{"items": [{"category": "semantic", "content": "<en az 40 karakter, '
        'tek cümlelik kalıcı bilgi>", "importance": 0.6, '
        '"provenance": "<url ya da dosya yolu>"}]}',
        "[/HAFIZA]",
        "```",
        "",
        "Kategori kapalı küme: working | episodic | semantic | procedural.",
        "Hata metni, yığın izi ya da günlük çıktısı hafızaya YAZILMAZ.",
        "",
        "## Yasaklar",
        "- Kod değişikliği yok: kaynak dosyaları düzenleme, commit atma.",
        "- Proje kökü SALT OKUNUR; yazman gereken geçici dosyalar yalnız kendi",
        "  çalışma dizinine yazılır.",
        "- Beyinden gelen yanıt araştırmanın yerine geçmez.",
        "- Kendi adına kalıcı bir ajan/oturum kaydı oluşturma; bu koşu tek",
        "  seferliktir ve bitince silinirsin.",
    ])


def prepare(
    skill: Any = None,
    prompt: str = "",
    brain_context: Any = None,
    engine: Optional[Dict[str, str]] = None,
    *,
    workdir: Optional[Path] = None,
    tools: Optional[List[str]] = None,
) -> EphemeralSpec:
    """
    Koşu künyesini üretir; hiçbir süreç açmaz, claude yolunda dosya yazmaz.

    `skill`: `SkillDefinition` ya da yetenek adı (çözümleme çağırana bırakılmaz,
    ad verilirse burada çözülür). `brain_context`: hazır metin ya da
    `AssembledContext`; None ise `CognitiveContextBuilder` ile kurulur.
    `engine`: `{"provider","model","effort"}` — Entropy'nin o anki motoru ya da
    bu koşu için seçilen motor.
    """
    skill_def = _resolve_skill(skill)
    skill_name = str(getattr(skill_def, "name", "") or (skill if isinstance(skill, str) else "") or "")
    goal = str(prompt or "").strip()
    run_id = uuid.uuid4().hex[:8]
    slug = slugify(f"{skill_name or 'arastirma'}-{run_id}")
    context_text, context_tokens = _context_text(brain_context, goal, skill_name)
    max_steps = _skill_max_steps(skill_def)
    eng = dict(engine or {})
    agent_md = build_agent_md(
        slug=slug,
        skill_name=skill_name,
        skill_instructions=str(getattr(skill_def, "instructions", "") or "")[:6000],
        goal=goal,
        brain_context=context_text,
        max_steps=max_steps,
    )
    description = (
        str(getattr(skill_def, "description", "") or "")
        or f"{skill_name or 'Araştırma'} işini tek seferlik koşan geçici ajan."
    )
    return EphemeralSpec(
        slug=slug,
        skill=skill_name,
        goal=goal,
        description=description,
        agent_md=agent_md,
        provider=str(eng.get("provider") or "").strip().lower() or "claude",
        model=str(eng.get("model") or "").strip(),
        effort=str(eng.get("effort") or "").strip().lower(),
        tools=list(tools or DEFAULT_TOOLS),
        max_steps=max_steps,
        run_id=run_id,
        session_id=str(uuid.uuid4()),
        workdir=Path(workdir) if workdir is not None else None,
        context_tokens=context_tokens,
    )


def _resolve_skill(skill: Any):
    """Ad verildiyse `SkillManager`den çözer; künye verildiyse aynen döner."""
    if skill is None or not isinstance(skill, str):
        return skill
    name = skill.strip()
    if not name:
        return None
    try:
        from entropy.skills.manager import SkillManager

        for item in SkillManager().list_skills():
            if str(getattr(item, "name", "")).lower() == name.lower():
                return item
    except Exception:
        logger.debug("Yetenek çözülemedi: %s", name, exc_info=True)
    return None


def _context_text(brain_context: Any, goal: str, skill_name: str) -> tuple:
    """Beyin bağlamını metne çevirir (bütçe `CONTEXT_TOKEN_BUDGET`)."""
    if isinstance(brain_context, str):
        return brain_context, len(brain_context) // 4
    if brain_context is not None and hasattr(brain_context, "render"):
        try:
            return str(brain_context.render() or ""), int(getattr(brain_context, "tokens", 0) or 0)
        except Exception:
            return "", 0
    try:
        from entropy.brain.context_builder import CognitiveContextBuilder

        ctx = CognitiveContextBuilder().build(
            query=goal,
            skill_name=skill_name or None,
            token_budget=CONTEXT_TOKEN_BUDGET,
            include_handoff=False,
        )
        return str(ctx.render() or ""), int(getattr(ctx, "tokens", 0) or 0)
    except Exception:
        logger.debug("Beyin bağlamı kurulamadı", exc_info=True)
        return "", 0


# ---------------------------------------------------------------------------
# Koşu
# ---------------------------------------------------------------------------


class EphemeralRun:
    """
    Tek bir geçici ajan koşusu: `prepare → spawn → stream → report → memory →
    cleanup`.

    Bloke etmez: `spawn` köprünün arka plan iş parçacığını başlatır, geri kalan
    adımlar `_on_result` içinde (köprünün iş parçacığında) koşar.
    """

    def __init__(
        self,
        skill: Any = None,
        goal: str = "",
        *,
        bridge: Any = None,
        engine: Optional[Dict[str, str]] = None,
        brain_context: Any = None,
        parent_run_id: str = "",
        card_id: str = "",
        memory: Any = None,
        vault=None,
        on_done: Optional[Callable[[str, bool], None]] = None,
    ):
        self.skill = skill
        self.goal = goal
        self.bridge = bridge
        self.engine = dict(engine or {})
        self.brain_context = brain_context
        self.parent_run_id = str(parent_run_id or "")
        self.card_id = str(card_id or "")
        self._memory = memory
        self._vault = vault
        self._on_done = on_done
        self.spec: Optional[EphemeralSpec] = None
        self.task_id: str = ""
        self.report_path: str = ""
        self.step_count: int = 0
        self.success: Optional[bool] = None
        self.memory_result: Any = None
        self.finished = threading.Event()

    # -- 1. prepare ----------------------------------------------------

    def prepare(self) -> EphemeralSpec:
        bridge = self.bridge or _default_bridge()
        engine = dict(self.engine)
        if not engine.get("provider"):
            engine["provider"] = str(getattr(bridge, "provider_name", "") or "claude")
        if not engine.get("model"):
            engine["model"] = str(
                getattr(bridge, "current_model", "") or getattr(bridge, "selected_model", "") or ""
            )
        if not engine.get("effort"):
            engine["effort"] = str(getattr(bridge, "selected_effort", "") or "")
        spec = prepare(
            skill=self.skill,
            prompt=self.goal,
            brain_context=self.brain_context,
            engine=engine,
        )
        spec.workdir = _make_workdir(spec.slug)
        if spec.provider != "claude":
            # agy'de `--agents` yok: tanım diske yazılır ve koşu sonunda silinir.
            _write_agy_agent_md(spec)
        self.spec = spec
        self.bridge = bridge
        return spec

    # -- 2. spawn ------------------------------------------------------

    def spawn(self) -> str:
        spec = self.spec or self.prepare()
        bridge = self.bridge
        self.task_id = f"eph-{spec.slug}"
        vault_reports = _vault_reports_dir(self._vault)
        extra_dirs = [str(spec.workdir)] + ([vault_reports] if vault_reports else [])
        kwargs: Dict[str, Any] = dict(
            task_id=self.task_id,
            task_name=f"{spec.skill or 'araştırma'}: {(spec.goal or '')[:60]}",
            prompt=spec.user_message(),
            mode="accept-edits",
            project_path=str(spec.workdir),
            on_result=self._on_result,
            # Raporu Entropy'nin kendisi yazar: başlık H1'den gelmeli, `[HAFIZA]`
            # bloğu görüntüden silinmeli ve bildirim TEK olmalı. Köprünün
            # kendi rapor yolu ikinci bir kart üretirdi.
            save_report=False,
            needs_write=False,
            max_steps=spec.max_steps,
            model=spec.model or None,
            effort=spec.effort or None,
            session_id=spec.session_id,
            skill=spec.skill or "",
            tools=list(spec.tools),
            stream_meta={"agent": spec.slug, "office": "", "card_id": self.card_id},
            ephemeral={
                "agents_json": spec.agents_json(),
                "system_prompt": spec.agent_md,
                "extra_dirs": extra_dirs,
                "no_session_persistence": True,
                "run_id": spec.run_id,
            },
        )
        _record_run_meta(self.task_id, "ephemeral", self.parent_run_id)
        _emit_stream_start(self.task_id, spec)
        bridge.send_background_task_async(**kwargs)
        return self.task_id

    # -- 3/4/5/6. sonuç: rapor → hafıza → bildirim → silme --------------

    def _on_result(self, full_text: str, ok: bool, report_path: str = "") -> None:
        spec = self.spec
        text = str(full_text or "")
        self.step_count = _steps_of(self.bridge, self.task_id)
        hit_limit = "[ADIM SINIRI]" in text
        self.success = bool(ok)
        try:
            self.report_path = self.report(text, ok) if text.strip() else ""
            self.memory_result = self.memory(text, ok)
            self._notify(text, ok, hit_limit)
            if self.card_id:
                _close_card(self.card_id, ok, hit_limit, self.report_path, text)
        except Exception:
            logger.exception("Geçici ajan sonucu işlenemedi (%s)", self.task_id)
        finally:
            self.cleanup()
            self.finished.set()
            if self._on_done is not None:
                try:
                    self._on_done(self.task_id, bool(ok))
                except Exception:
                    logger.exception("Geçici ajan geri çağrısı hata verdi")

    def report(self, text: str, ok: bool) -> str:
        """Raporu kasaya yazar; başlık gövdenin ilk H1'inden gelir."""
        from entropy.core.report_title import (
            derive_report_title,
            safe_filename_title,
            strip_machine_blocks,
        )

        spec = self.spec
        body = strip_machine_blocks(text).strip()
        title = derive_report_title(text, fallback=(spec.goal or spec.slug)[:60])
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        header = (
            f"# {title}\n\n"
            f"- **Ajan**: `{spec.slug}` (geçici, koşu sonunda silindi)\n"
            f"- **Yetenek**: {spec.skill or '-'}\n"
            f"- **Motor**: {spec.provider} / {spec.model or '(oturum modeli)'}"
            f"{(' / ' + spec.effort) if spec.effort else ''}\n"
            f"- **Görev kimliği**: `{self.task_id}`\n"
            f"- **Durum**: {'Başarılı' if ok else 'Hata / Uyarı'}\n\n"
        )
        # Gövde zaten H1 ile başlıyorsa ikinci bir başlık yazılmaz.
        if body.lstrip().startswith("# "):
            first, _, rest = body.lstrip().partition("\n")
            content = f"{first}\n\n{header.split(chr(10), 2)[2]}{rest.strip()}\n"
        else:
            content = header + body + "\n"
        try:
            vault = self._vault or _default_vault()
            path = vault.save_research_report(
                f"Ajan_{safe_filename_title(title, max_len=60)}_{stamp}",
                content,
                tags=["gecici_ajan", self.task_id],
                skill_name=spec.skill or None,
            )
            return str(path)
        except Exception:
            logger.exception("Geçici ajan raporu yazılamadı")
            return ""

    def memory(self, text: str, ok: bool) -> Any:
        """`[HAFIZA]` bloğunu ALT AJANIN yazdığı JSON olarak kapıya verir."""
        try:
            from entropy.brain.agent_memory_writer import ingest_agent_report

            memory = self._memory
            if memory is None:
                from entropy.brain.supabase.cognitive_memory import CognitiveMemorySystem

                memory = CognitiveMemorySystem()
            return ingest_agent_report(
                memory,
                text,
                report_path=self.report_path,
                success=bool(ok),
                # Kanıt = kasaya yazılmış rapor. Raporsuz koşunun bloğu okunmaz.
                has_proof=bool(self.report_path),
            )
        except Exception:
            logger.exception("Geçici ajanın hafıza bloğu işlenemedi")
            return None

    def _notify(self, text: str, ok: bool, hit_limit: bool) -> None:
        """TEK bildirim (çift kart yok): rapor kartını da bu satır temsil eder."""
        from entropy.core.event_bus import bus
        from entropy.core.report_title import derive_report_title

        spec = self.spec
        title = derive_report_title(text, fallback=spec.goal[:60] or spec.slug)
        state = "bitti" if ok and not hit_limit else (
            "adım tavanında durdu" if hit_limit else "hata ile bitti"
        )
        summary = (
            f"{NOTIFY_PREFIX} {spec.slug} {state}: {title}; "
            f"{self.step_count} araç adımı"
        )
        if self.report_path:
            summary += f"; rapor: {self.report_path}"
        try:
            bus.task_notification.emit(self.task_id, summary,
                                       self.report_path or summary)
        except Exception:
            pass
        # `report_created` BİLEREK yayılmaz: 14-E bildirim kartı `task_notification`
        # ile besleniyor ve iki sinyal aynı koşu için iki kart üretirdi
        # (A notu "aynı rapor ×2, üç bildirim" bulgusu).

    # -- 7. kendini silme ----------------------------------------------

    def cleanup(self) -> None:
        """
        Geçici çalışma dizinini (agy'nin `agent.md`si dâhil) siler.

        Sistem istemi dosyasını köprü zaten siliyor
        (`cleanup_system_prompt_file`), oturum kaydı `--no-session-persistence`
        ile hiç oluşmuyor. Kalan: ledger, rapor, olay, hafıza.
        """
        spec = self.spec
        if spec is None or spec.workdir is None:
            return
        try:
            shutil.rmtree(spec.workdir, ignore_errors=True)
        except Exception:
            logger.debug("Geçici çalışma dizini silinemedi: %s", spec.workdir)


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------


def _make_workdir(slug: str) -> Path:
    base = Path(tempfile.gettempdir()) / "entropy_ephemeral" / slug
    base.mkdir(parents=True, exist_ok=True)
    return base


def _write_agy_agent_md(spec: EphemeralSpec) -> Path:
    """agy yolunda tanım dosyaya yazılır (`--agents` yok)."""
    target = Path(spec.workdir) / ".agents" / "agents" / spec.slug / "agent.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    front = "\n".join([
        "---",
        f"name: {spec.slug}",
        f"description: {' '.join(spec.description.split())[:200]}",
        "---",
        "",
    ])
    target.write_text(front + spec.agent_md, encoding="utf-8")
    return target


def _default_bridge():
    from entropy.ui.manager import EntropyUIManager

    mgr = getattr(EntropyUIManager, "instance", None)
    bridge = getattr(mgr, "bridge", None) if mgr is not None else None
    if bridge is not None:
        return bridge
    from entropy.core.claude_bridge import ClaudeCodeBridge

    return ClaudeCodeBridge()


def _default_vault():
    from entropy.brain.obsidian.vault_manager import ObsidianVaultManager

    return ObsidianVaultManager()


def _vault_reports_dir(vault=None) -> str:
    try:
        vm = vault or _default_vault()
        base = Path(getattr(vm, "vault_path", "") or "")
        target = base / "Entropy" / "Reports"
        if base.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            return str(target)
    except Exception:
        pass
    return ""


def _steps_of(bridge: Any, task_id: str) -> int:
    for attr in ("background_step_counts", "_background_step_counts"):
        counts = getattr(bridge, attr, None)
        if isinstance(counts, dict) and task_id in counts:
            try:
                return int(counts[task_id])
            except Exception:
                return 0
    return 0


def _record_run_meta(task_id: str, run_type: str, parent_run_id: str) -> None:
    try:
        from entropy.core.task_ledger import task_ledger

        task_ledger.record_run_meta(task_id, run_type=run_type,
                                    parent_run_id=parent_run_id)
    except Exception:
        logger.debug("Ledger koşu künyesi yazılamadı", exc_info=True)


def _emit_stream_start(task_id: str, spec: EphemeralSpec) -> None:
    try:
        from entropy.core.event_bus import bus
        from entropy.core.provider import build_agent_stream_event

        bus.agent_stream.emit(build_agent_stream_event(
            task_id=task_id,
            kind="status",
            text=f"{spec.slug} doğdu; {spec.skill or 'araştırma'} işine başlıyor…",
            agent=spec.slug,
            state="working",
        ))
    except Exception:
        logger.debug("Geçici ajan akış olayı yayılamadı", exc_info=True)


def _close_card(card_id: str, ok: bool, hit_limit: bool, report_path: str,
                text: str) -> None:
    """
    Pano kartını kapatır (FSM'e DOKUNULMAZ, alt küme kullanılır).

    Adım tavanına çarpan kart `failed` değil **`review`** ile kapanır: iş
    yapılmıştır, yalnız tavan yetmemiştir (ARCHITECTURE §6.4).
    """
    try:
        from entropy.agents.tasks import TaskBoard

        board = TaskBoard()
        # `ok=True` → `review` (T6), `ok=False` → `failed` (T7). Adım tavanı
        # BAŞARISIZLIK DEĞİLDİR: iş yapıldı, yalnız tavan yetmedi.
        payload = {
            "ok": bool(ok) or bool(hit_limit),
            "report_path": report_path,
            "summary": (
                "adım tavanı aşıldı; kısmi sonuç incelemede"
                if hit_limit else text[:300]
            ),
        }
        board.apply_event(card_id, "run.finished", actor="ephemeral",
                          payload=payload)
    except Exception:
        logger.debug("Geçici koşu kartı kapatılamadı: %s", card_id, exc_info=True)


# ---------------------------------------------------------------------------
# Tetikleme yüzeyleri
# ---------------------------------------------------------------------------


def run_skill(skill: Any, goal: str, **kwargs) -> EphemeralRun:
    """`/skill run <ad> :: <istem>` ve `[AJAN run]` bloğunun ortak girişi."""
    run = EphemeralRun(skill=skill, goal=goal, **kwargs)
    run.prepare()
    run.spawn()
    return run


def parse_agent_blocks(text: str) -> List[Dict[str, Any]]:
    """
    `[AJAN run] {json} [/AJAN]` bloklarını ayrıştırır.

    Bozuk JSON ATLANIR (pano bloklarıyla aynı bağışlayıcılık): tek yazım hatası
    turu çöpe atmamalı.
    """
    raw = text or ""
    out: List[Dict[str, Any]] = []
    for m in AGENT_BLOCK_OPEN_RE.finditer(raw):
        end = raw.find(AGENT_BLOCK_CLOSE, m.end())
        body = raw[m.end():end if end != -1 else len(raw)].strip()
        if not body:
            continue
        try:
            parsed = json.loads(body)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            out.append(parsed)
    return out


def strip_agent_blocks(text: str) -> str:
    """`[AJAN run] … [/AJAN]` bloklarını görüntülenen metinden çıkarır."""
    raw = text or ""
    out = []
    pos = 0
    for m in AGENT_BLOCK_OPEN_RE.finditer(raw):
        if m.start() < pos:
            continue
        out.append(raw[pos:m.start()])
        end = raw.find(AGENT_BLOCK_CLOSE, m.end())
        pos = len(raw) if end == -1 else end + len(AGENT_BLOCK_CLOSE)
    out.append(raw[pos:])
    return "".join(out).strip()


#: Entropy'nin sistem istemine giren araç sözleşmesi satırı (`[AJAN run]`).
AGENT_TOOL_SECTION = (
    "[AJAN run] {\"skill\": \"<yetenek adı ya da boş>\", \"goal\": \"<tek "
    "cümlelik iş tanımı>\"} [/AJAN]\n"
    "- Bir araştırma/yetenek işi gerektiğinde bu bloğu yaz: o iş için tek "
    "seferlik bir ajan doğar, raporunu anlık iletir ve kendini siler.\n"
    "- Onay gerekmez (ajan açmak senin işin); ajan izin isteyen bir araç "
    "çağırırsa onay kullanıcıya ayrıca sorulur."
)


def consume_agent_blocks(text: str, **kwargs) -> List[str]:
    """
    Yanıttaki `[AJAN run]` bloklarını koşar; makbuz satırlarını döndürür.

    Tur başına TEK ajan: kendi kendine ajan yağdıran bir Entropy kotayı bir
    gecede bitirir (pano kartındaki `MAX_CARDS_PER_TURN` ile aynı gerekçe).
    """
    blocks = parse_agent_blocks(text)
    if not blocks:
        return []
    receipts: List[str] = []
    for payload in blocks[:1]:
        goal = str(payload.get("goal") or payload.get("prompt") or "").strip()
        skill = str(payload.get("skill") or "").strip()
        if not goal:
            receipts.append("Ajan açılamadı: `goal` zorunlu.")
            continue
        try:
            run = run_skill(skill or None, goal, **kwargs)
            receipts.append(
                f"{NOTIFY_PREFIX} {run.spec.slug} açıldı: {goal[:80]} "
                f"(geçici; iş bitince kendini siler)"
            )
        except Exception as exc:
            logger.warning("Geçici ajan açılamadı: %s", exc, exc_info=True)
            receipts.append(f"Ajan açılamadı: {exc}")
    if len(blocks) > 1:
        receipts.append(
            f"({len(blocks) - 1} ajan bloğu yok sayıldı: tur başına en fazla 1)"
        )
    return receipts


__all__ = [
    "DEFAULT_MAX_STEPS",
    "CONTEXT_TOKEN_BUDGET",
    "DEFAULT_TOOLS",
    "AGENT_TOOL_SECTION",
    "NOTIFY_PREFIX",
    "EphemeralSpec",
    "EphemeralRun",
    "build_agent_md",
    "prepare",
    "run_skill",
    "slugify",
    "parse_agent_blocks",
    "strip_agent_blocks",
    "consume_agent_blocks",
]
