"""
Ajan oturum bütçesi ve devir sayfası (Faz 12-B, araştırma C §2.1 / karar 3).

Ölçüm
-----
Aynı ajanın üç kartı `--resume` ile **23.886 → 38.818 → 66.542** token harcadı
(ledger, araştırma C). Artış hızlanıyor çünkü her tur bütün konuşmayı yeniden
gönderiyor; 4. kart ekstrapolasyonla ~110k ve tek başına 90k tavanını aşıyor.
Buna karşılık kalıcılığın kazancı da gerçek: 3. kartta ajan "bunu zaten
ürettim" deyip işi tekrarlamadı.

Politika
--------
Oturum sonsuz değil ama BOŞA da atılmıyor:

1. `cards_in_session ≥ config.agent_session_max_cards` **veya**
   `tokens_in_session ≥ config.agent_session_max_tokens` → oturum döner
   (`AgentSessionStore.rotate`), sonraki kart taze `--session-id` ile başlar.
   agy kolunda aynı kural: `--conversation` düşürülür.
2. Dönmeden önce `Board/agents/<ad>/handoff.md` yazılır: son oturumun kartları,
   kararları ve açık işleri. **Kotasız** — özet için model çağırmak, kaçınmaya
   çalıştığımız maliyetin ta kendisi olurdu (bkz. `memory.handoff` gerekçesi).
   İçerik kartların `summary`/`checkpoint`/`notes` alanlarından çıkarımsal
   toplanır.
3. Yeni oturumun ilk isteminin sonuna devir sayfası `[ÖNCEKİ OTURUM]` bloğu
   olarak eklenir (K2'nin `claude-progress.txt` deseni).

`--autocompact` gibi sürüm bağımlı bayraklar burada YOK: risk R-D (bayrak
2.1.265'e özgü). Bütçe politikası CLI bayrağına değil, bizim sayaçlarımıza
dayanır ve iki sağlayıcıda da aynı çalışır.
"""

from __future__ import annotations

import datetime
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

#: Devir sayfasının dosya adı (`Entropy/Board/agents/<ad>/handoff.md`).
HANDOFF_FILENAME = "handoff.md"

#: İsteme eklenen bloğun etiketi.
HANDOFF_TAG = "[ÖNCEKİ OTURUM]"

#: Devir sayfasına giren en fazla kart ve satır başına karakter tavanı.
HANDOFF_MAX_CARDS = 6
HANDOFF_LINE_CHARS = 240
#: Bloğun isteme eklenen kısmının tavanı (bütçe koruması).
HANDOFF_PROMPT_CHARS = 2000


def handoff_path(agent: str, vault_path=None) -> Path:
    """`<kasa>/Entropy/Board/agents/<ad>/handoff.md`."""
    from entropy.core import paths as _paths

    return _paths.agent_session_path(agent, vault_path).with_name(HANDOFF_FILENAME)


def _thresholds():
    try:
        from entropy.core.config import config

        return (int(getattr(config, "agent_session_max_cards", 0) or 0),
                int(getattr(config, "agent_session_max_tokens", 0) or 0))
    except Exception:
        return 0, 0


def _line(text: str) -> str:
    return " ".join(str(text or "").split())[:HANDOFF_LINE_CHARS]


def build_handoff(agent: str, board=None, vault_path=None) -> str:
    """
    Son oturumun devir metnini üretir (model çağırmaz).

    Kaynak: ajanın en son kapanmış kartları. Her kart için tek satır özet,
    varsa kontrol noktası ve `[SORU]` notu. "Açık işler" = kartın kontrol
    noktasındaki `sonraki:` bilgisi ve hâlâ `assigned`/`backlog` bekleyen
    kartların başlıkları.
    """
    from entropy.agents.board_tool_exec import ASK_NOTE_PREFIX

    if board is None:
        try:
            from entropy.agents.tasks import TaskBoard

            board = TaskBoard(vault_path=vault_path)
        except Exception:
            return ""
    try:
        cards = [c for c in board.list()
                 if str(getattr(c, "agent", "") or "").strip().lower() == (agent or "").strip().lower()
                 and not (getattr(c, "office", "") or "").strip()]
    except Exception:
        return ""
    if not cards:
        return ""

    finished = [c for c in cards if c.status in ("review", "done", "failed")]
    finished.sort(key=lambda c: str(getattr(c, "finished_at", "") or ""), reverse=True)
    finished = finished[:HANDOFF_MAX_CARDS]
    pending = [c for c in cards if c.status in ("backlog", "assigned")]

    now = datetime.datetime.now().isoformat(timespec="seconds")
    lines: List[str] = [
        f"# Devir — {agent}",
        "",
        f"- Yazıldı: {now}",
        "- Kaynak: kart özetleri ve kontrol noktaları (model çağrılmadı)",
        "",
        "## Yapılanlar",
        "",
    ]
    if finished:
        for card in finished:
            summary = _line(card.summary) or "(özet yok)"
            lines.append(f"- `{card.id}` **{_line(card.title)}** ({card.status}): {summary}")
    else:
        lines.append("- (kapanmış kart yok)")

    decisions = [_line(c.verdict) for c in finished if (c.verdict or "").strip()]
    lines += ["", "## Kararlar", ""]
    lines += [f"- {d}" for d in decisions] or ["- (kayda geçmiş karar yok)"]

    open_items: List[str] = []
    for card in finished:
        cp = _line(card.checkpoint)
        if cp:
            open_items.append(f"`{card.id}` kontrol noktası: {cp}")
        for note in (card.notes or "").splitlines():
            if note.strip().startswith(ASK_NOTE_PREFIX):
                open_items.append(f"`{card.id}` {_line(note)}")
    for card in pending:
        open_items.append(f"`{card.id}` bekliyor: {_line(card.title)}")
    lines += ["", "## Açık işler", ""]
    lines += [f"- {item}" for item in open_items[:HANDOFF_MAX_CARDS * 2]] or ["- (yok)"]
    lines.append("")
    return "\n".join(lines)


