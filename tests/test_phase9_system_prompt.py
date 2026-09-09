"""
Faz 9 · iş 9.3 + Ek-1 + Ek-2 testleri.

Kapsam:
  * `memory/system_prompt.build_system_prompt` — bölüm sırası, sağlayıcıya göre
    araç sözleşmesi, karakter tavanı, kırpma önceliği, determinizm.
  * `memory/obsidian/vault_manager.list_reports(cache=True)` — imza önbelleği.
  * `memory/vault_hygiene.archive_office` — wiki sorgu sayfası + posta izleri.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from entropy.memory import system_prompt as sp
from entropy.memory.obsidian.vault_manager import ObsidianVaultManager, clear_report_cache
from entropy.memory.vault_hygiene import archive_office, office_residue


# --------------------------------------------------------------- 9.3 istem


def _build(kind="chat", provider="claude", **kw):
    return sp.build_system_prompt(kind, provider=provider, **kw)


def test_identity_is_first_and_names_entropy():
    text = _build(query="merhaba")
    assert text.startswith("[KİMLİK]"), text[:80]
    assert "Entropy AI" in text
    assert "Türkçe" in text


def test_tool_contract_only_on_claude():
    claude = _build(provider="claude", query="dosyayı düzenle")
    agy = _build(provider="agy", query="dosyayı düzenle")
    assert "[ARAÇ SÖZLEŞMESİ]" in claude
    assert "[ARAÇ SÖZLEŞMESİ]" not in agy
    # Varsayılan istem düştüğü için en kritik kural açıkça yazılmalı.
    assert "Read ile oku" in claude
    assert "old_string" in claude
    assert "MUTLAK" in claude


def test_tool_contract_mentions_entropy_slash_commands():
    text = _build(provider="claude", query="x")
    assert "/distill" in text and "/desk" in text
    assert "ENTROPY'nindir" in text


def test_section_order_is_stable():
    text = sp.build_system_prompt(
        "chat",
        provider="claude",
        query="rapor",
        history_summary="- Kullanıcı: selam\n- Entropy: merhaba",
    )
    idx_identity = text.find("[KİMLİK]")
    idx_tools = text.find("[ARAÇ SÖZLEŞMESİ]")
    idx_history = text.find("[ÖNCEKİ SOHBET ÖZETİ]")
    assert idx_identity < idx_tools < idx_history


def test_card_mode_injects_agent_spec():
    spec = {
        "name": "arastirmaci",
        "role": "Web araştırması yapar",
        "tools": ["Read", "WebSearch"],
        "system_prompt": "Kaynaksız iddia yazma.",
    }
    card = sp.build_system_prompt("card", provider="claude", agent_spec=spec, query="ara")
    assert "[BU KOŞUNUN AJANI]" in card
    assert "arastirmaci" in card and "WebSearch" in card
    assert "Kaynaksız iddia yazma." in card
    # Arka plan kartında Entropy payı 0 olmamalı (araştırma A §1.3).
    assert len(card) > 500
    # Sohbet kipinde kart künyesi hiç yazılmaz.
    chat = sp.build_system_prompt("chat", provider="claude", agent_spec=spec, query="ara")
    assert "[BU KOŞUNUN AJANI]" not in chat


def test_never_exceeds_max_chars():
    long_summary = "- Kullanıcı: " + ("uzun mesaj " * 400)
    for limit in (600, 1500, 4000, 8000):
        text = sp.build_system_prompt(
            "chat",
            provider="claude",
            query="entropy hafıza raporları",
            history_summary=long_summary,
            max_chars=limit,
        )
        assert len(text) <= limit, f"{limit} sınırı aşıldı: {len(text)}"


def test_trim_priority_identity_survives_smallest_budget():
    text = sp.build_system_prompt(
        "chat",
        provider="claude",
        query="rapor",
        history_summary="özet " * 200,
        max_chars=900,
    )
    assert "[KİMLİK]" in text
    assert "[ÖNCEKİ SOHBET ÖZETİ]" not in text


def test_deterministic_for_same_input():
    kw = dict(provider="claude", query="hafıza", history_summary="- Entropy: tamam")
    assert sp.build_system_prompt("chat", **kw) == sp.build_system_prompt("chat", **kw)


def test_no_forbidden_brand():
    text = _build(kind="card", query="x", agent_spec={"name": "a", "role": "b"})
    assert "".join(("mur", "atify")) not in text.lower()


def test_unknown_kind_falls_back_to_chat():
    assert sp.build_system_prompt("garip", provider="claude", query="x").startswith("[KİMLİK]")


def test_section_lengths_reports_totals():
    lens = sp.section_lengths("chat", provider="claude", query="rapor")
    assert lens["total"] > 0
    assert lens["identity"] > 100
    assert lens["tools"] > 500
    assert sum(v for k, v in lens.items() if k != "total") <= lens["total"]


def test_no_dedicated_builder_for_desk_orchestrators():
    """Desk orkestratörleri Entropy'yi bilmez; bu modülde onlara yol yoktur."""
    assert sp.VALID_KINDS == ("chat", "card")
    assert not any("orchestrator" in n.lower() for n in dir(sp))


