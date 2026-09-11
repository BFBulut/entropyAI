"""
Faz 13-C / C4 — TEK YÖN sözleşmesi (Desk ↛ Entropy).

İki hüküm ölçülür:

(a) **Kimlik sızıntısı yok.** Ofis orkestratörünün ve işçisinin gördüğü hiçbir
    metinde Entropy'nin kimliği ya da Entropy'ye ait `[DESK …]` araç sözleşmesi
    bulunmaz. Kapsam: ofis şartnamesi (`spawn_section`, `build_plan_prompt`,
    `build_eval_prompt`), `brain.system_prompt` ofis kipi ve harness'ın doğuş
    talimatı.

(b) **Desk hiçbir yoldan Entropy panosuna kart yazamaz.** `board_create` ofis
    kartından reddedilir, ajan aktöründen reddedilir; `Entropy/Tasks/` altına
    ofis kartı düşmez; `board_ask` yalnızca posta kutusuna yazar (kart açmaz).

Bu dosya "iddia" değil ölçüm yapar: her hüküm gerçek üretim çağrısını koşar.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List

import pytest

from entropy.agents import board_tool_exec, board_tools
from entropy.agents.tasks import ALL_CARDS, TaskBoard, TaskCard


# Entropy kimliğini ele veren dizgiler (ofis metinlerinde HİÇBİRİ olmamalı).
IDENTITY_NEEDLES = ("entropy",)
DESK_NEEDLE = "[DESK"


def _mkcard(board: TaskBoard, title: str, *, agent: str, office: str = "",
            id: str = "20260911-1200-kart", **kw) -> TaskCard:
    return board.create(
        TaskCard(id=id, title=title, office=office, agent=agent,
                 status="backlog", **kw)
    )


@dataclass
class _Call:
    name: str
    args: Dict[str, Any]


def _assert_no_entropy(text: str, where: str) -> None:
    low = (text or "").lower()
    for needle in IDENTITY_NEEDLES:
        assert needle not in low, f"{where}: '{needle}' sızdı"
    assert DESK_NEEDLE not in (text or ""), f"{where}: '{DESK_NEEDLE}' sızdı"


# --- (a) kimlik sızıntısı ----------------------------------------------------


def test_office_system_prompt_kind_is_not_a_silent_chat_fallback() -> None:
    """
    `build_system_prompt` YALNIZCA Entropy'nindir: geçerli kipleri `chat`/`card`.
    Ofis metni oradan ÜRETİLMEZ; üretilseydi bilinmeyen kip sessizce `chat`e
    düşeceği için ofis ajanı Entropy'nin kimliğini ve araçlarını görürdü.
    Bu test o sessiz düşüşü kilit altına alır.
    """
    from entropy.brain import system_prompt

    assert system_prompt.VALID_KINDS == ("chat", "card")
    fallback = system_prompt.build_system_prompt("office", provider="claude")
    chat = system_prompt.build_system_prompt("chat", provider="claude")
    # Sessiz düşüş GERÇEKTEN var; bu yüzden ofis yolunda çağrılmaması sözleşme.
    assert fallback[:200] == chat[:200]
    import inspect

    from entropy.agents import harness as harness_mod

    src = inspect.getsource(harness_mod)
    assert "build_system_prompt" not in src, (
        "harness ofis istemini Entropy'nin sistem istemi kurucusundan üretiyor"
    )


def test_spawn_instruction_has_no_entropy_identity(office_harness) -> None:
    harness, office, _ = office_harness
    text = harness.spawn_section("kart-1")
    assert text.strip()
    _assert_no_entropy(text, "spawn_section")


def test_plan_prompt_has_no_entropy_identity_and_forbids_coding(
    office_harness, office_card
) -> None:
    harness, office, _ = office_harness
    prompt = harness.build_plan_prompt(office, office_card)
    _assert_no_entropy(prompt, "build_plan_prompt")
    assert "kod YAZMAZSIN" in prompt


def test_eval_prompt_has_no_entropy_identity(office_harness, office_card) -> None:
    harness, office, _ = office_harness
    prompt = harness.build_eval_prompt(office, office_card, [])
    _assert_no_entropy(prompt, "build_eval_prompt")


def test_office_charter_text_never_carries_the_desk_tool_contract() -> None:
    """`[DESK …]` sözleşmesi Entropy'nin sohbet istemine aittir, ofisinkine değil."""
    base = board_tools.tools_section(False)
    assert DESK_NEEDLE not in base
    entropy_side = board_tools.tools_section(True)
    assert DESK_NEEDLE in entropy_side