def write_handoff(agent: str, board=None, vault_path=None) -> Optional[Path]:
    """Devir sayfasını diske yazar; içerik boşsa yazmaz ve None döner."""
    text = build_handoff(agent, board=board, vault_path=vault_path)
    if not text.strip():
        return None
    path = handoff_path(agent, vault_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path
    except OSError:
        logger.warning("Devir sayfası yazılamadı: %s", path)
        return None


def handoff_section(agent: str, vault_path=None) -> str:
    """Diskteki devir sayfasını isteme eklenecek bloğa çevirir ("" = yok)."""
    path = handoff_path(agent, vault_path)
    try:
        if not path.is_file():
            return ""
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    if not text.strip():
        return ""
    body = text.strip()[:HANDOFF_PROMPT_CHARS]
    return (
        f"{HANDOFF_TAG}\n"
        "Bu ajanın önceki oturumu bağlam bütçesi dolduğu için kapandı. Ham "
        "sohbet geçmişin YOK; aşağıdaki devir sayfası tek kaynağın. Yapılmış "
        "işi tekrarlama, açık işlerden devam et.\n\n"
        f"{body}"
    )


def note_run(agent: str, provider: str, tokens: int = 0, vault_path=None) -> dict:
    """Bir kart koşusunu oturum sayaçlarına işler."""
    if not agent or not provider:
        return {}
    try:
        from entropy.core.identity import agent_session_store

        return agent_session_store(vault_path).note_run(agent, provider, tokens)
    except Exception:
        logger.debug("Oturum sayacı güncellenemedi", exc_info=True)
        return {}


def rotate_if_needed(agent: str, provider: str, board=None, vault_path=None) -> str:
    """
    Eşik aşıldıysa oturumu döndürür ve isteme eklenecek devir bloğunu döndürür.

    Dönüş "" ise oturum SÜRÜYOR (hiçbir şey yapılmadı). Eşikler 0 ise politika
    kapalıdır (eski davranış: sınırsız `--resume`).
    """
    if not agent or not provider:
        return ""
    max_cards, max_tokens = _thresholds()
    if not (max_cards or max_tokens):
        return ""
    try:
        from entropy.core.identity import agent_session_store

        store = agent_session_store(vault_path)
        status = store.budget_status(agent, provider,
                                     max_cards=max_cards, max_tokens=max_tokens)
        if not status.get("exceeded"):
            return ""
        # Devir sayfası ÖNCE yazılır: oturum döndükten sonra kaynak (kartlar)
        # değişmez ama sıralama niyeti açık olsun — sayfa yoksa dönme de olmaz
        # anlamına GELMEZ; sayfa yazılamasa bile oturum döner (bağlam dolu).
        write_handoff(agent, board=board, vault_path=vault_path)
        store.rotate(agent, provider)
        logger.info("Ajan oturumu döndürüldü (%s/%s): %s",
                    agent, provider, status.get("reason"))
        _announce(agent, provider, str(status.get("reason") or ""))
        return handoff_section(agent, vault_path)
    except Exception:
        logger.debug("Oturum bütçesi uygulanamadı", exc_info=True)
        return ""


def _announce(agent: str, provider: str, reason: str) -> None:
    try:
        from entropy.core.event_bus import bus

        bus.task_notification.emit(
            f"session:{agent}",
            "Ajan oturumu tazelendi",
            f"{agent} ({provider}): {reason}. Devir sayfası yazıldı "
            f"({HANDOFF_FILENAME}); yeni oturum onunla başlıyor.",
        )
    except Exception:
        pass


__all__ = ["HANDOFF_FILENAME", "HANDOFF_TAG", "handoff_path", "build_handoff",
           "write_handoff", "handoff_section", "note_run", "rotate_if_needed"]