# ------------------------------------------------------------- Ek-1 önbellek


def _make_reports(vault: Path, count: int) -> None:
    reports = vault / "Entropy" / "Reports"
    reports.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        (reports / f"rapor_{i:04d}.md").write_text(
            f"---\ntype: report\n---\n# Rapor {i}\nGövde.\n", encoding="utf-8"
        )


def test_list_reports_cache_returns_same_entries(tmp_path):
    _make_reports(tmp_path, 40)
    clear_report_cache(tmp_path)
    vm = ObsidianVaultManager(vault_path=tmp_path)
    first = vm.list_reports(cache=True)
    second = vm.list_reports(cache=True)
    assert len(first) == 40
    assert [e["path"] for e in first] == [e["path"] for e in second]
    assert [e["kind"] for e in first] == [e["kind"] for e in second]


def test_list_reports_cache_sees_new_and_changed_files(tmp_path):
    _make_reports(tmp_path, 5)
    clear_report_cache(tmp_path)
    vm = ObsidianVaultManager(vault_path=tmp_path)
    assert len(vm.list_reports(cache=True)) == 5

    (tmp_path / "Entropy" / "Reports" / "yeni.md").write_text(
        "---\ntype: report\n---\nyeni\n", encoding="utf-8"
    )
    assert len(vm.list_reports(cache=True)) == 6

    # Tür ön bilgide değişirse önbellek bunu görmeli (imza boyutla da değişir).
    target = tmp_path / "Entropy" / "Reports" / "rapor_0000.md"
    target.write_text("---\ntype: session\n---\n# Rapor 0\nGövde uzatıldı.\n", encoding="utf-8")
    kinds = {e["path"]: e["kind"] for e in vm.list_reports(cache=True)}
    assert kinds[str(target)] == "session"


def test_list_reports_cache_second_call_is_fast(tmp_path):
    """700 raporlu kasada ikinci çağrı ≤ 30 ms (ön bilgi yeniden okunmaz)."""
    _make_reports(tmp_path, 700)
    clear_report_cache(tmp_path)
    vm = ObsidianVaultManager(vault_path=tmp_path)
    t0 = time.perf_counter()
    first = vm.list_reports(cache=True)
    cold = (time.perf_counter() - t0) * 1000
    t1 = time.perf_counter()
    second = vm.list_reports(cache=True)
    warm = (time.perf_counter() - t1) * 1000
    assert len(first) == len(second) == 700
    print(f"\n[ölçüm] 700 rapor: ilk={cold:.1f} ms, ikinci={warm:.1f} ms")
    assert warm <= 30.0, f"ikinci çağrı {warm:.1f} ms (>30 ms)"


def test_list_reports_without_cache_still_works(tmp_path):
    _make_reports(tmp_path, 3)
    vm = ObsidianVaultManager(vault_path=tmp_path)
    assert len(vm.list_reports()) == 3
    assert len(vm.get_research_reports(kinds=["report"])) == 3


# ------------------------------------------------------- Ek-2 ofis arşivleme


def _seed_office(tmp_path: Path, office: str = "dogrulama") -> Path:
    root = tmp_path / "Entropy"
    # Faz 10-B: Desk verisi kasa kokunde (`<kasa>/Desk/Offices`); ofis klasoru
    # artik `Entropy/` altinda DEGIL.
    off = tmp_path / "Desk" / "Offices" / office
    (off / "reports").mkdir(parents=True, exist_ok=True)
    (off / "reports" / "20260909-171913-readme-ozeti.md").write_text(
        "---\ntype: office_report\n---\nrapor\n", encoding="utf-8"
    )

    queries = root / "Wiki" / "queries"
    queries.mkdir(parents=True, exist_ok=True)
    (queries / f"2026-09-09-{office}-readme-ozeti.md").write_text(
        "sorgu sayfası\n", encoding="utf-8"
    )
    # Ofis adını cümle içinde geçiren ama alan olarak taşımayan kullanıcı sayfası.
    (queries / "2026-09-09-elle-yazilmis.md").write_text(
        f"{office} hakkında elle not\n", encoding="utf-8"
    )

    inbox = root / "Inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / "20260909-135250-aaa.json").write_text(
        json.dumps({"id": "aaa", "from": office, "to": "entropy", "parts": []}),
        encoding="utf-8",
    )
    (inbox / "20260909-135251-bbb.json").write_text(
        json.dumps({"id": "bbb", "from": "desk", "to": "entropy", "parts": []}),
        encoding="utf-8",
    )
    return off