# --- (b) kart yazma yolları kapalı ------------------------------------------


def test_board_create_is_rejected_from_an_office_card(tmp_path) -> None:
    board = TaskBoard(vault_path=tmp_path)
    card = _mkcard(board, "Ofis üst kartı", agent="orkestratör", office="QA Ofisi")
    results = board_tool_exec.execute(
        [_Call("board_create", {"title": "Entropy panosuna kart", "agent": "a"})],
        board=board,
        card=card,
        actor="orkestratör",
        actor_kind=board_tool_exec.ACTOR_ENTROPY,
    )
    assert results[0]["ok"] is False
    assert "tek yönlü" in results[0]["error"]


def test_board_create_is_rejected_from_an_agent_actor(tmp_path) -> None:
    board = TaskBoard(vault_path=tmp_path)
    card = _mkcard(board, "Ofis üst kartı", agent="isci", office="QA Ofisi")
    results = board_tool_exec.execute(
        [_Call("board_create", {"title": "kart", "agent": "a"})],
        board=board,
        card=card,
        actor="isci",
        actor_kind=board_tool_exec.ACTOR_AGENT,
    )
    assert results[0]["ok"] is False


def test_no_office_card_lands_under_entropy_tasks(tmp_path) -> None:
    """Ofis kartının dosyası Desk kökünde durur; Entropy görev dizinine düşmez."""
    from entropy.core import paths

    board = TaskBoard(vault_path=tmp_path)
    _mkcard(board, "Ofis kartı", agent="orkestratör", office="QA Ofisi", id="20260911-1201-ofis")
    _mkcard(board, "Entropy kartı", agent="arastirmaci", office="", id="20260911-1202-entropy")
    tasks_dir = paths.vault_root(tmp_path) / "Entropy" / "Tasks"
    names = sorted(p.read_text(encoding="utf-8") for p in tasks_dir.glob("*.md"))
    assert len(names) == 1
    assert all("QA Ofisi" not in text for text in names)


def test_board_ask_is_rejected_from_an_office_card(tmp_path) -> None:
    """Ofis kartının sorusu Entropy'ye DEĞİL, ofisin kendi kutusuna gider."""
    board = TaskBoard(vault_path=tmp_path)
    card = _mkcard(board, "Ofis kartı", agent="isci", office="QA Ofisi")
    before = len(board.list())
    results = board_tool_exec.execute(
        [_Call("board_ask", {"question": "Bütçe ne kadar?"})],
        board=board,
        card=card,
        actor="isci",
        actor_kind=board_tool_exec.ACTOR_AGENT,
        vault_path=tmp_path,
    )
    assert results[0]["ok"] is False
    assert "posta kutusuna gider" in results[0]["error"]
    assert len(board.list()) == before, "board_ask kart açtı"


def test_board_ask_from_an_entropy_card_only_writes_to_the_mailbox(tmp_path) -> None:
    board = TaskBoard(vault_path=tmp_path)
    card = _mkcard(board, "Entropy kartı", agent="arastirmaci", office="")
    before = len(board.list())
    results = board_tool_exec.execute(
        [_Call("board_ask", {"question": "Bütçe ne kadar?"})],
        board=board,
        card=card,
        actor="arastirmaci",
        actor_kind=board_tool_exec.ACTOR_AGENT,
        vault_path=tmp_path,
    )
    assert results[0]["ok"] is True
    assert len(board.list()) == before, "board_ask kart açtı"
    assert board.get(card.id).status == "backlog", "board_ask kart durumunu değiştirdi"


# --- fikstürler --------------------------------------------------------------


@pytest.fixture()
def office_harness(tmp_path):
    from entropy.agents.desk_registry import DeskOffice, DeskRegistry
    from entropy.agents.harness import OfficeHarness

    board = TaskBoard(vault_path=tmp_path)
    offices = DeskRegistry(vault_path=tmp_path)
    office = offices.create(
        DeskOffice(name="QA Ofisi 13C", purpose="Küçük Python paketleri üretmek")
    )
    harness = OfficeHarness(
        "QA Ofisi 13C",
        board=board,
        registry=offices.agents("QA Ofisi 13C"),
        offices=offices,
    )
    return harness, office, offices


@pytest.fixture()
def office_card(tmp_path):
    board = TaskBoard(vault_path=tmp_path / "cards")
    return _mkcard(
        board,
        "slugify paketi",
        agent="orkestratör",
        office="QA Ofisi 13C",
        goal="İki modüllü küçük bir Python paketi yaz",
    )


