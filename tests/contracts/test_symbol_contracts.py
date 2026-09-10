"""
Faz 12-A: slash komutları ile hafıza/ajan katmanı arasındaki SEMBOL sözleşmesi.

Araştırma A §3.3 iki sessiz kopukluk ölçtü:
  * `/memory merge` var olmayan `gray_merge.run` adını içe aktarıyor, `except
    Exception` bunu yutuyor ve kullanıcıya "modül henüz kurulu değil" yalanını
    döndürüyordu (modül kurulu ve testleri yeşildi);
  * `/wiki compile` `compile_skill(name, turns=N)` çağırıyor, `TypeError`
    yutuluyor ve komut köprüsüz `compile_skill(name)`'e geriliyordu.

Bu test kopukluğu **import anında** yakalar: `core/slash_commands.py` içindeki
her `from entropy.brain.* import ...` / `from entropy.agents.* import ...`
girdisi gerçekten çözülmeli, ve kritik üç çağrının parametre adları
`inspect.signature` ile doğrulanmalı.
"""

from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path

import pytest

SLASH_PATH = Path(__file__).resolve().parents[2] / "src" / "entropy" / "core" / "slash_commands.py"


def _imported_symbols() -> list[tuple[str, str]]:
    """`slash_commands.py`ın içe aktardığı (modül, sembol) çiftleri."""
    tree = ast.parse(SLASH_PATH.read_text(encoding="utf-8"))
    pairs: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0:
            module = node.module or ""
            if not (module.startswith("entropy.brain") or module.startswith("entropy.agents")):
                continue
            for alias in node.names:
                pairs.append((module, alias.name))
    return sorted(set(pairs))


def test_slash_commands_import_real_symbols():
    """Her içe aktarılan sembol modülünde GERÇEKTEN var (yutulan ImportError yok)."""
    pairs = _imported_symbols()
    assert pairs, "slash_commands.py hiç hafıza/ajan sembolü içe aktarmıyor — tarama bozuk"
    eksik = []
    for module, symbol in pairs:
        mod = importlib.import_module(module)
        if hasattr(mod, symbol):
            continue
        try:
            # `from entropy.agents import pr_flow` gibi alt modül içe aktarımları.
            importlib.import_module(f"{module}.{symbol}")
        except ImportError:
            eksik.append(f"{module}.{symbol}")
    assert eksik == [], f"slash_commands.py var olmayan sembolleri çağırıyor: {eksik}"


def test_gray_merge_run_alias_does_not_exist():
    """Yanlış ad (`run`) hâlâ yok; sözleşme `run_merge_round`."""
    gm = importlib.import_module("entropy.brain.gray_merge")
    assert hasattr(gm, "run_merge_round")
    assert not hasattr(gm, "run"), (
        "gray_merge.run geri eklenmiş: sözleşme tek ad (run_merge_round) olmalı"
    )


@pytest.mark.parametrize(
    "module, symbol, expected",
    [
        ("entropy.brain.gray_merge", "run_merge_round",
         ("memory", "send_prompt", "limit", "gate", "graph")),
        ("entropy.brain.dream", "dream_and_consolidate",
         ("memory", "send_prompt", "vault_path")),
        ("entropy.brain.wiki", "compile_skill",
         ("skill", "bridge", "budget_turns", "vault_path")),
        ("entropy.brain.distiller", "PlaybookDistiller", ()),
    ],
)
def test_call_signatures_match_contract(module, symbol, expected):
    obj = getattr(importlib.import_module(module), symbol)
    if not expected:
        assert obj is not None
        return
    params = inspect.signature(obj).parameters
    eksik = [name for name in expected if name not in params]
    assert eksik == [], f"{module}.{symbol} imzasında eksik parametreler: {eksik}"


def test_wiki_compile_rejects_legacy_turns_kwarg():
    """Eski (yutulmuş) çağrı biçimi `turns=` artık sessizce geçmemeli."""
    from entropy.brain.wiki import compile_skill

    assert "turns" not in inspect.signature(compile_skill).parameters


def test_slash_commands_do_not_swallow_module_absence():
    """`except Exception` ile 'modül kurulu değil' yalanı kalmadı."""
    text = SLASH_PATH.read_text(encoding="utf-8")
    assert "henüz kurulu değil" not in text


def test_wiki_and_memory_handlers_accept_bridge():
    """`_handle_wiki` / `_handle_memory` köprüyü çağırandan alır."""
    from entropy.core import slash_commands as sc

    assert "bridge" in inspect.signature(sc._handle_wiki).parameters
    assert "bridge" in inspect.signature(sc._handle_wiki_compile).parameters
    assert "bridge" in inspect.signature(sc._handle_memory).parameters


def test_bridge_prompt_adapter_contract():
    """Uyarlayıcı `send_prompt(prompt) -> str` üretir ve köprüsüz açıkça patlar."""
    from entropy.core.bridge_prompt import BridgeUnavailable, make_send_prompt

    class _Bare:
        pass

    with pytest.raises(BridgeUnavailable):
        make_send_prompt(_Bare())

    sent: dict = {}

    class _Fake:
        def send_background_task_async(self, task_id, task_name, prompt, **kw):
            sent["task_id"] = task_id
            sent["prompt"] = prompt
            sent["kwargs"] = kw
            kw["on_result"]("cevap", True)

    send = make_send_prompt(_Fake(), label="Test turu")
    assert send("merhaba") == "cevap"
    assert sent["prompt"] == "merhaba"
    # Ara ürün: kasaya rapor yazılmaz, plan kipi açılmaz.
    assert sent["kwargs"]["save_report"] is False
    assert sent["kwargs"]["mode"] == "accept-edits"
