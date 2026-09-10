#!/usr/bin/env python3
"""
SlideEngine: Core Synthesis Engine for SlideDeckArchitect.
Produces interactive standalone HTML5 presentations with KaTeX LaTeX math rendering,
Obsidian/Marp-compatible Markdown slide decks, and typed Pydantic slide models.
"""

from __future__ import annotations

import os
import sys
import json
import argparse
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Pydantic Slide Models
# ---------------------------------------------------------------------------

class SlideType(str, Enum):
    TITLE = "title"
    THEORY_CORE = "theory_core"
    TWO_COLUMN = "two_column"
    EQUATION_BREAKDOWN = "equation_breakdown"
    KEY_TAKEAWAY = "key_takeaway"
    SUMMARY = "summary"


class SlideContentBlock(BaseModel):
    block_type: str = Field(..., description="text | bullets | equation | callout | code | table")
    title: Optional[str] = None
    data: Any = None


class SlideItem(BaseModel):
    id: int
    title: str
    subtitle: Optional[str] = None
    slide_type: SlideType = SlideType.THEORY_CORE
    bullets: List[str] = Field(default_factory=list)
    equations: List[str] = Field(default_factory=list)
    left_column: Optional[List[str]] = None
    right_column: Optional[List[str]] = None
    left_title: Optional[str] = None
    right_title: Optional[str] = None
    callout: Optional[str] = None
    speaker_notes: Optional[str] = None
    footer: Optional[str] = None


