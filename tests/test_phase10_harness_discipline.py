"""
FAZ 10-A — dosya tabanlı bellek, kontrol noktası, kanıtla kapatma, kural adayı.

Doğrulanan kullanıcı kuralları:
  1. Ajan doğunca ÖNCE pano/mimari/kural dosyalarını okur (mutlak yollar
     istemin ilk satırlarında); kart değişince pano yeniden yazılır.
  2. Her modül sonunda `[KONTROL NOKTASI]` bloğu yazılır; yeniden koşu o
     bloktan sürer ve isteme eski çıktı/sohbet GİRMEZ.
  3. İşçi "bitti" diyemez: yeşil `[KANIT]` bloğu olmayan kart `done` olamaz.
  4. Keşfedilen kural belleğe yazılmaz, `[KURAL] …` satırıyla ADAY olur.
  5. Orkestratörün WebSearch yetkisi araştırma adımını açar (≤3 arama, kaynak).
  6. Koşan karta gelen yorum bir sonraki isteme `[YORUM]` olarak girer.

Hiçbir test gerçek agy/claude süreci başlatmaz: sahte köprü ya da
`subprocess.Popen` taklidiyle sürülen GERÇEK köprü kullanılır.
"""

import json
import threading
from dataclasses import replace

import pytest

from entropy.agents.desk_registry import DeskOffice, DeskRegistry
from entropy.agents.harness import (
    SPAWN_HEADER,
    OfficeHarness,
    parse_proof,
    parse_rule_candidates,
    parse_tagged_block,
)
from entropy.agents.mailbox import instruct_office, office_mailbox
from entropy.agents.registry import AgentSpec
from entropy.agents.tasks import TaskBoard, TaskCard, new_task_id


# ---------------------------------------------------------------------------
# Düzenek
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_vault(tmp_path, monkeypatch):
    from entropy.core.config import config

    monkeypatch.setattr(config, "obsidian_vault_path", tmp_path / "Vault", raising=False)
    return tmp_path / "Vault"


@pytest.fixture(autouse=True)
def clean_active_registry():
    OfficeHarness._active.clear()
    yield
    OfficeHarness._active.clear()


@pytest.fixture
def vault(tmp_path):
    return tmp_path / "Vault"


@pytest.fixture
def board(vault):
    return TaskBoard(vault_path=vault)


@pytest.fixture
def offices(vault):
    return DeskRegistry(vault_path=vault)


@pytest.fixture
def seeded(offices, tmp_path):
    workdir = tmp_path / "proje"
    workdir.mkdir()
    offices.create(DeskOffice(
        name="alfa-ofisi", purpose="Araştırır ve yazar.",
        charter="Kabul standartları: kaynaklı yaz.",
        budget_tokens=1_000_000, workdir=str(workdir),
    ))
    agents = offices.agents("alfa-ofisi")
    agents.update(AgentSpec(name="isci", role="worker", description="kod yazar",
                            provider="agy", tools_policy="read-write"))
    agents.update(AgentSpec(name="degerlendirici", role="evaluator", description="notlar",
                            provider="agy", tools_policy="read-only"))
    return offices.get("alfa-ofisi")


class _ScriptedBridge:
    """Görev kimliğine göre yanıt döndüren, istemleri kaydeden köprü."""

    provider_name = "agy"

    def __init__(self, responses):
        self.responses = list(responses)   # [(eşleşen_parça, metin, ok)]
        self.prompts = {}                  # task_id -> istem (SON koşu)
        self.order = []
        self._lock = threading.RLock()

    def send_background_task_async(self, task_id, task_name, prompt, mode=None,
                                   on_result=None, save_report=True, agent=None, **kw):
        with self._lock:
            self.prompts[task_id] = prompt
            self.order.append(task_id)
            text, ok = "", False
            for idx, (matcher, body, good) in enumerate(self.responses):
                if matcher in task_id:
                    self.responses.pop(idx)
                    text, ok = body, good
                    break
        if on_result is not None:
            on_result(text, ok)
        return task_id

    def terminate_background_task(self, task_id):
        return True

    def card_prompts(self):
        return [p for tid, p in self.prompts.items() if tid.startswith("card-")]


