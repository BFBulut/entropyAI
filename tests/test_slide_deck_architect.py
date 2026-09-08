"""
Unit and Integration Test Suite for 'skills/slide-deck-architect'.
Tests SlideDeckBuilder, HTMLSlideRenderer, MarkdownSlideRenderer, and CLI execution.
Enforces 100% test pass rate.
"""

import sys
import json
import pytest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "skills" / "slide_deck_architect"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from skills.slide_deck_architect.slide_engine import (
    SlideDeck,
    SlideItem,
    SlideType,
    SlideDeckBuilder,
    HTMLSlideRenderer,
    MarkdownSlideRenderer,
    build_information_economics_deck,
    main as cli_main,
)


class TestSlideDeckBuilder:
    """Tests for the fluent SlideDeckBuilder API."""

    def test_builder_initialization(self):
        builder = SlideDeckBuilder(
            title="Test Presentation",
            subtitle="Testing Suite",
            author="Tester Agent",
            date="2026-09-06"
        )
        deck = builder.build()
        assert deck.title == "Test Presentation"
        assert deck.subtitle == "Testing Suite"
        assert deck.author == "Tester Agent"
        assert deck.date == "2026-09-06"
        assert len(deck.slides) == 0

    def test_builder_add_slides(self):
        builder = SlideDeckBuilder(title="Full Test Deck")
        builder.add_title_slide(speaker_notes="Title notes")
        builder.add_theory_slide(
            title="Core Theory",
            bullets=["Bullet 1", "Bullet 2"],
            equations=[r"E = mc^2"],
            callout="Crucial insight",
            speaker_notes="Theory notes"
        )
        builder.add_two_column_slide(
            title="Comparative Analysis",
            left_column=["Left 1", "Left 2"],
            right_column=["Right 1", "Right 2"],
            left_title="Column A",
            right_title="Column B"
        )
        builder.add_equation_breakdown_slide(
            title="Formula Deep Dive",
            equation=r"\sigma = \sqrt{\text{Var}}",
            variable_explanations=["Var is variance"],
            implications=["Sigma is std dev"]
        )
        builder.add_summary_slide(
            title="Conclusion",
            takeaways=["Takeaway A", "Takeaway B"]
        )

        deck = builder.build()
        assert len(deck.slides) == 5
        assert deck.slides[0].slide_type == SlideType.TITLE
        assert deck.slides[1].slide_type == SlideType.THEORY_CORE
        assert deck.slides[2].slide_type == SlideType.TWO_COLUMN
        assert deck.slides[3].slide_type == SlideType.EQUATION_BREAKDOWN
        assert deck.slides[4].slide_type == SlideType.SUMMARY


class TestHTMLSlideRenderer:
    """Tests for HTML5 standalone slide compilation."""

    def test_html_render_structure(self):
        builder = SlideDeckBuilder(title="HTML Render Test")
        builder.add_title_slide()
        builder.add_theory_slide(
            title="Theory Slide",
            bullets=["Point 1"],
            equations=[r"\lambda^* = 0.5"]
        )
        deck = builder.build()

        renderer = HTMLSlideRenderer()
        html = renderer.render(deck)

        assert "<!DOCTYPE html>" in html
        assert "katex.min.css" in html
        assert "katex.min.js" in html
        assert "HTML Render Test" in html
        assert "deck-controls" in html
        assert "toggleFullscreen" in html
        assert "toggleNotes" in html
        assert "updateSlide" in html
        assert "ArrowRight" in html

    def test_html_render_two_column(self):
        builder = SlideDeckBuilder(title="Col Test")
        builder.add_two_column_slide(
            title="Two Cols",
            left_column=["Item L"],
            right_column=["Item R"],
            left_title="Side L",
            right_title="Side R"
        )
        deck = builder.build()
        html = HTMLSlideRenderer().render(deck)
        assert "Two Cols" in html
        assert "two-cols" in html