class SlideDeck(BaseModel):
    title: str
    subtitle: Optional[str] = None
    author: Optional[str] = "Entropy AI"
    institution: Optional[str] = "Quantitative Research & Financial Engineering"
    date: Optional[str] = None
    theme: str = "cyber-slate"
    slides: List[SlideItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Fluent SlideDeck Builder
# ---------------------------------------------------------------------------

class SlideDeckBuilder:
    """Fluent API for assembling cohesive, high-density slide presentations."""

    def __init__(
        self,
        title: str,
        subtitle: Optional[str] = None,
        author: Optional[str] = "Entropy AI",
        institution: Optional[str] = "Financial Engineering & Market Microstructure",
        date: Optional[str] = None,
        theme: str = "cyber-slate"
    ):
        self.deck = SlideDeck(
            title=title,
            subtitle=subtitle,
            author=author,
            institution=institution,
            date=date,
            theme=theme,
            slides=[]
        )
        self._next_id = 1

    def add_title_slide(
        self,
        title: Optional[str] = None,
        subtitle: Optional[str] = None,
        speaker_notes: Optional[str] = None
    ) -> SlideDeckBuilder:
        self.deck.slides.append(
            SlideItem(
                id=self._next_id,
                title=title or self.deck.title,
                subtitle=subtitle or self.deck.subtitle,
                slide_type=SlideType.TITLE,
                speaker_notes=speaker_notes
            )
        )
        self._next_id += 1
        return self

    def add_theory_slide(
        self,
        title: str,
        subtitle: Optional[str] = None,
        bullets: Optional[List[str]] = None,
        equations: Optional[List[str]] = None,
        callout: Optional[str] = None,
        speaker_notes: Optional[str] = None
    ) -> SlideDeckBuilder:
        self.deck.slides.append(
            SlideItem(
                id=self._next_id,
                title=title,
                subtitle=subtitle,
                slide_type=SlideType.THEORY_CORE,
                bullets=bullets or [],
                equations=equations or [],
                callout=callout,
                speaker_notes=speaker_notes
            )
        )
        self._next_id += 1
        return self

    def add_two_column_slide(
        self,
        title: str,
        left_column: List[str],
        right_column: List[str],
        left_title: str = "Temel Aksiyom & Formülasyon",
        right_title: str = "Mikroyapı & Piyasa Sezgisi",
        subtitle: Optional[str] = None,
        equations: Optional[List[str]] = None,
        callout: Optional[str] = None,
        speaker_notes: Optional[str] = None
    ) -> SlideDeckBuilder:
        self.deck.slides.append(
            SlideItem(
                id=self._next_id,
                title=title,
                subtitle=subtitle,
                slide_type=SlideType.TWO_COLUMN,
                left_column=left_column,
                right_column=right_column,
                left_title=left_title,
                right_title=right_title,
                equations=equations or [],
                callout=callout,
                speaker_notes=speaker_notes
            )
        )
        self._next_id += 1
        return self

    def add_equation_breakdown_slide(
        self,
        title: str,
        equation: str,
        variable_explanations: List[str],
        implications: Optional[List[str]] = None,
        callout: Optional[str] = None,
        speaker_notes: Optional[str] = None
    ) -> SlideDeckBuilder:
        bullets = variable_explanations + (implications or [])
        self.deck.slides.append(
            SlideItem(
                id=self._next_id,
                title=title,
                slide_type=SlideType.EQUATION_BREAKDOWN,
                equations=[equation],
                bullets=bullets,
                callout=callout,
                speaker_notes=speaker_notes
            )
        )
        self._next_id += 1
        return self

    def add_summary_slide(
        self,
        title: str = "Sentez ve Temel Sonuçlar",
        takeaways: Optional[List[str]] = None,
        callout: Optional[str] = None,
        speaker_notes: Optional[str] = None
    ) -> SlideDeckBuilder:
        self.deck.slides.append(
            SlideItem(
                id=self._next_id,
                title=title,
                slide_type=SlideType.SUMMARY,
                bullets=takeaways or [],
                callout=callout,
                speaker_notes=speaker_notes
            )
        )
        self._next_id += 1
        return self

    def build(self) -> SlideDeck:
        return self.deck


# ---------------------------------------------------------------------------
# HTML5 Slide Renderer (KaTeX LaTeX + Cybernetic Slate Theme)
# ---------------------------------------------------------------------------

class HTMLSlideRenderer:
    """Compiles a SlideDeck into a single, zero-install, responsive HTML5 presentation."""

    def render(self, deck: SlideDeck) -> str:
        total_slides = len(deck.slides)
        slides_json = json.dumps(deck.model_dump(), ensure_ascii=False)

        html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{deck.title}</title>
    <!-- KaTeX CSS & JS for Mathematical Formulas -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css" crossorigin="anonymous">
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.js" crossorigin="anonymous"></script>
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/contrib/auto-render.min.js" crossorigin="anonymous"></script>
    <style>
        :root {{
            --bg-primary: #0a0e17;
            --bg-secondary: #111927;
            --bg-card: rgba(22, 33, 51, 0.75);
            --border-glow: rgba(56, 189, 248, 0.25);
            --border-card: #1e293b;
            --cyan-accent: #38bdf8;
            --emerald-accent: #34d399;
            --amber-accent: #fbbf24;
            --rose-accent: #fb7185;
            --text-main: #f1f5f9;
            --text-muted: #94a3b8;
            --font-sans: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            background: radial-gradient(circle at 50% 20%, #152238 0%, var(--bg-primary) 70%);
            color: var(--text-main);
            font-family: var(--font-sans);
            height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            user-select: none;
        }}

        /* Header / Meta Bar */
        .deck-header {{
            height: 52px;
            padding: 0 28px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid var(--border-card);
            background: rgba(10, 14, 23, 0.85);
            backdrop-filter: blur(12px);
            z-index: 100;
        }}

        .deck-brand {{
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 0.95rem;
            font-weight: 700;
            color: var(--cyan-accent);
            letter-spacing: 0.5px;
        }}

        .deck-controls {{
            display: flex;
            align-items: center;
            gap: 16px;
        }}

        .btn-ctrl {{
            background: var(--bg-secondary);
            border: 1px solid var(--border-card);
            color: var(--text-main);
            padding: 6px 14px;
            border-radius: 6px;
            font-size: 0.82rem;
            cursor: pointer;
            transition: all 0.2s ease;
        }}

        .btn-ctrl:hover {{
            background: var(--cyan-accent);
            color: #000;
            box-shadow: 0 0 12px var(--cyan-accent);
        }}

        /* Progress Bar */
        .progress-container {{
            height: 4px;
            width: 100%;
            background: var(--border-card);
            position: relative;
        }}

        .progress-bar {{
            height: 100%;
            width: 0%;
            background: linear-gradient(90deg, var(--cyan-accent), var(--emerald-accent));
            transition: width 0.3s ease;
            box-shadow: 0 0 8px var(--cyan-accent);
        }}

        /* Main Viewport */
        .viewport {{
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 40px 60px;
            position: relative;
            overflow: hidden;
        }}

        .slide-container {{
            width: 100%;
            max-width: 1200px;
            height: 100%;
            max-height: 720px;
            background: var(--bg-card);
            border: 1px solid var(--border-glow);
            border-radius: 16px;
            padding: 44px 56px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.6), inset 0 1px 1px rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(16px);
            opacity: 1;
            transform: scale(1);
            transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
        }}

        /* Slide Typography */
        .slide-tag {{
            display: inline-block;
            align-self: flex-start;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            font-weight: 700;
            color: var(--cyan-accent);
            background: rgba(56, 189, 248, 0.12);
            border: 1px solid var(--border-glow);
            padding: 4px 12px;
            border-radius: 20px;
            margin-bottom: 12px;
        }}

        .slide-title {{
            font-size: 2.2rem;
            font-weight: 800;
            line-height: 1.25;
            color: #ffffff;
            margin-bottom: 8px;
            letter-spacing: -0.5px;
        }}

        .slide-subtitle {{
            font-size: 1.15rem;
            color: var(--text-muted);
            margin-bottom: 24px;
        }}

        .slide-body {{
            flex: 1;
            display: flex;
            flex-direction: column;
            justify-content: center;
            gap: 20px;
            overflow-y: auto;
        }}

        /* Bullet List */
        .bullet-list {{
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 14px;
        }}

        .bullet-item {{
            font-size: 1.15rem;
            line-height: 1.6;
            color: #e2e8f0;
            display: flex;
            align-items: flex-start;
            gap: 12px;
        }}

        .bullet-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--cyan-accent);
            box-shadow: 0 0 8px var(--cyan-accent);
            margin-top: 9px;
            flex-shrink: 0;
        }}

        /* LaTeX Equation Box */
        .equation-box {{
            background: rgba(15, 23, 42, 0.85);
            border: 1px solid rgba(56, 189, 248, 0.35);
            border-left: 4px solid var(--cyan-accent);
            border-radius: 10px;
            padding: 20px 24px;
            margin: 10px 0;
            box-shadow: inset 0 2px 8px rgba(0, 0, 0, 0.4);
            text-align: center;
            font-size: 1.35rem;
            color: #ffffff;
            overflow-x: auto;
        }}

        /* Two Column Layout */
        .two-cols {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 28px;
            flex: 1;
        }}

        .col-card {{
            background: rgba(15, 23, 42, 0.5);
            border: 1px solid var(--border-card);
            border-radius: 12px;
            padding: 22px;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }}

        .col-title {{
            font-size: 1.05rem;
            font-weight: 700;
            color: var(--cyan-accent);
            border-bottom: 1px solid var(--border-card);
            padding-bottom: 8px;
        }}

        /* Callout Box */
        .callout-box {{
            background: rgba(52, 211, 153, 0.1);
            border: 1px solid rgba(52, 211, 153, 0.35);
            border-radius: 8px;
            padding: 14px 18px;
            font-size: 1.05rem;
            color: #a7f3d0;
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        /* Slide Footer */
        .slide-footer {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-top: 1px solid var(--border-card);
            padding-top: 16px;
            font-size: 0.85rem;
            color: var(--text-muted);
        }}

        /* Navigation Arrows */
        .nav-btn {{
            position: absolute;
            top: 50%;
            transform: translateY(-50%);
            background: rgba(17, 25, 39, 0.8);
            border: 1px solid var(--border-card);
            color: var(--text-main);
            width: 48px;
            height: 48px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.4rem;
            cursor: pointer;
            transition: all 0.2s;
            z-index: 50;
        }}

        .nav-btn:hover {{
            background: var(--cyan-accent);
            color: #000;
            box-shadow: 0 0 16px var(--cyan-accent);
        }}

        .nav-prev {{ left: 16px; }}
        .nav-next {{ right: 16px; }}

        /* Title Slide Archetype */
        .slide-title-archetype {{
            text-align: center;
            justify-content: center;
            align-items: center;
            gap: 20px;
        }}

        .slide-title-archetype .slide-title {{
            font-size: 3.2rem;
            background: linear-gradient(135deg, #ffffff 30%, var(--cyan-accent) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        .slide-title-archetype .slide-meta {{
            display: flex;
            flex-direction: column;
            gap: 8px;
            font-size: 1.15rem;
            color: var(--text-muted);
            margin-top: 20px;
        }}

        /* Speaker Notes Panel */
        .notes-drawer {{
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: rgba(10, 14, 23, 0.95);
            border-top: 2px solid var(--cyan-accent);
            padding: 16px 32px;
            font-size: 0.95rem;
            color: #cbd5e1;
            display: none;
            z-index: 200;
            backdrop-filter: blur(16px);
        }}
    </style>
</head>
<body>

    <!-- Header -->
    <header class="deck-header">
        <div class="deck-brand">
            <span>⚡</span>
            <span>{deck.title}</span>
        </div>
        <div class="deck-controls">
            <span id="slide-indicator" style="font-family: var(--font-mono); font-size: 0.85rem; color: var(--text-muted);">1 / {total_slides}</span>
            <button class="btn-ctrl" onclick="toggleNotes()">📝 Notlar [N]</button>
            <button class="btn-ctrl" onclick="toggleFullscreen()">⛶ Tam Ekran [F]</button>
        </div>
    </header>

    <!-- Progress Bar -->
    <div class="progress-container">
        <div id="progress-bar" class="progress-bar"></div>
    </div>

    <!-- Viewport -->
    <main class="viewport">
        <button class="nav-btn nav-prev" onclick="prevSlide()">‹</button>
        
        <div id="slide-card" class="slide-container">
            <!-- Dynamic Slide Injection -->
        </div>

        <button class="nav-btn nav-next" onclick="nextSlide()">›</button>
    </main>

    <!-- Speaker Notes -->
    <div id="notes-drawer" class="notes-drawer">
        <div style="font-weight: 700; color: var(--cyan-accent); margin-bottom: 6px;">🎙️ Konuşmacı Notları:</div>
        <div id="notes-content">Not bulunmuyor.</div>
    </div>

    <script>
        const deckData = {slides_json};
        let currentSlideIndex = 0;
        let notesVisible = false;

        function updateSlide() {{
            const slide = deckData.slides[currentSlideIndex];
            const card = document.getElementById('slide-card');
            const indicator = document.getElementById('slide-indicator');
            const progressBar = document.getElementById('progress-bar');
            const notesContent = document.getElementById('notes-content');

            // Progress
            const pct = ((currentSlideIndex + 1) / deckData.slides.length) * 100;
            progressBar.style.width = pct + '%';
            indicator.textContent = `${{currentSlideIndex + 1}} / ${{deckData.slides.length}}`;

            // Notes
            notesContent.textContent = slide.speaker_notes || "Bu slayt için ek konuşmacı notu bulunmuyor.";

            // Render Content based on SlideType
            let html = '';

            if (slide.slide_type === 'title') {{
                card.className = "slide-container slide-title-archetype";
                html = `
                    <div class="slide-tag">AKADEMİK & KANTİTATİF SEMİNER</div>
                    <h1 class="slide-title">${{slide.title}}</h1>
                    ${{slide.subtitle ? `<div class="slide-subtitle">${{slide.subtitle}}</div>` : ''}}
                    <div class="slide-meta">
                        <div><strong>Sunum:</strong> ${{deckData.author || 'Entropy AI'}}</div>
                        <div><strong>Kurum / Uzmanlık:</strong> ${{deckData.institution || 'Finansal Mühendislik'}}</div>
                        ${{deckData.date ? `<div><strong>Tarih:</strong> ${{deckData.date}}</div>` : ''}}
                    </div>
                `;
            }} else if (slide.slide_type === 'two_column') {{
                card.className = "slide-container";
                html = `
                    <div>
                        <div class="slide-tag">MİKROYAPI ANALİTİĞİ</div>
                        <h2 class="slide-title">${{slide.title}}</h2>
                        ${{slide.subtitle ? `<div class="slide-subtitle">${{slide.subtitle}}</div>` : ''}}
                    </div>
                    <div class="slide-body">
                        ${{slide.equations && slide.equations.length ? slide.equations.map(eq => `<div class="equation-box">$$${{eq}}$$</div>`).join('') : ''}}
                        <div class="two-cols">
                            <div class="col-card">
                                <div class="col-title">${{slide.left_title || 'Teorik Çerçeve'}}</div>
                                <ul class="bullet-list">
                                    ${{(slide.left_column || []).map(b => `<li class="bullet-item"><span class="bullet-dot"></span><span>${{b}}</span></li>`).join('')}}
                                </ul>
                            </div>
                            <div class="col-card">
                                <div class="col-title">${{slide.right_title || 'Piyasa Yorumu'}}</div>
                                <ul class="bullet-list">
                                    ${{(slide.right_column || []).map(b => `<li class="bullet-item"><span class="bullet-dot"></span><span>${{b}}</span></li>`).join('')}}
                                </ul>
                            </div>
                        </div>
                        ${{slide.callout ? `<div class="callout-box"><span>💡</span><span>${{slide.callout}}</span></div>` : ''}}
                    </div>
                    <div class="slide-footer">
                        <span>${{deckData.title}}</span>
                        <span>Slayt ${{currentSlideIndex + 1}}</span>
                    </div>
                `;
            }} else {{
                card.className = "slide-container";
                html = `
                    <div>
                        <div class="slide-tag">KANTİTATİF FORMÜLASYON</div>
                        <h2 class="slide-title">${{slide.title}}</h2>
                        ${{slide.subtitle ? `<div class="slide-subtitle">${{slide.subtitle}}</div>` : ''}}
                    </div>
                    <div class="slide-body">
                        ${{slide.equations && slide.equations.length ? slide.equations.map(eq => `<div class="equation-box">$$${{eq}}$$</div>`).join('') : ''}}
                        <ul class="bullet-list">
                            ${{(slide.bullets || []).map(b => `<li class="bullet-item"><span class="bullet-dot"></span><span>${{b}}</span></li>`).join('')}}
                        </ul>
                        ${{slide.callout ? `<div class="callout-box"><span>📌</span><span>${{slide.callout}}</span></div>` : ''}}
                    </div>
                    <div class="slide-footer">
                        <span>${{deckData.title}}</span>
                        <span>Slayt ${{currentSlideIndex + 1}}</span>
                    </div>
                `;
            }}

            card.innerHTML = html;

            // Trigger KaTeX render
            if (window.renderMathInElement) {{
                renderMathInElement(card, {{
                    delimiters: [
                        {{left: '$$', right: '$$', display: true}},
                        {{left: '$', right: '$', display: false}}
                    ],
                    throwOnError: false
                }});
            }}
        }}

        function nextSlide() {{
            if (currentSlideIndex < deckData.slides.length - 1) {{
                currentSlideIndex++;
                updateSlide();
            }}
        }}

        function prevSlide() {{
            if (currentSlideIndex > 0) {{
                currentSlideIndex--;
                updateSlide();
            }}
        }}

        function toggleNotes() {{
            notesVisible = !notesVisible;
            document.getElementById('notes-drawer').style.display = notesVisible ? 'block' : 'none';
        }}

        function toggleFullscreen() {{
            if (!document.fullscreenElement) {{
                document.documentElement.requestFullscreen().catch(() => {{}});
            }} else {{
                document.exitFullscreen().catch(() => {{}});
            }}
        }}

        // Keyboard navigation
        window.addEventListener('keydown', (e) => {{
            if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'PageDown') {{
                nextSlide();
            }} else if (e.key === 'ArrowLeft' || e.key === 'PageUp') {{
                prevSlide();
            }} else if (e.key === 'Home') {{
                currentSlideIndex = 0;
                updateSlide();
            }} else if (e.key === 'End') {{
                currentSlideIndex = deckData.slides.length - 1;
                updateSlide();
            }} else if (e.key === 'f' || e.key === 'F') {{
                toggleFullscreen();
            }} else if (e.key === 'n' || e.key === 'N') {{
                toggleNotes();
            }}
        }});

        // Touch swipe navigation
        let touchStartX = 0;
        window.addEventListener('touchstart', (e) => {{
            touchStartX = e.changedTouches[0].screenX;
        }});
        window.addEventListener('touchend', (e) => {{
            const touchEndX = e.changedTouches[0].screenX;
            if (touchStartX - touchEndX > 50) nextSlide();
            if (touchEndX - touchStartX > 50) prevSlide();
        }});

        // Initial setup
        window.addEventListener('load', () => {{
            updateSlide();
        }});
    </script>
</body>
</html>
"""
        return html


# ---------------------------------------------------------------------------
# Markdown Slide Renderer (Obsidian & Marp Compatible)
# ---------------------------------------------------------------------------

class MarkdownSlideRenderer:
    """Renders a SlideDeck into Obsidian/Marp native slides using '---' delimiters."""

    def render(self, deck: SlideDeck) -> str:
        lines = []

        # Frontmatter
        lines.append("---")
        lines.append(f"title: \"{deck.title}\"")
        if deck.subtitle:
            lines.append(f"subtitle: \"{deck.subtitle}\"")
        lines.append(f"author: \"{deck.author or 'Entropy AI'}\"")
        lines.append(f"date: \"{deck.date or ''}\"")
        lines.append("theme: gaia")
        lines.append("paginate: true")
        lines.append("math: katex")
        lines.append("---\n")

        for idx, slide in enumerate(deck.slides):
            if idx > 0:
                lines.append("\n---\n")

            if slide.slide_type == SlideType.TITLE:
                lines.append(f"# {slide.title}\n")
                if slide.subtitle:
                    lines.append(f"### {slide.subtitle}\n")
                lines.append(f"**Sunum:** {deck.author}  ")
                lines.append(f"**Kurum:** {deck.institution}  ")
                if deck.date:
                    lines.append(f"**Tarih:** {deck.date}  ")
            elif slide.slide_type == SlideType.TWO_COLUMN:
                lines.append(f"## {slide.title}\n")
                if slide.subtitle:
                    lines.append(f"*{slide.subtitle}*\n")

                for eq in slide.equations:
                    lines.append(f"$$\n{eq}\n$$\n")

                lines.append(f"### {slide.left_title or 'Sol Panel'}")
                for b in (slide.left_column or []):
                    lines.append(f"- {b}")
                lines.append("")

                lines.append(f"### {slide.right_title or 'Sağ Panel'}")
                for b in (slide.right_column or []):
                    lines.append(f"- {b}")
                lines.append("")

                if slide.callout:
                    lines.append(f"> [!TIP]\n> {slide.callout}\n")
            else:
                lines.append(f"## {slide.title}\n")
                if slide.subtitle:
                    lines.append(f"*{slide.subtitle}*\n")

                for eq in slide.equations:
                    lines.append(f"$$\n{eq}\n$$\n")

                for b in slide.bullets:
                    lines.append(f"- {b}")

                if slide.callout:
                    lines.append(f"\n> [!NOTE]\n> {slide.callout}\n")

            if slide.speaker_notes:
                lines.append(f"\n<!--\n🎙️ Notlar: {slide.speaker_notes}\n-->\n")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Pre-packaged Academic Slide Deck Builder: Information Economics
# ---------------------------------------------------------------------------

def build_information_economics_deck() -> SlideDeck:
    """Synthesizes the specific slide deck requested: Grossman-Stiglitz Paradox & Hasbrouck Information Share."""
    builder = SlideDeckBuilder(
        title="Bilgi Edinme Dengesi ve Piyasa Fiyat Keşfi",
        subtitle="Grossman-Stiglitz (1980) Paradoksu ve Hasbrouck (1991, 1995) Bilgi Paylaşımı (IS / GIS)",
        author="Entropy AI",
        institution="Kantitatif Finans ve Piyasa Mikroyapısı Araştırma Grubu",
        date="2026-09-06"
    )

    # Slide 1: Title
    builder.add_title_slide(
        speaker_notes="Bu seminerde modern finansal mikroyapının iki temel köşe taşını inceliyoruz: Bilgi edinmenin içsel dengesi ve parçalanmış piyasalarda fiyat keşfinin ekonometrik ayrıştırması."
    )

    # Slide 2: Grossman-Stiglitz Paradox Overview
    builder.add_theory_slide(
        title="1. Grossman-Stiglitz (1980) Paradoksu: Giriş",
        subtitle="Etkin Piyasalar Hipotezinin (EMH) İçsel Çelişkisi",
        bullets=[
            r"**Temel Teorem:** Bilgi edinme maliyeti sıfırdan büyük ($c > 0$) olduğunda, tam bilgi etkinliğine sahip bir piyasanın var olması imkansızdır.",
            r"**Mantıksal Kısır Döngü:** Eğer piyasa fiyatı $P$ tüm özel bilgiyi ($\theta$) kusursuzca yansıtıyorsa, hiçbir rasyonel aktör pozitif kaynak ($c > 0$) harcayarak bilgi toplamaz.",
            r"**Piyasanın Çöküşü:** Ancak kimse bilgi toplamazsa, fiyat $P$ hiçbir özel bilgiyi yansıtamaz ve piyasa tamamen bilgisiz kalır.",
            r"**Çözüm Yolu:** Fiyattaki gürültü (Noise Traders / Likidite Şoku) sayesinde bilgi kısmen gizlenir ve dengede pozitif oranda bilgili tüccar ($\lambda^*$) hayatta kalır."
        ],
        callout="Eğer piyasalar Fama anlamında güçlü formda etkin olsaydı, bilgiye yatırım yapan tüm analistler ve fonlar iflas ederdi.",
        speaker_notes="Sanford Grossman ve Joseph Stiglitz 1980 AER makalelerinde EMH'nin kalbine matematiksel bir hançer saplamıştır: Bilgi bedava değilse piyasa asla tam etkin olamaz."
    )

    # Slide 3: Grossman-Stiglitz CARA-Normal Formülasyonu
    builder.add_equation_breakdown_slide(
        title="2. Grossman-Stiglitz Denge Denklemi",
        equation=r"\frac{\text{Var}(\theta \mid \text{uninformed})}{\text{Var}(\theta \mid \text{informed})} = e^{2ac}",
        variable_explanations=[
            r"**$a$:** Negatif üstel CARA fayda fonksiyonundaki mutlak riskten kaçınma katsayısı ($U(W) = -e^{-aW}$).",
            r"**$c > 0$:** Özel bilgi sinyali $y = \theta + \epsilon$ toplamanın katlanılan parasal maliyeti.",
            r"**$\text{Var}(\theta \mid \text{informed})$:** Bilgili tüccarın sinyal sonrası nihai değer $\theta$ üzerindeki koşullu varyansı.",
            r"**$\text{Var}(\theta \mid \text{uninformed})$:** Bilgisiz tüccarın yalnızca piyasa fiyatını gözlemleyerek ulaştığı koşullu varyans."
        ],
        implications=[
            r"**İçsel Denge Oranı ($\lambda^*$):** Bilgili tüccar oranı $\lambda \in (0, 1)$ endojen olarak belirlenir.",
            r"**Eksik Fiyat Bilgilendiriciliği:** Fiyat bilgilendiriciliği $\rho^2 = \text{Corr}(P, \theta)^2 < 1$ olmak zorundadır. Piyasada her zaman gürültü tüccarı arzı $x \sim \mathcal{N}(0, \sigma_x^2)$ bulunmalıdır."
        ],
        callout="Varyans oranı tam olarak e^(2ac) katına ulaştığında, bilgili ve bilgisiz tüccarların beklenen faydaları eşitlenir.",
        speaker_notes="Formülde görüldüğü üzere maliyet c arttıkça veya riskten kaçınma a yükseldikçe, bilgisizlerin katlandığı belirsizlik katlanarak artar."
    )

    # Slide 4: İki Sütunlu Karşılaştırma: Bilgili vs Bilgisiz Tüccar
    builder.add_two_column_slide(
        title="3. Grossman-Stiglitz Denge Mekaniği",
        left_title="Bilgili Tüccarlar (Informed, λ*)",
        right_title="Bilgisiz Tüccarlar (Uninformed, 1 - λ*)",
        left_column=[
            r"Özel sinyali $y = \theta + \epsilon$ gözlemler.",
            r"Kişi başı sabit $c > 0$ araştırma maliyetine katlanır.",
            r"Talep fonksiyonu: $X_I(P, y) = \frac{E[\theta \mid y] - P}{a \cdot \text{Var}(\theta \mid y)}$.",
            r"Fiyat üzerindeki bilgi baskısını oluşturur."
        ],
        right_column=[
            r"Yalnızca piyasa denge fiyatı $P$'yi gözlemler.",
            r"Sıfır araştırma maliyetiyle piyasada işlem yapar.",
            r"Talebi fiyattan sinyal türetir: $E[\theta \mid P]$.",
            r"Gürültü tüccarı arzı $x$'i tam ayırt edemez (Sinyal/Gürültü Ayrımı)."
        ],
        callout=r"Denge ancak $\lambda^* \in (0, 1)$ aralığında var olabilir. $\lambda=0$ da $\lambda=1$ de kararsızdır.",
        speaker_notes="Bilgisiz tüccarlar fiyatı gözlemleyerek bedavacılık (free-riding) yapmaya çalışır. Ancak gürültü tüccarları piyasada olmasaydı fiyat bilgiyi %100 açığa vurur ve bedavacılık sistemi yok ederdi."
    )

    # Slide 5: Hasbrouck Cointegrated VAR Giriş
    builder.add_theory_slide(
        title="4. Joel Hasbrouck (1991, 1995): Fiyat Keşfi & Cointegrated VAR",
        subtitle="Parçalanmış Elektronik Piyasalarda Fiyat Liderliğinin Ölçülmesi",
        bullets=[
            r"**Problem:** Aynı finansal varlık (hisse senedi, tahvil, Bitcoin) birden fazla borsada (NYSE vs NASDAQ, Binance vs Coinbase) eşzamanlı işlem görmektedir.",
            r"**Tek Fiyat Kanunu & Eşbütünleşme:** Arbitraj sayesinde fiyatlar uzun vadede birlikte hareket eder: Fiyat serileri $p_t = [p_{1,t}, p_{2,t}, \dots, p_{n,t}]'$ **$I(1)$ eşbütünleşiktir**.",
            r"**Beveridge-Nelson Ayrıştırması:** Fiyat vektörü iki bileşene ayrılır: Kalıcı ortak rassal yürüyüş (Martingale / İçsel Değer $m_t$) ve geçici mikroyapı gürültüsü ($s_t$).",
            r"**Soru:** Ortak içsel değer yeniliği $\epsilon_t$'ye hangi borsa yön vermektedir?"
        ],
        callout="Hasbrouck Bilgi Paylaşımı (Information Share - IS), fiyat keşfinin tam coğrafi konumunu milisaniye seviyesinde tespit eder.",
        speaker_notes="Hasbrouck 1995 JOF makalesiyle finansal ekonometriye muazzam bir araç kazandırdı: Vektör Hata Düzeltme Modeli (VECM) üzerinden bilgi payı hesaplama."
    )

    # Slide 6: Hasbrouck VECM & Martingale Formülasyonu
    builder.add_equation_breakdown_slide(
        title="5. Hasbrouck Beveridge-Nelson & VECM Ayrıştırması",
        equation=r"p_t = \iota m_t + s_t, \quad m_t = m_{t-1} + \psi \epsilon_t",
        variable_explanations=[
            r"**$p_t$:** $n$ adet farklı borsadaki kotasyon fiyat vektörü.",
            r"**$m_t$:** Ortak kalıcı martingale içsel değer bileşeni ($m_t = m_{t-1} + \psi \epsilon_t$).",
            r"**$s_t$:** Sıfır ortalamalı durağan mikroyapı gürültüsü (Bid-Ask bounce, likidite şokları).",
            r"**$\psi$:** VECM hareketli ortalama (Wold MA) uzun dönem etki vektörü ($[\psi_1, \psi_2, \dots, \psi_n]$).",
            r"**$\epsilon_t$:** Yenilik vektörü, kovaryans matrisi $\Omega = E[\epsilon_t \epsilon_t']$."
        ],
        implications=[
            r"Eşbütünleşme vektörü gereği $\psi$ vektörünün satırları birbirine özdeştir: $\psi = \iota \beta'$.",
            r"Kalıcı varyans: $\sigma_m^2 = \psi \Omega \psi'$ formülüyle hesaplanır."
        ],
        callout="Tüm piyasalar aynı uzun vadeli içsel değere bağlıdır; ancak bu değere ilk tepki veren borsa liderdir.",
        speaker_notes="Burada psi vektörü hangi piyasanın yeniliklerinin kalıcı fiyata geçtiğini gösterir. Eğer psi_1 büyükse 1. borsa fiyatı yönlendiriyor demektir."
    )

    # Slide 7: Cholesky Ayrışımı ve Bilgi Paylaşımı (IS) Alt/Üst Sınırları
    builder.add_two_column_slide(
        title="6. Cholesky Ayrışımı & Hasbrouck Information Share (IS)",
        subtitle="Yenilik Korelasyonu ve Sıralama Bağımlılığı Çözümü",
        left_title="Cholesky Faktörizasyonu & IS Formülü",
        right_title="Ekonometrik Sınırlar & Ortak Bilgi Payı (GIS)",
        left_column=[
            r"Kovaryans matrisi alt üçgensel faktörlere ayrılır:",
            r"$$\Omega = F F'$$",
            r"$j$. piyasanın Bilgi Paylaşımı (Information Share):",
            r"$$IS_j = \frac{([\psi F]_j)^2}{\psi \Omega \psi'}$$",
            r"Payların toplamı bire eşittir: $\sum_{j=1}^n IS_j = 1$."
        ],
        right_column=[
            r"**Sıralama Bağımlılığı:** $\Omega$ köşegen değilse (borsalar arası korelasyon $\rho \neq 0$), Cholesky sıralaması üst ve alt sınırlar ($IS_j^{\max}, IS_j^{\min}$) üretir.",
            r"İlk sıradaki borsa en yüksek korelasyon payını alır.",
            r"**Çözüm (Midpoint / GIS):**",
            r"$$IS_j^{\text{mid}} = \frac{IS_j^{\max} + IS_j^{\min}}{2}$$",
            r"Lien-Shrestha (2009) Generalized IS (GIS) ile özdeğer tabanlı sıralamadan bağımsız metrik elde edilir."
        ],
        callout="Kripto para piyasalarında Binance ve Coinbase arasındaki fiyat keşfi liderliği bu metodolojiyle ölçülmektedir.",
        speaker_notes="Cholesky matrisinde birinci sıraya koyduğunuz borsa korelasyondan aslan payını alır. Bu yüzden akademik standart alt ve üst sınırları hesaplayıp ortalamasını almaktır."
    )

    # Slide 8: Karşılaştırmalı Sentez & Piyasa Mikroyapısı Çıkarımları
    builder.add_two_column_slide(
        title="7. İki Teorinin Birleşik Piyasa Mimarisi",
        subtitle="Grossman-Stiglitz Paradoksu ➔ Hasbrouck Fiyat Keşfi Köprüsü",
        left_title="Bilgi Edinme Düzeyi (Grossman-Stiglitz)",
        right_title="Emir Akışı & Uygulama (Hasbrouck)",
        left_column=[
            r"**Neden Bilgi Toplanır?** Bilgili tüccarlar beklenen kâr elde etmek için araştırma yapar ($c > 0$).",
            r"**Fiyatın Rolü:** Bilgiyi agregasyonla piyasaya taşır ancak asla tam etkin olamaz ($\rho^2 < 1$).",
            r"**Gürültü Şartı:** Likidite tüccarları olmasa piyasa likiditesi tamamen kurur (No-Trade Theorem)."
        ],
        right_column=[
            r"**Bilgi Nerede Fiyata Dönüşür?** Bilgili tüccarların girdiği limit ve piyasa emirlerinde (Order Flow Informativeness).",
            r"**Fiyat Keşfi Konumu:** En derin likiditeye ve en düşük gecikmeye (latency) sahip borsa en yüksek $IS_j$ payını alır.",
            r"**Kalıcı Etki:** Bilgili emir akışı kalıcı fiyat şokuna ($\psi \epsilon_t$) dönüşür."
        ],
        callout="Grossman-Stiglitz bilginin piyasaya NEDEN girdiğini, Hasbrouck ise bu bilginin NEREDE fiyata dönüştüğünü kanıtlar.",
        speaker_notes="Bu iki teori bir madalyonun iki yüzüdür. Biri bilginin ekonomik varoluş koşulunu açıklar, diğeri ise bu bilginin parçalanmış emir defterlerindeki ekonometrik izini sürer."
    )

    # Slide 9: Summary & Key Takeaways
    builder.add_summary_slide(
        title="8. Sonuç & Temel Çıkarımlar",
        takeaways=[
            r"**Tam Etkinlik İmkansızdır:** Grossman & Stiglitz (1980), bilgi maliyetli ($c > 0$) olduğu sürece piyasa fiyatlarının özel bilgiyi %100 yansıtamayacağını ispatlamıştır. Piyasada alfa ve aktif yönetim her zaman var olmak zorundadır.",
            r"**Gürültü Piyasayı Yaşatır:** Gürültü tüccarları ($x \sim \mathcal{N}(0, \sigma_x^2)$) olmadan bilgi ticareti yapılamaz; bilgisizler bedavacılıkla tüm bilgiyi çekip sistemi kilitler.",
            r"**Fiyat Keşfi Ölçülebilirdir:** Joel Hasbrouck (1991, 1995), eşbütünleşik VAR ve Beveridge-Nelson ayrıştırmasıyla kalıcı içsel değer yeniliklerinin hangi borsadan kaynaklandığını ($IS_j$) kesin matematiksel sınırlarla ortaya koymuştur.",
            r"**Modern Uygulama:** HFT algoritmaları, arbitraj botları ve kripto türev borsaları (Binance Perp vs Coinbase Spot) arasındaki liderlik rekabeti Hasbrouck Information Share ile modellenmektedir."
        ],
        callout="Teşekkürler! Sorularınız ve Kantitatif Tartışma İçin Söz Sizde.",
        speaker_notes="Sunumumuz burada sona erdi. Grossman-Stiglitz ve Hasbrouck ekolü, günümüz algoritmik piyasa yapıcılığının ve yüksek frekanslı ticaretin temel referans noktası olmaya devam etmektedir."
    )

    return builder.build()


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main(args_list: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="SlideDeckArchitect CLI")
    parser.add_argument("--demo", type=str, choices=["information-economics"], help="Hazır demo slayt destesini oluştur")
    parser.add_argument("--input", "-i", type=str, help="Girdi JSON dosya yolu")
    parser.add_argument("--output-html", "-o", type=str, help="Çıktı HTML dosya yolu")
    parser.add_argument("--output-md", "-m", type=str, help="Çıktı Markdown dosya yolu")
    parser.add_argument("--output-json", "-j", type=str, help="Çıktı JSON dosya yolu")

    args = parser.parse_args(args_list)

    deck: Optional[SlideDeck] = None

    if args.demo == "information-economics" or (not args.input and not args.demo):
        deck = build_information_economics_deck()
    elif args.input:
        in_path = Path(args.input)
        if not in_path.exists():
            print(f"Hata: Girdi dosyası bulunamadı: {in_path}", file=sys.stderr)
            return 1
        data = json.loads(in_path.read_text(encoding="utf-8"))
        deck = SlideDeck.model_validate(data)

    if not deck:
        print("Hata: Slayt destesi oluşturulamadı.", file=sys.stderr)
        return 1

    # Render HTML
    if args.output_html:
        out_h = Path(args.output_html)
        out_h.parent.mkdir(parents=True, exist_ok=True)
        html_content = HTMLSlideRenderer().render(deck)
        out_h.write_text(html_content, encoding="utf-8")
        print(f"✅ HTML5 Slayt Destesi Oluşturuldu: {out_h}")

    # Render Markdown
    if args.output_md:
        out_m = Path(args.output_md)
        out_m.parent.mkdir(parents=True, exist_ok=True)
        md_content = MarkdownSlideRenderer().render(deck)
        out_m.write_text(md_content, encoding="utf-8")
        print(f"✅ Markdown Slayt Destesi Oluşturuldu: {out_m}")

    # Export JSON
    if args.output_json:
        out_j = Path(args.output_json)
        out_j.parent.mkdir(parents=True, exist_ok=True)
        out_j.write_text(deck.model_dump_json(indent=2), encoding="utf-8")
        print(f"✅ JSON Slayt Verisi Kaydedildi: {out_j}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
