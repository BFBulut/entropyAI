"""
SlideDeckArchitect: Interactive HTML5, KaTeX & Markdown Slide Deck Synthesis Engine.
"""

from .slide_engine import (
    SlideDeck,
    SlideItem,
    SlideContentBlock,
    SlideType,
    SlideDeckBuilder,
    HTMLSlideRenderer,
    MarkdownSlideRenderer,
)

__all__ = [
    "SlideDeck",
    "SlideItem",
    "SlideContentBlock",
    "SlideType",
    "SlideDeckBuilder",
    "HTMLSlideRenderer",
    "MarkdownSlideRenderer",
]