def test_office_residue_matches_only_office_pages(tmp_path):
    _seed_office(tmp_path)
    res = office_residue("dogrulama", vault_path=tmp_path)
    assert len(res["queries"]) == 1
    assert "2026-09-09-dogrulama-readme-ozeti.md" in res["queries"][0]
    assert len(res["mail"]) == 1
    assert res["mail"][0].endswith("aaa.json")


def test_archive_office_dry_run_moves_nothing(tmp_path):
    off = _seed_office(tmp_path)
    out = archive_office("dogrulama", vault_path=tmp_path, dry_run=True, date="2026-09-09")
    assert out["dry_run"] is True
    assert out["residue"]["moved"] == []
    assert len(out["residue"]["planned"]) == 2
    assert off.is_dir()
    assert (tmp_path / "Entropy" / "Wiki" / "queries" / "2026-09-09-dogrulama-readme-ozeti.md").exists()


def test_archive_office_moves_folder_queries_and_mail(tmp_path):
    off = _seed_office(tmp_path)
    out = archive_office("dogrulama", vault_path=tmp_path, dry_run=False, date="2026-09-09")

    archive = tmp_path / "Entropy" / "_archive" / "2026-09-09"
    assert not off.exists(), "ofis klasörü taşınmadı"
    assert (archive / "dogrulama").is_dir()
    assert (archive / "dogrulama-residue" / "queries" / "2026-09-09-dogrulama-readme-ozeti.md").is_file()
    assert (archive / "dogrulama-residue" / "mail" / "20260909-135250-aaa.json").is_file()
    assert len(out["residue"]["moved"]) == 2

    # Kullanıcının elle yazdığı sayfa ve ilgisiz posta yerinde kalır.
    assert (tmp_path / "Entropy" / "Wiki" / "queries" / "2026-09-09-elle-yazilmis.md").exists()
    assert (tmp_path / "Entropy" / "Inbox" / "20260909-135251-bbb.json").exists()


def test_archived_office_report_leaves_report_feed(tmp_path):
    """Teşhis §8: arşivden sonra ofisin sorgu sayfası künyesi de düşmeli."""
    _seed_office(tmp_path)
    clear_report_cache(tmp_path)
    vm = ObsidianVaultManager(vault_path=tmp_path)
    before = {Path(e["path"]).name for e in vm.list_reports()}
    assert "2026-09-09-dogrulama-readme-ozeti.md" in before

    archive_office("dogrulama", vault_path=tmp_path, dry_run=False, date="2026-09-09")
    clear_report_cache(tmp_path)
    after = {Path(e["path"]).name for e in vm.list_reports()}
    assert "2026-09-09-dogrulama-readme-ozeti.md" not in after
    assert "20260909-171913-readme-ozeti.md" not in after


def test_archive_office_unknown_name_is_noop(tmp_path):
    out = archive_office("", vault_path=tmp_path, dry_run=False)
    assert out["count"] == 0


def test_archive_office_prunes_dangling_wiki_index_link(tmp_path):
    """
    Sorgu sayfasi arsive gidince `Wiki/index.md` bagi da temizlenir.

    Gercek kasada olculdu: `dogrulama` ofisinin sorgu sayfasi arsive tasindi
    ama `index.md` icindeki `[[2026-09-09-dogrulama-readme-ozeti]]` satiri
    kaldi ve Obsidian'da kirik bag olarak duruyordu. `log.md` bir OLAY
    gunlugudur, bilerek dokunulmaz.
    """
    from entropy.memory.vault_hygiene import prune_wiki_index

    _seed_office(tmp_path)
    wiki = tmp_path / "Entropy" / "Wiki"
    (wiki / "index.md").write_text(
        "# Wiki\n\n"
        "- [[2026-09-09-dogrulama-readme-ozeti]] — dogrulama: README ozeti\n"
        "- [[2026-09-09-elle-yazilmis]] — elle not\n",
        encoding="utf-8",
    )
    (wiki / "log.md").write_text(
        "- [2026-09-09 17:26] query: dogrulama: README ozeti\n", encoding="utf-8"
    )

    archive_office("dogrulama", vault_path=tmp_path, dry_run=False, date="2026-09-09")

    index = (wiki / "index.md").read_text(encoding="utf-8")
    assert "2026-09-09-dogrulama-readme-ozeti" not in index, index
    assert "2026-09-09-elle-yazilmis" in index, "ilgisiz bag silindi"
    assert "dogrulama" in (wiki / "log.md").read_text(encoding="utf-8"), "log.md gecmisi bozuldu"

    # Yardimci dogrudan cagrildiginda da yalnizca eslesen satiri siler.
    assert prune_wiki_index(["yok-boyle-bir-sayfa"], vault_path=tmp_path) == []
