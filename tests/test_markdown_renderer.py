"""Unit tests for high-fidelity Markdown and Diagram Renderer."""

import pytest
from entropy.ui.widgets.markdown_renderer import render_markdown_to_html, MermaidSvgGenerator

def test_mermaid_svg_flowchart():
    code = """
    graph TD
    A["Start Node"] --> B["Process Node"]
    B -->|Success| C["End Node"]
    """
    svg = MermaidSvgGenerator.render_to_svg(code)
    assert "<svg" in svg
    assert "</svg>" in svg
    assert "Start Node" in svg
    assert "End Node" in svg
    assert "marker-end" in svg

def test_mermaid_svg_state_diagram():
    code = """
    stateDiagram-v2
    [*] --> PENDING: Ingestion
    PENDING --> IN_PROGRESS: Assigned
    IN_PROGRESS --> COMPLETED: Done
    """
    svg = MermaidSvgGenerator.render_to_svg(code)
    assert "<svg" in svg
    assert "Durum Makinesi" in svg
    assert "PENDING" in svg
    assert "COMPLETED" in svg

def test_render_markdown_to_html_full():
    md = """# Master Rapor

Giriş paragrafı ve **kalın metin**.

```mermaid
graph LR
Node1 --> Node2
```

| Kolon A | Kolon B |
|---------|---------|
| Veri 1  | Veri 2  |

$$E = mc^2$$

- Madde 1
- Madde 2
"""
    html_out = render_markdown_to_html(md)
    assert "<h1" in html_out
    assert "data:image/svg+xml;base64," in html_out
    assert "<table" in html_out
    assert "Kolon A" in html_out
    assert "Cambria Math" in html_out
    assert "<li" in html_out

def test_mermaid_svg_pie_chart():
    code = """
    pie title Portföy Dağılımı
    "Hisse Senetleri" : 45
    "Tahvil" : 35
    "Nakit" : 20
    """
    svg = MermaidSvgGenerator.render_to_svg(code)
    assert "<svg" in svg
    assert "</svg>" in svg
    assert "Portföy Dağılımı" in svg
    assert "Hisse Senetleri" in svg
    assert "Tahvil" in svg
    assert "TOPLAM" in svg

def test_mermaid_svg_sequence_diagram():
    code = """
    sequenceDiagram
    Client->>Server: İstek Gönder
    Server-->>Client: Yanıt Döndür
    """
    svg = MermaidSvgGenerator.render_to_svg(code)
    assert "<svg" in svg
    assert "Sıralı İletişim" in svg
    assert "Client" in svg
    assert "Server" in svg

def test_render_markdown_image_resolution(tmp_path):
    # Test remote image preservation
    md_remote = "![Grafik](https://example.com/chart.png)"
    html_remote = render_markdown_to_html(md_remote)
    assert 'src="https://example.com/chart.png"' in html_remote

    # Test local relative image
    local_img = tmp_path / "asset.png"
    local_img.write_text("fake")
    md_local = "![Yerel](asset.png)"
    html_local = render_markdown_to_html(md_local, base_dir=tmp_path)
    assert local_img.as_uri() in html_local