def _plan(*titles, agent="isci", architecture_notes=None, extra=""):
    data = {"subtasks": [
        {"title": t, "goal": f"{t} hedefi", "criteria": [f"{t} ölçütü"],
         "agent": agent, "provider": "agy", "model": ""} for t in titles
    ]}
    if architecture_notes:
        data["architecture_notes"] = architecture_notes
    return f"{extra}\n```json\n" + json.dumps(data, ensure_ascii=False) + "\n```"


def _office_card(board, title="Modülü yaz", office="alfa-ofisi"):
    return board.create(TaskCard(
        id=new_task_id(title), title=title, status="backlog", agent="orkestrator",
        provider="agy", goal="Modülü yaz ve testini koştur.",
        criteria=["Testler yeşil"], office=office,
    ))


GREEN_PROOF = (
    "Modül bitti.\n\n"
    "[KANIT]\n"
    "Komut: python -m pytest tests/test_modul.py\n"
    "Sonuç: yeşil (12 passed)\n"
    "Özet: modülün tüm testleri geçti.\n"
)

RED_PROOF = (
    "[KANIT]\n"
    "Komut: python -m pytest tests/test_modul.py\n"
    "Sonuç: kırmızı (3 failed)\n"
    "Özet: iki test kaldı.\n"
)

CHECKPOINT_OUT = (
    "[KONTROL NOKTASI]\n"
    "Yapılan: ayrıştırıcı modülü bitti\n"
    "Sonraki: yazıcı modülü\n"
    "Dosyalar: src/modul/parser.py\n"
    "Testler: pytest tests/test_parser.py — yeşil\n"
)


def _harness(board, offices, bridge, office="alfa-ofisi"):
    return OfficeHarness(office, board=board, offices=offices,
                         bridge_factory=lambda provider: bridge)


# ---------------------------------------------------------------------------
# 1. Doğuş talimatı ve pano
# ---------------------------------------------------------------------------


def test_plan_prompt_starts_with_workspace_file_paths(seeded, board, offices):
    harness = _harness(board, offices, _ScriptedBridge([]))
    card = _office_card(board)
    prompt = harness.build_plan_prompt(seeded, card)

    head = "\n".join(prompt.splitlines()[:6])
    assert head.startswith(SPAWN_HEADER)
    paths = harness.workspace_paths()
    assert str(paths["board"]) in head
    assert str(paths["architecture"]) in head
    # Mutlak yol: ajan başka bir cwd'de koşsa da dosyayı açabilmeli.
    assert paths["board"].is_absolute()


def test_board_file_is_rewritten_when_cards_change(seeded, board, offices):
    bridge = _ScriptedBridge([
        ("office-plan", _plan("Ayrıştırıcı", "Yazıcı"), True),
        ("card-", GREEN_PROOF, True),
        ("card-", GREEN_PROOF, True),
        ("office-eval", '```json\n{"grades": []}\n```', True),
    ])
    harness = _harness(board, offices, bridge)
    card = _office_card(board)
    harness.start(card.id)

    text = harness.workspace_paths()["board"].read_text(encoding="utf-8")
    assert "Ayrıştırıcı" in text and "Yazıcı" in text


def test_plan_architecture_notes_land_in_architecture_file(seeded, board, offices):
    bridge = _ScriptedBridge([
        ("office-plan", _plan("Ayrıştırıcı", architecture_notes=["Ayrıştırıcı saf fonksiyondur"]), True),
        ("card-", GREEN_PROOF, True),
        ("office-eval", '```json\n{"grades": []}\n```', True),
    ])
    harness = _harness(board, offices, bridge)
    harness.start(_office_card(board).id)

    text = harness.workspace_paths()["architecture"].read_text(encoding="utf-8")
    assert "Ayrıştırıcı saf fonksiyondur" in text


