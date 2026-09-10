"""
Pano araçlarının YÜRÜTÜCÜSÜ (Faz 12-B, araştırma C §1.3 / karar 1).

Sorun
-----
`board_tools.py` beş aracı tanımlıyor ve `tasks._board_tool_results` blokları
ayrıştırıyordu, ama dönen çağrı listesi hiçbir yerde tüketilmiyordu: yalnızca
`board_finish` argümanları okunuyordu. Canlı kanıt (araştırma C §1.3): ajanın
yazdığı `[KONTROL NOKTASI]` bloğu kartın `checkpoint` alanına HİÇ işlenmedi,
`board_ask` sorusu kimseye ulaşmadı, `board_next` yanıtsız kaldı. Yanıtsız araç
yüzeyi modeli boşuna deneme yapmaya iter (Anthropic araç rehberi).

Bu modül tek giriş noktasıdır: `execute(calls, board=..., card=..., actor=...)`.

Neden ayrı modül
----------------
`tasks.py` zaten 2.000 satır ve panonun durum makinesini taşıyor; araç
yürütmesi ondan bağımsız olarak test edilebilmeli (sahte pano, sahte posta
kutusu). Ayrıca aynı yürütücü iki yönden çağrılır: ajanın koşu sonucundan
(`tasks._finish`) ve Entropy'nin sohbet yanıtından (`core.response_hooks`).

Yön kuralı
----------
- `board_create` YALNIZCA Entropy'nindir (`actor_kind="entropy"`); ajan
  çağırırsa reddedilir. Ofis kartından gelen çağrı da reddedilir: Desk →
  Entropy tek yönlüdür, bir ofis ajanı Entropy'nin panosuna kart açamaz.
- `board_ask` ajandan Entropy'ye gider (soru serbest); ofis kartında
  reddedilir (ofis tarafının kendi posta kutusu var).
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any, Dict, List, Optional

from entropy.agents import board_tools

logger = logging.getLogger(__name__)

#: Ajanın koşusundan gelen çağrılar için aktör türü.
ACTOR_AGENT = "agent"
#: Entropy'nin sohbet yanıtından gelen çağrılar için aktör türü.
ACTOR_ENTROPY = "entropy"

#: Kart notuna düşen soru satırının ön eki (makbuz ve arayüz bunu arar).
ASK_NOTE_PREFIX = "[SORU]"
#: `board_ask` sonrası kartın inceleme alanına yazılan durum metni.
ASK_REVIEW_TEXT = "soru bekliyor"


class ToolResult(dict):
    """Tek araç çağrısının sonucu (`dict` alt sınıfı: JSON'a doğrudan gider)."""


def _ok(name: str, **fields) -> ToolResult:
    out = ToolResult(tool=name, ok=True)
    out.update(fields)
    return out


def _err(name: str, message: str) -> ToolResult:
    return ToolResult(tool=name, ok=False, error=message)


def execute(
    calls,
    board=None,
    card=None,
    actor: str = "",
    actor_kind: str = ACTOR_AGENT,
    vault_path=None,
) -> List[ToolResult]:
    """
    Ayrıştırılmış araç çağrılarını yürütür ve sonuç listesini döndürür.

    Hiçbir çağrı istisna YÜKSELTMEZ: bir aracın patlaması kartın kapanmasını
    engellememeli (kapanmayan kart, kirli bir araç sonucundan pahalıdır).
    Hatalar sonuç sözlüğünde `ok=False` + `error` olarak döner ve günlüğe düşer.
    """
    results: List[ToolResult] = []
    for call in list(calls or []):
        name = getattr(call, "name", "") or ""
        args = dict(getattr(call, "args", None) or {})
        try:
            if name == "board_checkpoint":
                results.append(_run_checkpoint(board, card, args, actor, vault_path))
            elif name == "board_ask":
                results.append(_run_ask(board, card, args, actor, actor_kind, vault_path))
            elif name == "board_next":
                results.append(_run_next(board, card, args, actor))
            elif name == "board_create":
                results.append(_run_create(board, card, args, actor, actor_kind))
            elif name == "board_finish":
                # `board_finish` kartın kapanış yolunda (`tasks._finish`)
                # tüketilir; burada yalnızca kayıt için raporlanır.
                results.append(_ok(name, handled_by="tasks._finish"))
            else:
                results.append(_err(name or "?", "bilinmeyen araç"))
        except Exception as exc:  # pragma: no cover - savunma
            logger.warning("Pano aracı yürütülemedi (%s): %s", name, exc)
            results.append(_err(name or "?", str(exc)))
    return results


# --- board_checkpoint --------------------------------------------------------


def _run_checkpoint(board, card, args: Dict[str, Any], actor: str,
                    vault_path) -> ToolResult:
    """
    Kontrol noktasını diske yazar ve kartın `checkpoint` alanını doldurur.

    Disk yazımı `memory.checkpoints.write_checkpoint`ın işidir ve o modül
    hafıza katmanına aittir: içe aktarma KORUMALI, modül yoksa kart alanı yine
    de dolar (ajan katmanı hafıza katmanına sert bağımlı olamaz).
    """
    if card is None:
        return _err("board_checkpoint", "kart yok")
    done = str(args.get("done") or "").strip()
    next_steps = str(args.get("next") or args.get("next_steps") or "").strip()
    files = args.get("files") or args.get("files_touched") or []
    tests = str(args.get("tests") or "").strip()
    summary = str(args.get("summary") or done).strip()
    if not (done or next_steps or tests or summary):
        return _err("board_checkpoint", "boş kontrol noktası: en az `done` yaz")

    path = ""
    try:
        from entropy.memory.checkpoints import write_checkpoint  # type: ignore

        written = write_checkpoint(
            card.office or "entropy",
            card.id,
            summary=summary,
            done=done,
            next_steps=next_steps,
            files_touched=files,
            tests=tests,
            author=actor or card.agent or "",
            vault_path=vault_path,
        )
        path = str(written)
    except Exception:
        logger.debug("Kontrol noktası diske yazılamadı", exc_info=True)

    # Kart alanı sözleşmesi (Faz 10-A): `checkpoint` kontrol noktası
    # DOSYASININ yolunu taşır — çökme sonrası yeniden koşu o dosyadan sürer.
    # Dosya yazılamadıysa (hafıza katmanı yok) tek satırlık özet yazılır ki
    # alan hiç boş kalmasın.
    line = " · ".join(p for p in (done, f"sonraki: {next_steps}" if next_steps else "",
                                  f"test: {tests}" if tests else "") if p)[:400]
    updated = _update_card(board, card, checkpoint=path or line)
    _emit_checkpoint(card, path)
    return _ok("board_checkpoint", card_id=card.id, path=path,
               checkpoint=line, card=updated)


def _emit_checkpoint(card, path: str) -> None:
    try:
        from entropy.core.event_bus import bus

        bus.checkpoint_written.emit({
            "office": card.office or "", "card_id": card.id, "path": path,
        })
    except Exception:
        pass


# --- board_ask ---------------------------------------------------------------


def _run_ask(board, card, args: Dict[str, Any], actor: str, actor_kind: str,
             vault_path) -> ToolResult:
    """Ajanın sorusunu Entropy'nin gelen kutusuna bırakır (bloke etmez)."""
    question = str(args.get("question") or "").strip()
    if not question:
        return _err("board_ask", "boş soru")
    if card is not None and (card.office or "").strip():
        return _err("board_ask",
                    "ofis kartından Entropy'ye soru sorulamaz: soru ofisin "
                    "kendi posta kutusuna gider")
    task_id = str(args.get("task_id") or (card.id if card is not None else "")).strip()
    try:
        from entropy.agents.mailbox import ask_entropy

        ask_entropy(actor or (card.agent if card is not None else "") or "agent",
                    question, task_id=task_id, vault_path=vault_path)
    except Exception as exc:
        return _err("board_ask", f"posta kutusuna bırakılamadı: {exc}")

    updated = None
    if card is not None:
        note = f"{ASK_NOTE_PREFIX} {question}"[:500]
        notes = (card.notes or "").rstrip()
        updated = _update_card(
            board, card,
            notes=(notes + "\n" + note).strip() if notes else note,
            review=ASK_REVIEW_TEXT,
        )
    # Kart DURUMU değişmez: soru bloke etmez, ajan çalışmaya devam eder.
    return _ok("board_ask", card_id=task_id, question=question[:200],
               review=ASK_REVIEW_TEXT, card=updated)


# --- board_next --------------------------------------------------------------


def _run_next(board, card, args: Dict[str, Any], actor: str) -> ToolResult:
    """
    Ajana atanmış SIRADAKİ `assigned` kartı döndürür (yoksa "yok").

    Sahiplenme burada YAPILMAZ: kartı tetikleyici (`dispatcher`) çekiyor ve
    kilidi o alıyor; araç iki kez sahiplenirse `claims/<id>.lock` yarışı
    doğardı. Araç "sıradaki ne" sorusunun yanıtıdır, bir itme kanalı değil.
    """
    agent = str(args.get("agent") or actor or (card.agent if card is not None else "")).strip()
    if not agent:
        return _err("board_next", "ajan adı yok")
    if board is None:
        return _err("board_next", "pano yok")
    current = card.id if card is not None else ""
    candidates = [
        c for c in board.list(status="assigned")
        if str(getattr(c, "agent", "") or "").strip().lower() == agent.lower()
        and not (getattr(c, "office", "") or "").strip()
        and c.id != current
    ]
    if not candidates:
        return _ok("board_next", agent=agent, result="yok", card=None)
    candidates.sort(key=lambda c: (str(getattr(c, "priority", "") or "P9"),
                                   str(getattr(c, "created_at", "") or ""),
                                   str(c.id)))
    return _ok("board_next", agent=agent, result="var",
               next=board_tools.normalize_next(candidates[0]))


# --- board_create ------------------------------------------------------------


def _run_create(board, card, args: Dict[str, Any], actor: str,
                actor_kind: str) -> ToolResult:
    """`board_create` yalnızca Entropy'nindir; ajandan gelen çağrı reddedilir."""
    if actor_kind != ACTOR_ENTROPY:
        return _err(
            "board_create",
            "bu araç sana kapalı: kart açmaya yalnızca Entropy karar verir. "
            "Bir işin başkasına devredilmesi gerekiyorsa `board_ask` ile sor.",
        )
    if card is not None and (card.office or "").strip():
        return _err("board_create",
                    "ofis kartından Entropy panosuna kart açılamaz (tek yönlü akış)")
    from entropy.agents.board_autonomy import create_card_from_args

    created, note = create_card_from_args(args, board=board)
    if created is None:
        return _err("board_create", note)
    return _ok("board_create", card_id=created.id, title=created.title,
               agent=created.agent, status=created.status, note=note)


# --- ortak -------------------------------------------------------------------


def _update_card(board, card, **fields):
    """Kartı diske yazar; pano yoksa yalnızca bellekteki kopyayı günceller."""
    updated = replace(card, **fields)
    if board is None:
        return updated
    try:
        return board.update(updated)
    except Exception:
        logger.debug("Kart güncellenemedi (%s)", getattr(card, "id", "?"), exc_info=True)
        return updated


__all__ = ["execute", "ToolResult", "ACTOR_AGENT", "ACTOR_ENTROPY",
           "ASK_NOTE_PREFIX", "ASK_REVIEW_TEXT"]
