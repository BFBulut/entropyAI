"""
Yetenek yönlendirme (karar mekanizması) testleri.

Doğrulanan davranış:
- Türkçe site/büyüme ifadeleri medya ajansı yeteneğine düşer (önceden None).
- Göndermeli kısa takip ("bunu slayt yap") son yeteneği önceler ama açık bir
  anahtar kelime eşleşmesini ezmez.
- Alakasız mesajlar yetenek almaz; son yetenek sızmaz.
- Köprü yardımcısı geçmişi ve son yeteneği sınıflandırıcıya taşır.
"""

from pathlib import Path

import pytest

from entropy.skills.manager import SkillManager


def _write_skill(root: Path, name: str, desc: str, tags: str = "x"):
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: \"{desc}\"\ntags: {tags}\n---\n\n# {name}\n\nTalimat.\n",
        encoding="utf-8",
    )


@pytest.fixture
def sm(tmp_path):
    _write_skill(tmp_path, "media-agency-soldier", "Bir web sitesi veya marka için medya ajansı bakış açısıyla rakip ve pazar araştırması")
    _write_skill(tmp_path, "financial-auditor", "Şirket bilançolarını ve nakit akımını denetler")
    _write_skill(tmp_path, "slide-deck-architect", "Interactive HTML5 slide deck synthesis engine")
    _write_skill(tmp_path, "pdf-analyzer", "PDF belgelerini inceler ve tablo ayıklar")
    return SkillManager(root_skills_dir=tmp_path)


def _name(r):
    return r.name if r else None


def test_site_growth_phrasing_routes_to_media_agency(sm):
    """Kullanıcının fiili ifadeleri; önceden hiçbir yeteneğe düşmüyordu."""
    for p in (
        "canivopets sitesini incele ve buyume onerileri cikar",
        "bir web sitesi nasil analiz edilir",
        "musterinin sitesini inceleyip buyume onerisi cikar",
    ):
        assert _name(sm.auto_detect_skill_for_prompt(p)) == "media-agency-soldier", p


def test_explicit_keyword_beats_last_skill_prior(sm):
    """Açık alan terimi varsa son yetenek önceliği onu ezmemeli."""
    r = sm.auto_detect_skill_for_prompt("bilanco ve nakit akim analizi yap", last_skill="media-agency-soldier")
    assert _name(r) == "financial-auditor"


def test_anaphoric_followup_keeps_last_skill(sm):
    r = sm.auto_detect_skill_for_prompt("simdi de bunu derinlestir", last_skill="media-agency-soldier")
    assert _name(r) == "media-agency-soldier"
    r2 = sm.auto_detect_skill_for_prompt("devam et", last_skill="financial-auditor")
    assert _name(r2) == "financial-auditor"


def test_anaphoric_followup_with_its_own_keyword_wins(sm):
    """'bunu slayt yap': gönderme var ama 'slayt' kendi yeteneğini açıkça söylüyor."""
    r = sm.auto_detect_skill_for_prompt("bunu slayt yap", last_skill="media-agency-soldier")
    assert _name(r) == "slide-deck-architect"


def test_unrelated_prompt_gets_no_skill_even_with_last_skill(sm):
    assert sm.auto_detect_skill_for_prompt("merhaba nasilsin") is None
    assert sm.auto_detect_skill_for_prompt("bugun hava nasil", last_skill="financial-auditor") is None


def test_long_prompt_is_not_treated_as_anaphoric(sm):
    """Uzun bir mesajda 'bunu' geçmesi tek başına son yeteneği dayatmamalı."""
    p = "bunu okuduktan sonra sirketin bilanco ve nakit akim tablosunu forensik olarak denetle ve raporla"
    r = sm.auto_detect_skill_for_prompt(p, last_skill="media-agency-soldier")
    assert _name(r) == "financial-auditor"


def test_history_is_semantic_only_and_does_not_leak_keywords(sm):
    """Geçmişteki 'bilanco' yeni bir slayt isteğini finans'a çekmemeli."""
    r = sm.auto_detect_skill_for_prompt("slayt destesi hazirla", history=["bilanco analizi yap"])
    assert _name(r) == "slide-deck-architect"


def test_bridge_helper_passes_context(monkeypatch, tmp_path):
    """Köprü, son yeteneği ve son kullanıcı turlarını sınıflandırıcıya taşımalı."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from entropy.core.agy_bridge import AgyProcessBridge

    b = AgyProcessBridge()
    b.conversation_history = [
        {"role": "user", "content": "ilk"},
        {"role": "assistant", "content": "a"},
        {"role": "user", "content": "ikinci"},
        {"role": "assistant", "content": "b"},
        {"role": "user", "content": "ucuncu"},
    ]
    b.last_active_skill = "financial-auditor"
    assert b.recent_user_turns(2) == ["ikinci", "ucuncu"]

    seen = {}

    class _SM:
        def auto_detect_skill_for_prompt(self, prompt, last_skill=None, history=None):
            seen.update(prompt=prompt, last_skill=last_skill, history=history)
            return None

    b.detect_skill_for_prompt("devam", sm=_SM())
    assert seen == {"prompt": "devam", "last_skill": "financial-auditor", "history": ["ikinci", "ucuncu"]}