def test_subcard_prompt_leads_with_spawn_and_carries_discipline(seeded, board, offices):
    bridge = _ScriptedBridge([
        ("office-plan", _plan("Ayrıştırıcı"), True),
        ("card-", GREEN_PROOF, True),
        ("office-eval", '```json\n{"grades": []}\n```', True),
    ])
    harness = _harness(board, offices, bridge)
    harness.start(_office_card(board).id)

    prompt = bridge.card_prompts()[0]
    assert prompt.lstrip().startswith(SPAWN_HEADER)
    assert str(harness.workspace_paths()["board"]) in prompt
    # Disiplin blokları: kontrol noktası, kanıt, kural adayı.
    assert "[KONTROL NOKTASI]" in prompt
    assert "[KANIT" in prompt
    assert "[KURAL]" in prompt


# ---------------------------------------------------------------------------
# 2. Kontrol noktası disiplini
# ---------------------------------------------------------------------------


def test_checkpoint_is_written_and_resume_replaces_old_output(seeded, board, offices):
    """Yeniden koşan kartın istemine kontrol noktası girer, eski çıktı girmez."""
    marker = "ESKİ ÇIKTININ TAMAMI"
    first = f"{marker}\n\n{CHECKPOINT_OUT}\n{RED_PROOF}"
    bridge = _ScriptedBridge([
        ("office-plan", _plan("Ayrıştırıcı"), True),
        ("card-", first, True),
        ("office-eval", "__grades__", True),
        ("card-", GREEN_PROOF, True),
        ("office-eval", '```json\n{"grades": []}\n```', True),
    ])
    harness = _harness(board, offices, bridge)
    parent = _office_card(board)

    # Değerlendirici düşük not verince kart bir kez yeniden koşar.
    def _grades(_text, _ok=True):
        rows = [{"id": cid, "grade": 0.2, "verdict": "kanıt kırmızı", "missing": ["yeşil test"]}
                for cid in board.get(parent.id).children]
        return "```json\n" + json.dumps({"grades": rows}) + "\n```"

    original = bridge.send_background_task_async

    def _patched(task_id, task_name, prompt, mode=None, on_result=None, **kw):
        if "office-eval" in task_id and "__grades__" in [r[1] for r in bridge.responses]:
            bridge.prompts[task_id] = prompt
            for idx, (matcher, body, good) in enumerate(list(bridge.responses)):
                if matcher in task_id and body == "__grades__":
                    bridge.responses.pop(idx)
                    break
            if on_result is not None:
                on_result(_grades(prompt), True)
            return task_id
        return original(task_id, task_name, prompt, mode=mode, on_result=on_result, **kw)

    bridge.send_background_task_async = _patched
    harness.start(parent.id)

    child_id = board.get(parent.id).children[0]
    child = board.get(child_id)
    assert child.checkpoint, "kontrol noktası yolu karta yazılmadı"
    assert "ayrıştırıcı modülü bitti" in \
        open(child.checkpoint, encoding="utf-8").read().lower()

    second = bridge.prompts[f"card-{child_id}"]
    assert "[KALDIĞIN YER" in second
    assert marker not in second, "yeniden koşuya eski çıktı sızdı"


# ---------------------------------------------------------------------------
# 3. Kanıtla kapatma
# ---------------------------------------------------------------------------


