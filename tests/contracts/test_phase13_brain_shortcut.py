"""
Faz 13-A2 — BEYİN KISA DEVRESİ KAPALI (kullanıcı geri bildirimi, bağlayıcı).

Gerçek ekranda ölçülen hata: kullanıcı "araştırma yap" dedi → kart
`kind=research` → kart CLI'ya HİÇ gitmeden "Beyinden yanıtlandı (güven 0,49)"
notuyla kapandı ve "yanıt" diye gösterilen metin Entropy'nin KİMLİK düğümüydü
("I am Entropy AI, an autonomous agentic desktop operating system…").

Kullanıcının kuralı: **"araştır" dendiğinde araştırma canlı koşar; beyin ajana
bağlamdır, araştırmanın yerine geçmez.** Bu dosya o kuralı altı hükümle
çiviler; hepsi tmp kasa / sahte köprü ile koşar, model çağrısı YOKTUR.
"""

from __future__ import annotations

import pytest

from entropy.agents import amplification
from entropy.agents.registry import AgentRegistry, AgentSpec
from entropy.agents.tasks import TaskBoard, TaskCard


@pytest.fixture
def vault(tmp_path):
    root = tmp_path / "vault"
    (root / "Entropy" / "Tasks").mkdir(parents=True, exist_ok=True)
    AgentRegistry(vault_path=root).create(
        AgentSpec(name="arastirmaci", role="Araştırmacı", provider="claude",
                  tools_policy="read-only", prompt="Araştır.")
    )
    return root


class FakeCtx:
    """`AssembledContext` yerine geçen asgari nesne."""

    def __init__(self, confidence: float, text: str) -> None:
        self.brain_confidence = confidence
        self.text = text

    @property
    def brain_has_answer(self) -> bool:
        from entropy.memory.context_builder import crag_min_score

        return self.brain_confidence >= crag_min_score()


class FakeBuilder:
    def __init__(self, ctx):
        self.ctx = ctx

    def build(self, query, **_kw):
        return self.ctx


class FakeBridge:
    def __init__(self) -> None:
        self.calls = []

    def send_background_task_async(self, **kwargs):
        self.calls.append(kwargs)


def _assigned_card(board, **kw) -> TaskCard:
    card = board.create(TaskCard(agent="arastirmaci", provider="claude", **kw))
    board.apply_event(card.id, "task.assigned", payload={"agent": "arastirmaci"})
    return card


# --- (a) araştırma kartı yüksek güvenle bile CANLI koşar --------------------

def test_research_card_runs_live_even_with_a_confident_brain_hit(
        vault, tmp_path, monkeypatch):
    """Yüksek güvenli, kaynaklı beyin isabeti VAR — kart yine de CLI'ya gider."""
    from entropy.core.config import config

    monkeypatch.setattr(config, "brain_shortcut_enabled", False, raising=False)
    body = "Bulgu: hibrit arama BM25 + vektör. Kaynak: https://ornek.org/rapor"
    monkeypatch.setattr("entropy.memory.context_builder.CognitiveContextBuilder",
                        lambda *a, **k: FakeBuilder(FakeCtx(0.93, body)))

    board = TaskBoard(vault_path=vault)
    card = _assigned_card(board, id="p13-a", title="Hibrit aramayı araştır",
                          goal="rapor hazırla", kind="research")

    bridge = FakeBridge()
    task_id = board.run(card.id, bridge_factory=lambda _p=None: bridge)

    assert bridge.calls, "araştırma kartı kısa devre yaptı (canlı koşmalıydı)"
    assert not str(task_id or "").startswith("brain-")
    prompt = str(bridge.calls[0].get("prompt") or bridge.calls[0].get("task") or "")
    assert "[BEYİN]" in prompt, "beyin bağlamı isteme girmedi"
    assert "https://ornek.org/rapor" in prompt
    closed = board.get(card.id)
    assert "Beyinden yanıtlandı" not in (closed.summary or "")


# --- (b) kimlik düğümü ASLA yanıt değil -------------------------------------

def test_identity_node_is_never_an_answer_and_never_packed():
    from entropy.memory import context_builder as cb

    class Node:
        def __init__(self, is_identity=0, provenance=""):
            self.is_identity = is_identity
            self.provenance = provenance
            self.content = "I am Entropy AI, an autonomous agentic desktop OS."

    assert cb.is_answer_node(Node(is_identity=1)) is False
    assert cb.is_answer_node(Node(provenance="identity:core")) is False
    assert cb.is_answer_node(Node(provenance="legacy:pre-v2")) is False
    assert cb.is_answer_node(Node(provenance="https://ornek.org/x")) is True
    assert cb.is_identity_node(Node(provenance="identity:core")) is True
    assert cb.is_identity_node(Node(provenance="legacy:pre-v2")) is False