class TestMarkdownSlideRenderer:
    """Tests for Obsidian/Marp markdown slide rendering."""

    def test_markdown_delimiters_and_frontmatter(self):
        builder = SlideDeckBuilder(title="Markdown Slide Test")
        builder.add_title_slide()
        builder.add_theory_slide(
            title="Point Slide",
            bullets=["Alpha", "Beta"],
            equations=[r"\psi = 1.0"],
            callout="Watch out"
        )
        deck = builder.build()

        md = MarkdownSlideRenderer().render(deck)

        assert "---" in md
        assert "title: \"Markdown Slide Test\"" in md
        assert "math: katex" in md
        assert "\n---\n" in md
        assert "## Point Slide" in md
        assert "- Alpha" in md
        assert "- Beta" in md
        assert "> [!NOTE]" in md
        assert "Watch out" in md


class TestInformationEconomicsDeck:
    """Tests for the pre-packaged Grossman-Stiglitz & Hasbrouck deck."""

    def test_information_economics_deck_integrity(self):
        deck = build_information_economics_deck()
        assert "Grossman-Stiglitz" in deck.title or "Grossman-Stiglitz" in (deck.subtitle or "")
        assert "Hasbrouck" in deck.title or "Hasbrouck" in (deck.subtitle or "")
        assert len(deck.slides) == 9

        # Slide titles check
        titles = [s.title for s in deck.slides]
        assert any("Grossman-Stiglitz" in t for t in titles)
        assert any("Hasbrouck" in t for t in titles)
        assert any("Cholesky" in t for t in titles)

        # Equations check
        all_eqs = [eq for s in deck.slides for eq in s.equations]
        assert any("Var" in eq for eq in all_eqs)
        assert any("psi" in eq or r"\psi" in eq for eq in all_eqs)


class TestCLIExecution:
    """End-to-end CLI execution test."""

    def test_cli_demo_export(self, tmp_path):
        out_html = tmp_path / "test_slides.html"
        out_md = tmp_path / "test_slides.md"
        out_json = tmp_path / "test_slides.json"

        exit_code = cli_main([
            "--demo", "information-economics",
            "--output-html", str(out_html),
            "--output-md", str(out_md),
            "--output-json", str(out_json)
        ])

        assert exit_code == 0
        assert out_html.exists()
        assert out_md.exists()
        assert out_json.exists()

        assert out_html.stat().st_size > 1000
        assert out_md.stat().st_size > 1000

        # Validate JSON
        data = json.loads(out_json.read_text(encoding="utf-8"))
        assert data["title"] == "Bilgi Edinme Dengesi ve Piyasa Fiyat Keşfi"
        assert len(data["slides"]) == 9


class TestCanivoPetsSlideDeck:
    """Tests for the Canivo Pets 360° growth audit slide deck."""

    def test_canivopets_deck_integrity_and_render(self):
        from scripts.generate_canivopets_slides import build_canivopets_slide_deck
        deck = build_canivopets_slide_deck()

        assert "Canivo Pets" in deck.title
        assert len(deck.slides) == 12

        titles = [s.title for s in deck.slides]
        assert any("Kurumsal Kimlik" in t for t in titles)
        assert any("Ürün Kataloğu" in t for t in titles)
        assert any("MarTech" in t for t in titles)
        assert any("Core Web Vitals" in t for t in titles)
        assert any("Birim Ekonomisi" in t for t in titles)
        assert any("Marj Korumalı Kampanyalar" in t for t in titles)
        assert any("Çok Kanallı Reklam" in t for t in titles)
        assert any("Kreatif Yorgunluk" in t for t in titles)
        assert any("Klaviyo" in t for t in titles)
        assert any("Onboarding SLA" in t for t in titles)

        # Render HTML
        html = HTMLSlideRenderer().render(deck)
        assert "Canivo Hunter" in html
        assert "TRADE BAŞYİĞİT" in html
        assert "Breakeven ROAS" in html
        assert "WebP" in html

        # Render Markdown
        md = MarkdownSlideRenderer().render(deck)
        assert "## 2. 🏢 Kurumsal Kimlik" in md
        assert "## 7. 🚀 Marj Korumalı Kampanyalar" in md
        assert "\n---\n" in md