def _run_single(board, offices, child_output, intent=""):
    bridge = _ScriptedBridge([
        ("office-plan", _plan("Ayrıştırıcı"), True),
        ("card-", child_output, True),
        ("office-eval", '```json\n{"grades": []}\n```', True),
    ])
    harness = _harness(board, offices, bridge)
    parent = _office_card(board)
    if intent:
        # Yazma niyeti alt karta miras kalmıyor; plandan sonra elle işaretlemek
        # yerine kartı koşmadan önce yakalamak için bridge'i sırayla kullanıyoruz.
        harness._orig_pump = harness._pump

        def _pump(card_id, _h=harness, _intent=intent):
            card = board.get(card_id)
            for cid in (card.children if card else []):
                child = board.get(cid)
                if child is not None and child.status == "backlog" and not child.intent:
                    board.update(replace(child, intent=_intent))
            return _h._orig_pump(card_id)

        harness._pump = _pump
    harness.start(parent.id)
    return harness, board.get(board.get(parent.id).children[0])


def test_card_without_proof_cannot_be_done(seeded, board, offices):
    _, child = _run_single(board, offices, "Bitirdim, her şey tamam.", intent="write")
    assert child.status == "review"
    assert "kanıt eksik" in (child.notes or "").lower()
    assert not child.proof


def test_card_with_red_proof_cannot_be_done(seeded, board, offices):
    _, child = _run_single(board, offices, RED_PROOF, intent="write")
    assert child.status == "review"
    assert "kanıt kırmızı" in (child.notes or "").lower()


def test_card_with_green_proof_is_done(seeded, board, offices):
    _, child = _run_single(board, offices, GREEN_PROOF, intent="write")
    assert child.status == "done"
    assert "pytest" in child.proof


def test_research_only_card_accepts_produced_path_as_proof(seeded, board, offices):
    """Yazma niyeti olmayan kartta kanıt = üretilen dosya/rapor yolu."""
    output = (
        "Araştırma bitti.\n\n"
        "[KANIT]\n"
        "Çıktı: reports/pazar-arastirmasi.md\n"
        "Özet: bulgular rapora yazıldı.\n"
    )
    _, child = _run_single(board, offices, output)  # intent yok -> okuma
    assert child.status == "done"
    assert "reports/pazar-arastirmasi.md" in child.proof


def test_eval_prompt_has_proof_section_and_criterion(seeded, board, offices):
    harness = _harness(board, offices, _ScriptedBridge([]))
    parent = _office_card(board)
    child = board.create(TaskCard(id=new_task_id("Alt"), title="Alt", office="alfa-ofisi",
                                  parent=parent.id, agent="isci",
                                  summary="çıktı", proof="Sonuç: yeşil (12 passed)"))
    prompt = harness.build_eval_prompt(seeded, parent, [child])
    assert "Kanıt:" in prompt and "Sonuç: yeşil" in prompt
    assert "[ÖLÇÜT — KANIT]" in prompt


# ---------------------------------------------------------------------------
# 4. Kural adayları
# ---------------------------------------------------------------------------


def test_rule_lines_become_candidates_not_memory(seeded, board, offices, vault):
    from entropy.memory import promoted_rules

    rule = "Kart özetleri her zaman Türkçe yazılmalı ve kaynak bağlantısı içermeli."
    output = f"{GREEN_PROOF}\n[KURAL] {rule}\n"
    _run_single(board, offices, output, intent="write")

    candidates = promoted_rules.list_rules("alfa-ofisi", vault_path=vault)
    texts = [r.text for r in candidates]
    assert any(rule[:30] in t for t in texts)
    # Aday ONAYLI değildir: onayı kullanıcı verir.
    assert all(r.status != "promoted" for r in candidates)
    # Onaylı kurallar bölümü hâlâ boş: ajan belleğe kural yazamadı.
    assert promoted_rules.rules_section("alfa-ofisi", vault_path=vault) == ""


