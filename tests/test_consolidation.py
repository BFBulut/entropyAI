"""
Bilişsel konsolidasyon (rüya) testleri.

Önceki sürüm içeriksiz "N bölümsel etkileşimden damıtıldı" etiketleri yazıyordu
(0.85 önemle; recall'da gerçek bilgiyi bastırıyordu). Doğrulanan davranış:
- Etiket düğümleri tespit edilip temizlenir.
- Yeni özet gerçek anı içeriği taşır ve etiket biçiminde değildir.
- AGY sentez prompt'u yalnızca yeterli anı varken üretilir; çıktı semantic düğüm olur.
"""

import time

import pytest

from entropy.brain.supabase.cognitive_memory import CognitiveMemorySystem


@pytest.fixture
def mem(tmp_path):
    return CognitiveMemorySystem(db_path=tmp_path / "mem.db")


def test_placeholder_consolidations_are_purged(mem):
    mem.record_memory(
        category="semantic",
        content="Konsolide Bilişsel Özet (2026-09-04): 3 bölümsel etkileşimden damıtıldı.",
        importance=0.85,
        metadata={"source": "dream_consolidation"},
    )
    keep, _ = mem.record_memory(
        category="semantic",
        content="Konsolide öğrenimler: müşteri raporları önce teknik SEO ile başlar.",
        importance=0.8,
        metadata={"source": "dream_consolidation_agy"},
    )
    removed = mem.purge_placeholder_consolidations()
    assert removed == 1
    ids = {n.id for n in mem.get_all_nodes()}
    assert keep.id in ids


def test_dream_writes_real_content_not_label(mem):
    now = time.time()
    for i in range(3):
        mem.record_memory(category="episodic", content=f"Kullanıcı canivopets için buyume raporu istedi {i}", importance=0.5)
    rules = mem.dream_and_consolidate()
    assert rules, "en az iki anı varken özet üretilmeli"
    summary = rules[0]
    assert "canivopets" in summary
    assert "etkileşimden damıtıldı" not in summary
    node = next(n for n in mem.get_all_nodes() if (n.metadata or {}).get("source") == "dream_consolidation")
    assert node.importance < 0.85, "özet, gerçek bilgiyi bastıracak kadar yüksek önemle kaydedilmemeli"


def test_dream_is_noop_with_too_few_memories(mem):
    mem.record_memory(category="episodic", content="tek anı", importance=0.5)
    assert mem.dream_and_consolidate() == []


def test_consolidation_prompt_and_store(mem):
    assert mem.build_consolidation_prompt() is None
    mem.record_memory(category="episodic", content="Slayt istenirken önce araştırma raporu okunmalı", importance=0.7)
    mem.record_memory(category="episodic", content="Finans yeteneği bilanço olmadan çalıştırılmamalı", importance=0.6)

    prompt = mem.build_consolidation_prompt()
    assert prompt and "KONSOLİDASYON" in prompt
    assert "Slayt istenirken" in prompt and "Finans yeteneği" in prompt

    assert mem.store_consolidation("kısa") is None, "boş/çok kısa sentez kaydedilmemeli"
    node = mem.store_consolidation("- Slayt üretmeden önce ilgili araştırma raporu okunur.\n- Finans analizi bilanço gerektirir.")
    assert node is not None
    assert node.category == "semantic"
    assert (node.metadata or {}).get("source") == "dream_consolidation_agy"