# --- QA bulgusu: çok kelimeli ofis adı kırpılmamalı -------------------------


def test_desk_office_add_keeps_a_multi_word_name(tmp_path) -> None:
    """
    `/desk office add QA Ofisi 13C :: amaç` ofisi TAM adıyla açar.

    Regresyon: gövde `split()` ile bölünüp `names[0]` alınıyordu; kullanıcı
    "QA Ofisi 13C" açtığını sanarken diskte "QA" ofisi doğuyordu.
    """
    from entropy.agents.desk_registry import DeskRegistry
    from entropy.core import slash_commands as sc

    offices = DeskRegistry(vault_path=tmp_path)
    message = sc._handle_desk_admin(
        "office", "add QA Ofisi 13C :: Küçük Python paketleri", offices)
    assert "QA Ofisi 13C" in message
    spec = offices.get("QA Ofisi 13C")
    assert spec is not None, "ofis tam adıyla açılmadı"
    assert offices.get("QA") is None, "ad kırpılmış bir ofis doğdu"
    assert spec.purpose == "Küçük Python paketleri"
    # Orkestratör de doğar (kural 2).
    assert spec.orchestrator
    assert offices.agents("QA Ofisi 13C").get(spec.orchestrator) is not None


def test_desk_office_add_strips_surrounding_quotes(tmp_path) -> None:
    from entropy.agents.desk_registry import DeskRegistry
    from entropy.core import slash_commands as sc

    offices = DeskRegistry(vault_path=tmp_path)
    sc._handle_desk_admin("office", 'add "Tırnaklı Ofis" :: amaç', offices)
    assert offices.get("Tırnaklı Ofis") is not None


def test_desk_office_rm_also_takes_a_multi_word_name(tmp_path) -> None:
    from entropy.agents.desk_registry import DeskRegistry
    from entropy.core import slash_commands as sc

    offices = DeskRegistry(vault_path=tmp_path)
    sc._handle_desk_admin("office", "add QA Ofisi 13C :: amaç", offices)
    message = sc._handle_desk_admin("office", "rm QA Ofisi 13C", offices)
    assert "silindi" in message
    assert offices.get("QA Ofisi 13C") is None


def test_desk_admin_apply_creates_the_office_with_its_full_name(tmp_path) -> None:
    """Onay kuyruğundan uygulanan `office_create` de tam adı korur."""
    from entropy.agents import desk_admin
    from entropy.agents.desk_registry import DeskRegistry

    rid = desk_admin.queue_request(
        "office_create",
        {"name": "Onay Ofisi 13C", "purpose": "onay akışı"},
        vault_path=tmp_path,
    )
    rid = rid if isinstance(rid, str) else (rid or {}).get("id", "")
    result = desk_admin.apply_pending(rid, vault_path=tmp_path)
    assert result["ok"] is True, result["message"]
    assert DeskRegistry(vault_path=tmp_path).get("Onay Ofisi 13C") is not None
    assert not desk_admin.list_pending(tmp_path), "uygulanan istek kuyrukta kaldı"


# --- QA bulgusu: ofis kartı "kayıp kart" sayılmamalı ------------------------


def test_office_cards_are_not_counted_as_board_drift(tmp_path) -> None:
    """
    Ofis kartının dosyası Desk kökünde durur; ayrışma sayacı iki kökü de
    okumazsa her ofis kartı kalıcı "(dosya yok)" uyarısı üretir.

    Canlı ölçüm (Faz 13-C QA): iki alt kart koşarken uygulama dakikada bir
    "Pano ayrışması: 2 kart" yazıyordu, oysa iki kartın dosyası da diskteydi.
    """
    from entropy.agents.board_events import board_drift

    board = TaskBoard(vault_path=tmp_path)
    office_card = _mkcard(board, "Ofis kartı", agent="isci", office="QA Ofisi",
                          id="20260911-1301-ofis")
    board.apply_event(office_card.id, "task.assigned", actor="human")
    board.rewrite_taskboard()

    view = board.events.write_projection()
    assert office_card.id in (view.get("cards") or {}), "ofis kartı projeksiyonda yok"
    entropy_only = board_drift(list(board.list()), view)
    both_roots = board_drift(list(board.list(office=ALL_CARDS)), view)
    assert any(d["id"] == office_card.id for d in entropy_only), (
        "ölçüm kurgusu geçersiz: tek kökte ayrışma görünmüyor"
    )
    assert both_roots == [], f"ofis kartı ayrışma sayıldı: {both_roots}"