def test_rule_candidates_emit_rules_updated_when_signal_exists(seeded, board, offices):
    from entropy.core import event_bus

    seen = []
    signal = getattr(event_bus.bus, "rules_updated", None)
    if signal is None:
        pytest.skip("event_bus.rules_updated henüz yok (ui katmanı ekleyecek)")
    signal.connect(lambda office, count: seen.append((office, count)))

    harness = _harness(board, offices, _ScriptedBridge([]))
    harness.collect_rule_candidates(
        "isci", "[KURAL] Tüm ofis raporları kaynak bağlantısıyla kapanır.", source="x")
    assert seen and seen[0][0] == "alfa-ofisi"


def test_parse_helpers_survive_without_memory_layer():
    """Ayrıştırıcılar bellek katmanından bağımsızdır (guard sözleşmesi)."""
    assert parse_tagged_block(CHECKPOINT_OUT, "[KONTROL NOKTASI]").startswith("Yapılan")
    assert parse_proof(GREEN_PROOF)["green"] is True
    assert parse_proof(RED_PROOF)["green"] is False
    assert parse_proof("kanıt yok") is None
    assert parse_rule_candidates("[KURAL] Kaynak göster\nnormal satır") == ["Kaynak göster"]


# ---------------------------------------------------------------------------
# 5. Orkestratör araştırma düzeltmesi
# ---------------------------------------------------------------------------


def test_orchestrator_web_tools_enable_research_step(seeded, board, offices):
    harness = _harness(board, offices, _ScriptedBridge([]))
    # Kadroda yalnızca `read-write` üye var: eski kontrol False dönüyordu.
    assert harness._can_web_search() is True
    prompt = harness.build_plan_prompt(seeded, _office_card(board))
    assert "[ARAŞTIRMA NOTU]" in prompt
    assert "En çok 3 arama" in prompt
    assert "KAYNAK BAĞLANTISINI" in prompt
    assert '"source"' in prompt


def test_research_note_source_is_stored_with_finding(seeded, board, offices, vault):
    from entropy.memory.office_graph import OfficeGraph

    plan = "```json\n" + json.dumps({
        "subtasks": [{"title": "Ayrıştırıcı", "goal": "g", "criteria": ["c"],
                      "agent": "isci", "provider": "agy", "model": ""}],
        "research_notes": [{"title": "Rakip fiyatı düştü", "body": "Sektör raporu",
                            "source": "https://ornek.example/rapor"}],
    }, ensure_ascii=False) + "\n```"
    bridge = _ScriptedBridge([
        ("office-plan", plan, True),
        ("card-", GREEN_PROOF, True),
        ("office-eval", '```json\n{"grades": []}\n```', True),
    ])
    _harness(board, offices, bridge).start(_office_card(board).id)

    graph = OfficeGraph("alfa-ofisi", vault)
    bodies = [n.get("body", "") for n in graph.nodes.values() if n.get("kind") == "bulgu"]
    assert any("https://ornek.example/rapor" in b for b in bodies)


# ---------------------------------------------------------------------------
# 6. Koşan karta yorum
# ---------------------------------------------------------------------------


def test_card_comment_enters_next_run_and_is_marked_read(seeded, board, offices, vault):
    bridge = _ScriptedBridge([
        ("office-plan", _plan("Ayrıştırıcı"), True),
        ("card-", GREEN_PROOF, True),
        ("office-eval", '```json\n{"grades": []}\n```', True),
    ])
    harness = _harness(board, offices, bridge)
    parent = _office_card(board)
    instruct_office("alfa-ofisi", "sürümü 3.11 varsay", task_id=parent.id, vault_path=vault)

    harness.start(parent.id)

    prompt = bridge.card_prompts()[0]
    assert "[YORUM" in prompt and "sürümü 3.11 varsay" in prompt
    # Kart durmaz: koşu tamamlandı ve mesaj okundu işaretlendi.
    assert board.get(parent.id).status == "review"
    box = office_mailbox("alfa-ofisi", vault_path=vault)
    assert all(m.read for m in box.list(kind="instruction"))


