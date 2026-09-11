"""Faz 13-D: hafıza denetçisinin silme yolundaki modül adları gerçek olmalı.

13-C'ye kadar yedek aday listesi taşınma öncesi adları taşıyordu
(`entropy.brain.cognitive_memory`), bu yüzden döngü hiçbir zaman bir
`delete_memory` bulamıyor ve silme sessizce ham SQL yoluna düşüyordu.
"""

import importlib

import pytest

from entropy.ui.widgets.memory_inspector_dialog import DELETE_MEMORY_MODULES


def test_delete_memory_module_candidates_are_importable():
    assert DELETE_MEMORY_MODULES, "aday listesi boş olmamalı"
    for module_path in DELETE_MEMORY_MODULES:
        importlib.import_module(module_path)


@pytest.mark.parametrize("stale", ["entropy.brain.cognitive_memory", "entropy.core.cognitive_memory"])
def test_stale_module_names_are_gone(stale):
    assert stale not in DELETE_MEMORY_MODULES
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(stale)


def test_primary_delete_entry_point_is_the_memory_layer():
    """Silme, bellek katmanının tek girişini (`delete_memory`) kullanmalı."""
    from entropy.brain.supabase.cognitive_memory import CognitiveMemorySystem

    assert callable(getattr(CognitiveMemorySystem, "delete_memory", None))