def test_identity_hit_does_not_raise_brain_confidence(tmp_path):
    """Geri çağırma yalnız kimlik düğümü döndürürse güven 0 kalır."""
    from entropy.memory.context_builder import CognitiveContextBuilder

    class Node:
        def __init__(self, content, is_identity=0, provenance=""):
            self.content = content
            self.is_identity = is_identity
            self.provenance = provenance

    class Memory:
        def hybrid_recall(self, query, **_kw):
            return [(Node("I am Entropy AI, an agentic desktop OS.",
                          is_identity=1, provenance="identity:core"), 0.49)]

        def get_all_nodes(self):
            return []

    builder = CognitiveContextBuilder(memory_system=Memory())
    ctx = builder.build("vektör veritabanlarını araştır")
    assert ctx.brain_confidence == 0.0
    assert ctx.brain_has_answer is False
    assert "I am Entropy AI" not in ctx.render()


# --- (c) açık tercih: brain_only -------------------------------------------

def test_brain_only_shortcuts_with_an_explicit_label(monkeypatch):
    body = "Yanıt: ölçüm 42 ms. Kaynak: https://ornek.org/olcum"
    answer = amplification.brain_lookup(
        "gecikmeyi araştır --brain-only",
        builder=FakeBuilder(FakeCtx(0.88, body)))
    assert answer.has_answer is True, answer.shortcut_reason
    note = answer.note()
    assert "CANLI ARAŞTIRMA YAPILMADI" in note
    assert "Beyinden yanıtlandı" in note


def test_brain_only_still_refuses_low_confidence_or_sourceless_answers():
    low = amplification.brain_lookup(
        "gecikme --brain-only",
        builder=FakeBuilder(FakeCtx(0.60, "Yanıt. Kaynak: https://ornek.org/x")))
    assert low.has_answer is False and "güven" in low.shortcut_reason

    sourceless = amplification.brain_lookup(
        "gecikme --brain-only",
        builder=FakeBuilder(FakeCtx(0.90, "Kaynaksız bir iddia cümlesi.")))
    assert sourceless.has_answer is False
    assert "kaynaksız" in sourceless.shortcut_reason


def test_brain_only_card_field_is_honoured():
    class Card:
        brain_only = True
        title = "Gecikme"
        goal = "ölç"
        kind = "research"

    assert amplification.brain_only_requested(Card()) is True
    assert amplification.brain_only_requested(None, "normal araştırma") is False


# --- (d) tazelik ipuçları ---------------------------------------------------

@pytest.mark.parametrize("query", [
    "güncel fiyatları getir", "sıfırdan bir kurulum planı",
    "bugün ne oldu", "web'de tara", "internetten yeni haberleri topla",
    "2026 raporunu getir",
])
def test_freshness_hints_close_the_crag_gate(query, tmp_path):
    from entropy.memory.context_builder import (
        CognitiveContextBuilder, wants_fresh_data,
    )

    assert wants_fresh_data(query) is True

    class Node:
        content = "Eski bir bulgu."
        is_identity = 0
        provenance = "https://ornek.org/eski"

    class Memory:
        def hybrid_recall(self, q, **_kw):
            return [(Node(), 0.95)]

        def get_all_nodes(self):
            return []

    ctx = CognitiveContextBuilder(memory_system=Memory()).build(query)
    assert ctx.brain_confidence >= 0.9
    assert ctx.freshness_required is True
    assert ctx.brain_has_answer is False, "tazelik istenen sorguda beyin 'yanıt' iddia etti"


def test_stable_question_keeps_the_gate_open(tmp_path):
    from entropy.memory.context_builder import wants_fresh_data

    assert wants_fresh_data("hibrit aramanın matematiği nedir") is False


# --- (e) kind sezgisi -------------------------------------------------------

@pytest.mark.parametrize("text", [
    "vektör veritabanlarını araştır", "raporu incele", "piyasayı tara",
    "araştırma yap",
])
def test_research_verbs_are_inferred_as_research(text):
    assert amplification.infer_kind(text) == "research"


# --- (f) sistem istemi kısa devre vaat etmez --------------------------------

def test_board_tool_contract_promises_a_live_run():
    from entropy.memory.system_prompt import board_tools_section

    text = board_tools_section()
    assert "board_create" in text
    assert "CLI'ya HİÇ gitmez" not in text, \
        "istem hâlâ 'research kartı koşmaz' vaat ediyor"
    assert "CANLI" in text or "canlı" in text