def test_card_scoped_comment_does_not_leak_into_plan_prompt(seeded, board, offices, vault):
    """Karta yazılan yorum plan istemine `[TALİMAT]` olarak girmez."""
    bridge = _ScriptedBridge([
        ("office-plan", _plan("Ayrıştırıcı"), True),
        ("card-", GREEN_PROOF, True),
        ("office-eval", '```json\n{"grades": []}\n```', True),
    ])
    harness = _harness(board, offices, bridge)
    parent = _office_card(board)
    instruct_office("alfa-ofisi", "kart yorumu", task_id=parent.id, vault_path=vault)
    instruct_office("alfa-ofisi", "ofis talimatı", vault_path=vault)

    harness.start(parent.id)
    plan_prompt = bridge.prompts[f"office-plan-{parent.id}"]
    assert "ofis talimatı" in plan_prompt
    assert "kart yorumu" not in plan_prompt


# ---------------------------------------------------------------------------
# Gerçek köprü yolu (Popen taklidi) — sahte köprüyle geçen test yetmez
# ---------------------------------------------------------------------------


class _FakeProc:
    def __init__(self, lines, returncode=0):
        self._lines = list(lines)
        self.returncode = returncode
        self.pid = 999010
        self.stdin = None
        self.stdout = self

    def readline(self):
        return self._lines.pop(0) if self._lines else ""

    def close(self):
        pass

    def wait(self, timeout=None):
        return self.returncode

    def poll(self):
        return self.returncode


def _agy_lines(text):
    return [
        json.dumps({"event": "result", "result": {
            "response": text,
            "usage": {"input_tokens": 50, "output_tokens": 10, "total_tokens": 60},
        }}) + "\n",
    ]


def _wait_until(predicate, timeout=20.0):
    import time

    end = time.time() + timeout
    while time.time() < end:
        try:
            if predicate():
                return True
        except Exception:
            pass
        time.sleep(0.05)
    return False


def test_real_bridge_subcard_prompt_carries_spawn_and_proof_rules(
        seeded, board, offices, tmp_path, monkeypatch):
    """
    GERÇEK `AgyProcessBridge.send_background_task_async` yolu (Popen taklidi):
    alt kart istemi doğuş talimatıyla başlar, kanıt kuralını taşır ve yeşil
    kanıtlı kart `done` olur. Kota harcanmaz.
    """
    from entropy.core.agy_bridge import AgyProcessBridge
    from entropy.core.task_ledger import TaskLedger

    monkeypatch.setattr("entropy.core.agy_bridge.task_ledger",
                        TaskLedger(db_path=tmp_path / "ledger.db"))
    bridge = AgyProcessBridge()
    bridge.active_project_dir = tmp_path

    parent = _office_card(board)
    prompts = []
    finished = threading.Event()

    def fake_popen(cmd, **kwargs):
        joined = " ".join(str(c) for c in cmd)
        prompts.append(joined)
        if len(prompts) == 1:
            return _FakeProc(_agy_lines(_plan("Ayrıştırıcı")))
        if "degerlendirici" in joined:
            finished.set()
            return _FakeProc(_agy_lines('```json\n{"grades": []}\n```'))
        return _FakeProc(_agy_lines(GREEN_PROOF))

    monkeypatch.setattr("entropy.core.agy_bridge.subprocess.Popen", fake_popen)

    harness = OfficeHarness("alfa-ofisi", board=board, offices=offices,
                            bridge_factory=lambda provider: bridge)
    assert harness.start(parent.id) is True
    assert _wait_until(lambda: board.get(parent.id).status in ("review", "failed"))

    child_prompt = next(p for p in prompts if "GÖREV SÖZLEŞMESİ" in p)
    assert SPAWN_HEADER in child_prompt
    assert str(harness.workspace_paths()["board"]) in child_prompt
    assert "[KANIT" in child_prompt and "[KONTROL NOKTASI]" in child_prompt

    child = board.get(board.get(parent.id).children[0])
    assert child.status == "done" and "pytest" in child.proof
