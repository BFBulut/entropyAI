---
name: slide-deck-architect
description: "Interactive HTML5, KaTeX & Markdown Slide Deck Synthesis Engine for Financial Engineering, Academic Research & Corporate Presentations."
version: 1.0.0
author: Google Deepmind / Antigravity Team
tags: [slides, presentation, html5, katex, obsidian, financial-engineering, data-visualization]
---

# 📽️ SlideDeckArchitect Skill

`slide-deck-architect` is an autonomous slide synthesis engine designed to transform deep research, quantitative finance formulations, microstructural theories, and architectural decisions into:
1. **Interactive Standalone HTML5 Presentations**: Modern, responsive slide decks featuring KaTeX LaTeX rendering, dark high-contrast themes, keyboard navigation (`ArrowRight`, `ArrowLeft`, `Space`), slide timer, progress bar, and fullscreen mode (`F`).
2. **Obsidian / Marp Native Markdown Decks**: Standard `---` slide delimiter format ready for presentation inside Obsidian or Marp CLI.
3. **JSON Slide Data Interchange**: Fully typed Pydantic data schemas.

---

## 🚀 Key Capabilities

- **Mathematical Formula Rendering**: Native KaTeX support for complex mathematical physics and financial econometrics formulas (e.g. $\lambda^*$, $\rho^2 = \text{Corr}(P, \theta)^2$, $m_t = m_{t-1} + \psi \epsilon_t$, $\Omega = F F'$, $IS_j = \frac{([\psi F]_j)^2}{\psi \Omega \psi'}$).
- **Multiple Slide Archetypes**:
  - `TITLE`: Cover slide with presenter, institution, date, and subtitle.
  - `THEORY_CORE`: Core mathematical or conceptual exposition with formula blocks.
  - `TWO_COLUMN`: Side-by-side comparative analysis or derivation vs intuition.
  - `EQUATION_BREAKDOWN`: Step-by-step mathematical decomposition with variable legend.
  - `IMPLICATIONS`: Empirical, regulatory, and market microstructure takeaways.
  - `CONCLUSION`: Final synthesis, open research directions, and Q&A.
- **Zero Heavy Dependencies**: Pure Python standard library + Pydantic for generation, with self-contained CDN fallbacks for web browsers.

---

## 🛠️ CLI Usage

```bash
# Generate presentation deck from JSON specification
python -m skills.slide_deck_architect.slide_engine --input deck.json --output-html presentation.html --output-md presentation.md

# Generate from built-in templates
python -m skills.slide_deck_architect.slide_engine --demo "information-economics" --output-html slides.html
```

---

## 🐍 Programmatic Python API

```python
from skills.slide_deck_architect import (
    SlideDeckBuilder,
    HTMLSlideRenderer,
    MarkdownSlideRenderer,
    SlideType
)

builder = SlideDeckBuilder(
    title="Bilgi Edinme Dengesi ve Fiyat Keşfi",
    subtitle="Grossman-Stiglitz Paradoksu & Hasbrouck Bilgi Paylaşımı",
    author="Entropy AI",
    date="2026-09-06"
)

builder.add_slide(
    title="Grossman-Stiglitz (1980) Paradoksu",
    slide_type=SlideType.THEORY_CORE,
    bullets=[
        "Bilgi edinme maliyeti c > 0 olduğunda piyasalar tam etkin olamaz.",
        "Fiyatlar tüm özel bilgiyi yansıtırsa kimse bilgi toplamaz."
    ],
    equation=r"\frac{\text{Var}(\theta \mid \text{uninformed})}{\text{Var}(\theta \mid \text{informed})} = e^{2ac}",
    notes="Piyasaların tam bilgi etkinliğinin imkansızlığının matematiksel ispatı."
)

deck = builder.build()

# Render HTML5
html = HTMLSlideRenderer().render(deck)

# Render Markdown
md = MarkdownSlideRenderer().render(deck)
```
