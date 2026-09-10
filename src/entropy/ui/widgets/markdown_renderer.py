"""High-Fidelity Cybernetic Markdown & Diagram Renderer for Entropy AI.

Converts Markdown, Mermaid diagrams, Mathematical formulas, and Tables
into rich, beautiful HTML with embedded SVG diagrams supported natively by Qt QTextBrowser.
"""

import base64
import html
import math
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from entropy.core.config import config
from entropy.ui.design.embedded import palette as _embedded_palette
from entropy.ui.themes.cyber_theme import CYBER_THEME, READING_TOKENS as RT, reading_css

# --------------------------------------------------------------------------- #
# Gomulu belge tema koprusu (Faz 12-D.2, denetim D12-04 / D12-09)
#
# Bu dosya eskiden kendi "neon" paletini tasiyordu (saf tayf kroma 255 renkler). SVG cizicileri artik renklerini TOKENS / TOKENS["viz"] uzerinden
# `entropy.ui.design.embedded.palette()` ile alir. Qt zengin metin motoru CSS
# degiskeni tanimadigi icin degerler burada duz onaltiliga acilir.
# --------------------------------------------------------------------------- #

#: Okuma yuzeyinin o anki kullanilabilir genisligi (px). SVG'ler bu degere gore
#: olceklenir: `viewBox` mantiksal koordinati korur, `width/height` yalnizca
#: sunum olcusudur -> yatay kaydirma cikmaz (denetim D12-09).
_READER_WIDTH = [860]

#: SVG cevresindeki okuma dolgusu (reading_css body padding + kenarlik).
READER_GUTTER = 56


def set_reader_width(width: int) -> int:
    """Okuma yuzeyi genisligini bildirir (okuyucunun resizeEvent'i cagirir)."""
    try:
        value = int(width)
    except (TypeError, ValueError):
        return _READER_WIDTH[0]
    _READER_WIDTH[0] = max(280, min(2400, value))
    return _READER_WIDTH[0]


def reader_width() -> int:
    return _READER_WIDTH[0]


def _pal():
    """Gomulu govdelerin renk tablosu (tema degisince kendiliginden doner)."""
    return _embedded_palette()


def _svg_open(total_w: int, total_h: int) -> str:
    """Akiskan <svg> acilisi: mantiksal viewBox + kutuya sigan sunum olcusu."""
    avail = max(240, reader_width() - READER_GUTTER)
    scale = min(1.0, avail / float(total_w or 1))
    render_w = int(round(total_w * scale))
    render_h = int(round(total_h * scale))
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{render_w}" height="{render_h}" '
        f'viewBox="0 0 {total_w} {total_h}" preserveAspectRatio="xMidYMid meet">'
    )


def _escape(text: str) -> str:
    """Safely escape HTML entities."""
    return html.escape(text)


class MermaidSvgGenerator:
    """Generates crisp, high-contrast cybernetic SVG diagrams from Mermaid specifications."""

    @classmethod
    def render_to_svg(cls, mermaid_code: str) -> str:
        """Parse mermaid diagram syntax and return a complete SVG string."""
        P = _pal()
        lines = [line.strip() for line in mermaid_code.strip().splitlines() if line.strip()]
        if not lines:
            return ""

        header = lines[0].lower()
        if "pie" in header:
            return cls._render_pie_chart(lines)
        elif "statediagram" in header:
            return cls._render_state_diagram(lines[1:])
        elif "graph" in header or "flowchart" in header:
            is_lr = "lr" in header
            return cls._render_flowchart(lines[1:], is_horizontal=is_lr)
        elif "sequencediagram" in header:
            return cls._render_sequence_diagram(lines[1:])
        else:
            return cls._render_flowchart(lines, is_horizontal=False)

    @classmethod
    def _render_flowchart(cls, lines: List[str], is_horizontal: bool = False) -> str:
        """Render node-edge flowchart to SVG."""
        P = _pal()
        nodes: Dict[str, str] = {}
        edges: List[Tuple[str, str, str]] = []

        # Parse nodes and connections
        for line in lines:
            if line.startswith("subgraph") or line.startswith("end"):
                continue
            # Edge pattern: A --> B or A["Label A"] -->|Condition| B["Label B"]
            # or A -- label --> B
            parts = re.split(r'-->|---|==>|-\.->', line)
            if len(parts) >= 2:
                left = parts[0].strip()
                right = parts[1].strip()
                label = ""

                # Extract edge condition |cond|
                cond_match = re.search(r'\|([^\|]+)\|', right)
                if cond_match:
                    label = cond_match.group(1).strip()
                    right = right[:cond_match.start()] + right[cond_match.end():]
                    right = right.strip()
                elif "--" in left:
                    sub = left.split("--")
                    if len(sub) == 2:
                        left = sub[0].strip()
                        label = sub[1].strip().strip('"').strip("'")

                node_a, text_a = cls._parse_node(left)
                node_b, text_b = cls._parse_node(right)

                if node_a:
                    nodes[node_a] = text_a or nodes.get(node_a, node_a)
                if node_b:
                    nodes[node_b] = text_b or nodes.get(node_b, node_b)

                if node_a and node_b:
                    edges.append((node_a, node_b, label))
            else:
                node_id, text = cls._parse_node(line)
                if node_id:
                    nodes[node_id] = text or nodes.get(node_id, node_id)

        if not nodes:
            # Fallback simple card
            return cls._render_generic_card("Diyagram Akışı", lines)

        node_keys = list(nodes.keys())
        node_width = 160
        node_height = 42

        if is_horizontal:
            # Layout left-to-right
            spacing_x = 100
            total_w = max(400, len(node_keys) * (node_width + spacing_x) + 40)
            total_h = 220
            pos = {}
            for idx, k in enumerate(node_keys):
                x = 30 + idx * (node_width + spacing_x)
                y = 90 + (25 if idx % 2 == 1 else -25)
                pos[k] = (x, y)
        else:
            # Layout top-to-bottom
            spacing_y = 65
            total_w = 640
            total_h = max(200, len(node_keys) * (node_height + spacing_y) + 40)
            pos = {}
            for idx, k in enumerate(node_keys):
                x = (total_w - node_width) // 2
                y = 30 + idx * (node_height + spacing_y)
                pos[k] = (x, y)

        svg_parts = [
            _svg_open(total_w, total_h),
            '<defs>',
            '  <linearGradient id="nodeGrad" x1="0%" y1="0%" x2="100%" y2="100%">',
            f'    <stop offset="0%" stop-color="{P["raised"]}"/>',
            f'    <stop offset="100%" stop-color="{P["surface"]}"/>',
            '  </linearGradient>',
            '  <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">',
            '    <feGaussianBlur stdDeviation="3" result="blur" />',
            '    <feComposite in="SourceGraphic" in2="blur" operator="over" />',
            '  </filter>',
            '  <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">',
            f'    <path d="M 0 1 L 10 5 L 0 9 z" fill="{P["accent"]}" />',
            '  </marker>',
            '</defs>',
            f'<rect width="{total_w}" height="{total_h}" rx="8" fill="{P["surface"]}" stroke="{P["line_strong"]}" stroke-width="1"/>'
        ]

        # Draw edges
        for a, b, label in edges:
            if a in pos and b in pos:
                x1, y1 = pos[a]
                x2, y2 = pos[b]
                start_x = x1 + node_width // 2
                start_y = y1 + node_height
                end_x = x2 + node_width // 2
                end_y = y2

                if is_horizontal:
                    start_x = x1 + node_width
                    start_y = y1 + node_height // 2
                    end_x = x2
                    end_y = y2 + node_height // 2

                svg_parts.append(
                    f'<line x1="{start_x}" y1="{start_y}" x2="{end_x}" y2="{end_y}" '
                    f'stroke="{P["accent"]}" stroke-width="2" marker-end="url(#arrow)" opacity="0.85"/>'
                )
                if label:
                    mid_x = (start_x + end_x) // 2
                    mid_y = (start_y + end_y) // 2 - 6
                    svg_parts.append(
                        f'<rect x="{mid_x - 30}" y="{mid_y - 10}" width="60" height="18" rx="3" fill="{P["bg"]}" stroke="{P["line_strong"]}" stroke-width="1"/>'
                        f'<text x="{mid_x}" y="{mid_y + 3}" fill="{P["ok"]}" font-family="Segoe UI, sans-serif" font-size="10" text-anchor="middle">{_escape(label[:12])}</text>'
                    )

        # Draw nodes
        for k, (x, y) in pos.items():
            label = nodes.get(k, k)
            short_lbl = label[:24] + ("..." if len(label) > 24 else "")
            svg_parts.append(
                f'<g transform="translate({x}, {y})">'
                f'  <rect width="{node_width}" height="{node_height}" rx="6" fill="url(#nodeGrad)" stroke="{P["accent"]}" stroke-width="1.5" filter="url(#glow)"/>'
                f'  <text x="{node_width // 2}" y="{node_height // 2 + 5}" fill="{P["text"]}" font-family="Segoe UI, sans-serif" font-size="11" font-weight="bold" text-anchor="middle">{_escape(short_lbl)}</text>'
                f'</g>'
            )

        svg_parts.append('</svg>')
        return "".join(svg_parts)

    @classmethod
    def _render_pie_chart(cls, lines: List[str]) -> str:
        """Render Mermaid pie chart cleanly to cybernetic SVG."""
        P = _pal()
        title = "Pasta Grafiği (Pie Distribution)"
        data: List[Tuple[str, float]] = []

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
            lower_l = line_str.lower()
            if lower_l.startswith("pie"):
                line_str = line_str[3:].strip()
                if not line_str:
                    continue
                lower_l = line_str.lower()

            if lower_l.startswith("title"):
                title = line_str[5:].strip().strip(':').strip()
                continue
            elif lower_l == "showdata":
                continue

            # Check for "Label" : value or Label : value
            parts = line_str.split(":", 1)
            if len(parts) == 2:
                lbl = parts[0].strip().strip('"').strip("'")
                val_str = parts[1].strip().split()[0]
                try:
                    val = float(val_str)
                    data.append((lbl, val))
                except ValueError:
                    pass

        if not data:
            return cls._render_generic_card(title, lines)

        total = sum(v for _, v in data)
        if total <= 0:
            return cls._render_generic_card(title, lines)

        # Kategorik seri paleti artik `TOKENS["viz"].kind*` ailesinden gelir
        # (saf tayf renk yok, hepsinin kontrasti olculu).
        palette = P["series"]

        w = 640
        h = max(280, len(data) * 28 + 80)
        cx, cy, r = 160, h // 2, min(90, (h - 60) // 2)

        svg = [
            _svg_open(w, h),
            f'<rect width="{w}" height="{h}" rx="8" fill="{P["surface"]}" stroke="{P["line_strong"]}" stroke-width="1"/>',
            f'<text x="20" y="28" fill="{P["accent"]}" font-family="Segoe UI, sans-serif" font-size="13" font-weight="bold">{_escape(title)}</text>'
        ]

        # Draw wedges
        start_angle = -math.pi / 2
        for idx, (lbl, val) in enumerate(data):
            slice_angle = (val / total) * 2 * math.pi
            end_angle = start_angle + slice_angle
            color = palette[idx % len(palette)]

            if len(data) == 1 or abs(slice_angle - 2 * math.pi) < 1e-4:
                svg.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}" fill-opacity="0.85" stroke="{P["surface"]}" stroke-width="2"/>')
            else:
                x1 = cx + r * math.cos(start_angle)
                y1 = cy + r * math.sin(start_angle)
                x2 = cx + r * math.cos(end_angle)
                y2 = cy + r * math.sin(end_angle)
                large_arc = 1 if slice_angle > math.pi else 0

                path_d = f"M {cx} {cy} L {x1:.2f} {y1:.2f} A {r} {r} 0 {large_arc} 1 {x2:.2f} {y2:.2f} Z"
                svg.append(f'<path d="{path_d}" fill="{color}" fill-opacity="0.85" stroke="{P["surface"]}" stroke-width="1.5"/>')

            # Legend item on right side
            leg_y = 65 + idx * 26
            pct = (val / total) * 100
            val_display = f"{val:g}" if val.is_integer() else f"{val:.1f}"
            svg.append(
                f'<g transform="translate(300, {leg_y})">'
                f'  <rect x="0" y="0" width="14" height="14" rx="3" fill="{color}"/>'
                f'  <text x="22" y="11" fill="{P["text"]}" font-family="Segoe UI" font-size="11">{_escape(lbl[:25])}</text>'
                f'  <text x="240" y="11" fill="{P["text_muted"]}" font-family="Consolas" font-size="11" text-anchor="end">{val_display} ({pct:.1f}%)</text>'
                f'</g>'
            )

            start_angle = end_angle

        # Inner donut cutout
        inner_r = r // 2
        svg.append(f'<circle cx="{cx}" cy="{cy}" r="{inner_r}" fill="{P["surface"]}" stroke="{P["line_strong"]}" stroke-width="1"/>')
        svg.append(f'<text x="{cx}" y="{cy + 4}" fill="{P["accent"]}" font-family="Segoe UI" font-size="10" font-weight="bold" text-anchor="middle">TOPLAM</text>')

        svg.append('</svg>')
        return "".join(svg)

    @classmethod
    def _render_state_diagram(cls, lines: List[str]) -> str:
        """Render state diagrams cleanly to SVG."""
        P = _pal()
        transitions: List[Tuple[str, str, str]] = []
        states = set()

        for line in lines:
            line = line.strip()
            if "-->" in line:
                parts = line.split("-->")
                src = parts[0].strip()
                dst_part = parts[1].strip()
                lbl = ""
                if ":" in dst_part:
                    dst, lbl = dst_part.split(":", 1)
                    dst = dst.strip()
                    lbl = lbl.strip()
                else:
                    dst = dst_part

                src_name = "Başlangıç" if src == "[*]" else src
                dst_name = "Bitiş" if dst == "[*]" else dst
                states.add(src_name)
                states.add(dst_name)
                transitions.append((src_name, dst_name, lbl))

        states_list = sorted(list(states))
        total_w = 640
        total_h = max(240, len(transitions) * 50 + 70)

        svg = [
            _svg_open(total_w, total_h),
            '<defs>',
            '  <marker id="arrow-green" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">',
            f'    <path d="M 0 1 L 10 5 L 0 9 z" fill="{P["ok"]}" />',
            '  </marker>',
            '</defs>',
            f'<rect width="{total_w}" height="{total_h}" rx="8" fill="{P["surface"]}" stroke="{P["line_strong"]}" stroke-width="1"/>',
            f'<text x="20" y="26" fill="{P["accent"]}" font-family="Segoe UI, sans-serif" font-size="12" font-weight="bold">Durum Makinesi (State Transition Flow)</text>'
        ]

        y = 55
        for src, dst, lbl in transitions:
            svg.append(
                f'<g transform="translate(20, {y})">'
                f'  <rect x="0" y="0" width="130" height="30" rx="4" fill="{P["raised"]}" stroke="{P["accent"]}" stroke-width="1"/>'
                f'  <text x="65" y="19" fill="{P["accent"]}" font-family="Segoe UI" font-size="11" font-weight="bold" text-anchor="middle">{_escape(src[:16])}</text>'
                f'  <line x1="135" y1="15" x2="275" y2="15" stroke="{P["ok"]}" stroke-width="2" marker-end="url(#arrow-green)"/>'
                f'  <text x="205" y="10" fill="{P["text_muted"]}" font-family="Segoe UI" font-size="9" text-anchor="middle">{_escape(lbl[:22])}</text>'
                f'  <rect x="280" y="0" width="130" height="30" rx="4" fill="{P["raised"]}" stroke="{P["ok"]}" stroke-width="1"/>'
                f'  <text x="345" y="19" fill="{P["ok"]}" font-family="Segoe UI" font-size="11" font-weight="bold" text-anchor="middle">{_escape(dst[:16])}</text>'
                f'</g>'
            )
            y += 45

        svg.append('</svg>')
        return "".join(svg)

    @classmethod
    def _render_sequence_diagram(cls, lines: List[str]) -> str:
        """Render sequence diagram cleanly to SVG."""
        P = _pal()
        messages: List[Tuple[str, str, str]] = []
        participants = set()

        for line in lines:
            line = line.strip()
            match = re.search(r'([A-Za-z0-9_\-]+)\s*(?:->>|-->>|->)\s*([A-Za-z0-9_\-]+)\s*:\s*(.+)', line)
            if match:
                src, dst, msg = match.groups()
                participants.add(src)
                participants.add(dst)
                messages.append((src, dst, msg))

        parts_list = sorted(list(participants))
        total_w = max(500, len(parts_list) * 160 + 40)
        total_h = max(240, len(messages) * 44 + 90)

        svg = [
            _svg_open(total_w, total_h),
            f'<rect width="{total_w}" height="{total_h}" rx="8" fill="{P["surface"]}" stroke="{P["line_strong"]}" stroke-width="1"/>',
            f'<text x="20" y="26" fill="{P["accent"]}" font-family="Segoe UI, sans-serif" font-size="12" font-weight="bold">Sıralı İletişim (Sequence Flow)</text>'
        ]

        part_x = {}
        for idx, p in enumerate(parts_list):
            x = 50 + idx * 160
            part_x[p] = x
            svg.append(
                f'<rect x="{x - 50}" y="45" width="100" height="26" rx="4" fill="{P["raised"]}" stroke="{P["accent"]}" stroke-width="1"/>'
                f'<text x="{x}" y="62" fill="{P["accent"]}" font-family="Segoe UI" font-size="11" font-weight="bold" text-anchor="middle">{_escape(p)}</text>'
                f'<line x1="{x}" y1="71" x2="{x}" y2="{total_h - 15}" stroke="{P["line_strong"]}" stroke-dasharray="4" stroke-width="1"/>'
            )

        cur_y = 95
        for src, dst, msg in messages:
            if src in part_x and dst in part_x:
                x1 = part_x[src]
                x2 = part_x[dst]
                color = P["ok"] if x1 < x2 else P["warn"]
                svg.append(
                    f'<line x1="{x1}" y1="{cur_y}" x2="{x2}" y2="{cur_y}" stroke="{color}" stroke-width="2"/>'
                    f'<text x="{(x1 + x2) // 2}" y="{cur_y - 5}" fill="{P["text"]}" font-family="Segoe UI" font-size="10" text-anchor="middle">{_escape(msg[:35])}</text>'
                )
                cur_y += 38

        svg.append('</svg>')
        return "".join(svg)

    @classmethod
    def _render_generic_card(cls, title: str, lines: List[str]) -> str:
        """Render a clean cybernetic info card when complex graph syntax is present."""
        P = _pal()
        w = 600
        h = max(160, len(lines) * 22 + 60)
        svg = [
            _svg_open(w, h),
            f'<rect width="{w}" height="{h}" rx="8" fill="{P["surface"]}" stroke="{P["accent"]}" stroke-width="1.2"/>',
            f'<text x="20" y="28" fill="{P["accent"]}" font-family="Segoe UI" font-size="13" font-weight="bold">{title}</text>'
        ]
        y = 55
        for l in lines[:10]:
            clean_l = _escape(l.strip())
            svg.append(f'<text x="25" y="{y}" fill="{P["text"]}" font-family="Consolas" font-size="11">{clean_l[:75]}</text>')
            y += 20
        svg.append('</svg>')
        return "".join(svg)

    @classmethod
    def _parse_node(cls, token: str) -> Tuple[str, str]:
        """Extract node id and label from tokens like A["Label"] or Node1."""
        token = token.strip()
        bracket_match = re.match(r'([A-Za-z0-9_\-]+)\s*[\[\(\{\>](.*)[\]\)\}\>]', token)
        if bracket_match:
            node_id = bracket_match.group(1).strip()
            label = bracket_match.group(2).strip().strip('"').strip("'")
            return node_id, label
        simple_id = re.sub(r'[^A-Za-z0-9_\-]', '', token)
        return simple_id, simple_id


def _render_markdown_body(markdown_text: str, base_dir: Optional[Path] = None) -> str:
    """
    Markdown gövdesini satır içi stilli HTML'e çevirir (sarmalayıcı yok).

    Hem sohbet balonları (parça) hem de rapor okuyucu (tam belge) bunu kullanır;
    böylece üç yüzeyde de tek tasarım sistemi geçerlidir.
    """
    P = _pal()
    if not markdown_text:
        return ""

    # 1. Normalize line breaks and extract YAML frontmatter if present
    text = markdown_text.replace('\r\n', '\n').replace('\r', '\n').lstrip()
    metadata_banner_html = ""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            fm_text = parts[1].strip()
            text = parts[2].strip()
            meta: Dict[str, Any] = {}
            for line in fm_text.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    k = k.strip().lower()
                    v = v.strip().strip('"').strip("'")
                    if k == "tags":
                        if v.startswith("[") and v.endswith("]"):
                            meta[k] = [t.strip().strip('"').strip("'") for t in v[1:-1].split(",") if t.strip()]
                        else:
                            meta[k] = [v]
                    else:
                        meta[k] = v

            if meta:
                tags_pills = ""
                if "tags" in meta:
                    for t in meta["tags"][:6]:
                        tags_pills += f'<span style="background-color:{RT["accent_soft"]}; color:{RT["accent"]}; border-radius:10px; padding:2px 10px; margin-right:6px; font-size:11px;">#{_escape(t)}</span>'

                title_text = meta.get("title") or ""
                date_text = meta.get("date") or ""
                agent_text = meta.get("agent") or ""
                proj_text = meta.get("project") or ""
                skill_text = meta.get("skill") or ""

                info_line = []
                if date_text:
                    info_line.append(f"{date_text}")
                if agent_text:
                    info_line.append(f"{agent_text}")
                if proj_text:
                    info_line.append(f"Proje: {proj_text}")
                if skill_text:
                    info_line.append(f"Yetenek: {skill_text}")
                meta_info = " &nbsp;|&nbsp; ".join(info_line)

                metadata_banner_html = (
                    f'<div style="background-color:{RT["surface_raised"]}; border-left:3px solid {RT["accent"]}; border-radius:{RT["radius"]}; padding:14px 18px; margin-bottom:20px;">'
                )
                if title_text:
                    metadata_banner_html += f'<div style="color:{RT["text"]}; font-size:18px; font-weight:600; margin-bottom:6px;">{_escape(title_text)}</div>'
                if meta_info:
                    metadata_banner_html += f'<div style="color:{RT["text_dim"]}; font-size:13px; margin-bottom:8px;">{meta_info}</div>'
                if tags_pills:
                    metadata_banner_html += f'<div style="margin-top:6px;">{tags_pills}</div>'
                metadata_banner_html += '</div>'

    # 2. Extract and convert ```mermaid ... ``` blocks to SVG images
    def replace_mermaid(match):
        code = match.group(1).strip()
        try:
            svg = MermaidSvgGenerator.render_to_svg(code)
            if svg:
                b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
                return (
                    f'\n<div style="text-align:center; margin:16px 0;">'
                    f'<img src="data:image/svg+xml;base64,{b64}" style="max-width:100%; border-radius:8px;" />'
                    f'</div>\n'
                )
        except Exception:
            pass
        # Denetim D12-09: bu yedek blokta `white-space` yoktu ve okuma yüzeyinde
        # yatay kaydırma üretiyordu; artık sarıyor.
        return (
            f'<pre style="background:{RT["surface_raised"]}; color:{RT["accent"]};'
            f' padding:12px 16px; border-radius:{RT["radius"]}; font-family:{RT["font_mono"]};'
            f' white-space:pre-wrap; word-wrap:break-word;">'
            f'<code>{_escape(code)}</code></pre>'
        )

    text = re.sub(r'```mermaid\s*\n(.*?)```', replace_mermaid, text, flags=re.DOTALL | re.IGNORECASE)

    # 3. Extract and style generic code blocks ```lang ... ```
    # Tasarım: siyah şerit yerine yüzeyle uyumlu yumuşak köşeli kart, solda
    # renk şeridi ve pil biçiminde dil etiketi.
    def replace_code_block(match):
        lang = match.group(1).strip() or "kod"
        code_content = match.group(2).strip()
        return (
            f'<div style="background-color:{RT["surface_raised"]}; border:1px solid {RT["divider_soft"]};'
            f' border-left:3px solid {RT["accent"]}; border-radius:{RT["radius"]};'
            f' margin:{RT["block_margin"]} 0; padding:12px 16px;">'
            f'<div style="margin-bottom:8px;">'
            f'<span style="background-color:{RT["accent_soft"]}; color:{RT["accent"]};'
            f' border-radius:10px; padding:2px 10px; font-size:11px; font-weight:600;'
            f' letter-spacing:0.6px; font-family:{RT["font_mono"]};">{_escape(lang.upper())}</span>'
            f'</div>'
            f'<pre style="margin:0; font-family:{RT["font_mono"]}; font-size:{RT["font_size_mono"]};'
            f' line-height:1.5; color:{RT["text"]}; white-space:pre-wrap;">'
            f'<code>{_escape(code_content)}</code></pre>'
            f'</div>'
        )

    text = re.sub(r'```([a-zA-Z0-9_\-]*)\s*\n(.*?)```', replace_code_block, text, flags=re.DOTALL)

    # 4. Math display blocks $$ ... $$
    def replace_math_block(match):
        formula = match.group(1).strip()
        return (
            f'<div style="background-color:{RT["surface_raised"]}; border-left:3px solid {RT["accent_alt"]}; border-radius:{RT["radius"]}; padding:10px 18px; margin:{RT["block_margin"]} 0; text-align:center;">'
            f'<span style="color:{RT["accent_alt"]}; font-family:Cambria Math, Georgia, serif; font-size:14px; font-style:italic;">{_escape(formula)}</span>'
            f'</div>'
        )

    text = re.sub(r'\$\$(.*?)\$\$', replace_math_block, text, flags=re.DOTALL)

    # 5. Inline Math $...$
    # Satır içi matematik: renk belirteçten gelir (ham hex yok).
    text = re.sub(
        r'(?<!\$)\$(?!\$)(.*?)\$',
        '<i style="color:%s; font-family:Cambria Math, serif;">\\1</i>' % _pal()["ok"],
        text,
    )

    # 6. Parse Markdown Tables
    lines = text.split('\n')
    processed_lines = []
    in_table = False
    table_rows = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('|') and stripped.endswith('|'):
            in_table = True
            # Check if separator line
            if re.match(r'^\|[\s\-:|]+\|$', stripped):
                continue
            cols = [c.strip() for c in stripped[1:-1].split('|')]
            table_rows.append(cols)
        else:
            if in_table:
                # Flush table to HTML
                table_html = _build_table_html(table_rows)
                processed_lines.append(table_html)
                table_rows = []
                in_table = False
            processed_lines.append(line)

    if in_table and table_rows:
        processed_lines.append(_build_table_html(table_rows))

    text = '\n'.join(processed_lines)

    # 7. Başlık hiyerarşisi: renk yerine boyut/ağırlık farkı, üstte nefes payı.
    text = re.sub(r'^#\s+(.+)$', rf'<h1 style="color:{RT["text"]}; font-size:18px; font-weight:600; border-bottom:1px solid {RT["divider"]}; padding-bottom:8px; margin-top:22px; margin-bottom:12px;">\1</h1>', text, flags=re.MULTILINE)
    text = re.sub(r'^##\s+(.+)$', rf'<h2 style="color:{RT["text"]}; font-size:18px; font-weight:600; margin-top:20px; margin-bottom:8px;">\1</h2>', text, flags=re.MULTILINE)
    text = re.sub(r'^###\s+(.+)$', rf'<h3 style="color:{RT["accent"]}; font-size:14px; font-weight:600; margin-top:16px; margin-bottom:6px;">\1</h3>', text, flags=re.MULTILINE)
    text = re.sub(r'^####\s+(.+)$', rf'<h4 style="color:{RT["text_dim"]}; font-size:13px; font-weight:600; letter-spacing:0.4px; margin-top:14px; margin-bottom:4px;">\1</h4>', text, flags=re.MULTILINE)

    # 8. Blockquotes: dolgu yok, yalnızca sol şerit.
    text = re.sub(r'^>\s*(.+)$', rf'<blockquote style="border-left:3px solid {RT["accent"]}; padding:4px 0 4px 14px; margin:10px 0; color:{RT["text_dim"]};">\1</blockquote>', text, flags=re.MULTILINE)

    # 9. Horizontal rules
    text = re.sub(r'^(?:---|\*\*\*|___)$', rf'<hr style="border:none; border-top:1px solid {RT["divider_soft"]}; margin:18px 0;" />', text, flags=re.MULTILINE)

    # 10. Bold, Italic, Inline Code
    text = re.sub(r'\*\*(.+?)\*\*', rf'<b style="color:{RT["text"]};">\1</b>', text)
    text = re.sub(r'\*(.+?)\*', rf'<i style="color:{RT["text_body"]};">\1</i>', text)
    text = re.sub(r'`([^`]+)`', rf'<code style="background-color:{RT["surface_soft"]}; color:{RT["accent"]}; border-radius:4px; padding:1px 6px; font-family:{RT["font_mono"]}; font-size:{RT["font_size_small"]};">\1</code>', text)

    # 11. Images: ![Alt](url_or_path)
    def resolve_image(match):
        alt = match.group(1)
        src = match.group(2).strip()
        if src.startswith(("http://", "https://", "data:")):
            return f'<div style="text-align:center; margin:12px 0;"><img src="{src}" alt="{alt}" style="max-width:95%; border:1px solid {_pal()["line"]}; border-radius:8px;" /></div>'
        try:
            img_path = Path(src)
            if not img_path.is_absolute() and base_dir:
                cand = base_dir / src
                if cand.exists():
                    src = cand.as_uri()
            elif img_path.exists():
                src = img_path.as_uri()
        except Exception:
            pass
        return f'<div style="text-align:center; margin:12px 0;"><img src="{src}" alt="{alt}" style="max-width:95%; border:1px solid {_pal()["line"]}; border-radius:8px;" /></div>'

    text = re.sub(r'!\[(.*?)\]\((.*?)\)', resolve_image, text)

    # 12. Links: [Label](url) — pil biçiminde, gövde metninden ayrışır.
    text = re.sub(
        r'\[(.*?)\]\((.*?)\)',
        rf'<a href="\2" style="color:{RT["accent"]}; background-color:{RT["accent_soft"]}; border-radius:10px; padding:1px 8px; text-decoration:none; font-weight:600;">\1</a>',
        text,
    )

    # 13. Bullet lists (madde işaretleri hizalı, satır aralığı nefesli)
    text = re.sub(rf'^\s*[-*+]\s+(.+)$', rf'<li style="color:{RT["text_body"]}; margin:5px 0; line-height:{RT["line_height"]};">\1</li>', text, flags=re.MULTILINE)

    # Wrap adjacent <li> in <ul>
    text = re.sub(r'(<li[^>]*>.*?</li>(?:\s*<li[^>]*>.*?</li>)*)', r'<ul style="margin:8px 0; padding-left:22px;">\1</ul>', text, flags=re.DOTALL)

    # 14. Paragraph line breaks (preserving existing HTML blocks)
    paragraphs = text.split('\n\n')
    formatted_paras = []
    for p in paragraphs:
        p_strip = p.strip()
        if not p_strip:
            continue
        if p_strip.startswith('<h1') or p_strip.startswith('<h2') or p_strip.startswith('<h3') \
           or p_strip.startswith('<div') or p_strip.startswith('<table') or p_strip.startswith('<ul') \
           or p_strip.startswith('<blockquote') or p_strip.startswith('<hr'):
            formatted_paras.append(p_strip)
        else:
            p_clean = p_strip.replace('\n', '<br/>')
            formatted_paras.append(
                f'<p style="margin:10px 0; line-height:{RT["line_height"]}; font-size:{RT["font_size_body"]}; color:{RT["text_body"]};">{p_clean}</p>'
            )

    body_html = '\n'.join(formatted_paras)
    if metadata_banner_html:
        body_html = metadata_banner_html + '\n' + body_html
    return body_html


def render_markdown_fragment(markdown_text: str, base_dir: Optional[Path] = None) -> str:
    """
    Markdown'ı GÖMÜLEBİLİR bir HTML parçasına dönüştürür (belge sarmalayıcısı yok).

    Sohbet balonları bunu kullanır. Eskiden balonların içine tam bir
    <html><body style="background-color:..."> belgesi gömülüyordu; Qt zengin
    metin motoru iç gövdenin arka planını boyadığı için mesajların arkasında
    siyah bloklar oluşuyordu. Rapor okuyucusu ise tam belgeyi kullanır.
    """
    if not markdown_text:
        return f'<div style="color:{RT["text_dim"]};">Henüz içerik yok.</div>'
    return _render_markdown_body(markdown_text, base_dir=base_dir)


def render_markdown_to_html(
    markdown_text: str,
    base_dir: Optional[Path] = None,
    reader_width: Optional[int] = None,
) -> str:
    """Markdown'ı, ortak okuma CSS'i gömülü eksiksiz bir HTML belgesine dönüştürür.

    `reader_width` verilirse gömülü SVG'ler o genişliğe göre ölçeklenir
    (denetim D12-09: sabit genişlikli diyagramlar yatay kaydırma üretiyordu).
    """
    if reader_width:
        set_reader_width(reader_width)
    if not markdown_text:
        return (
            f"<html><body style='background-color:{RT['surface_base']};"
            f" color:{RT['text_dim']};'>Henüz içerik yok.</body></html>"
        )
    body_html = _render_markdown_body(markdown_text, base_dir=base_dir)
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
{reading_css()}
</style>
</head>
<body>
{body_html}
</body>
</html>"""


def build_command_card_html(body_html: str) -> str:
    """
    Yerel slash komut çıktısını okunur bir kart olarak sarar.

    Sistem balonu ortalanmış küçük bir hap; `/handoff` gibi çok satırlı, yol ve
    madde içeren çıktılar orada okunmuyordu. Kart sol şeritli, sola hizalı ve
    okuma belirteçleriyle biçimlenmiş bir yüzey verir.
    """
    return (
        f"<div style='margin:0 0 14px 0; padding:10px 14px;"
        f" background-color:{RT['surface_raised']};"
        f" border-left:3px solid {RT['accent_warn']};"
        f" border-radius:{RT['radius_small']};'>"
        f"<div style='color:{RT['accent_warn']}; font-size:11px; font-weight:600;"
        f" letter-spacing:1px; margin-bottom:4px;'>KOMUT ÇIKTISI</div>"
        f"<div style='color:{RT['text_body']}; font-size:{RT['font_size_body']};"
        f" line-height:{RT['line_height']};'>{body_html}</div>"
        f"</div>"
    )


def build_chat_bubble_html(sender: str, text: str, is_system: bool = False) -> str:
    """
    Sohbet mesajı için tek kaynaklı HTML üretir (Chat modu + Zen sohbet paneli).

    Ağır balon yok: kullanıcı ve asistan yalnızca sol renk şeridi ve etiket ile
    ayrışır; asistan gövdesi markdown parçası olarak işlenir.
    """
    if is_system:
        return (
            f"<div style='margin:10px 0; text-align:center;'>"
            f"<span style='background-color:{RT['surface_raised']}; color:{RT['text_dim']};"
            f" border-radius:12px; padding:4px 14px; font-size:{RT['font_size_small']};'>"
            f"{text}</span></div>"
        )

    is_user = sender in ("Siz", "Sen")
    stripe = RT["accent_alt"] if is_user else RT["accent"]
    label = "Siz" if is_user else "Entropy AI"
    body = text if is_user else _render_markdown_body(text)
    # Kullanıcı mesajı yüzeyden bir kademe yükseltilir; asistan mesajı arka planla
    # aynı kalır. Kenarlık/dolgu yığmadan iki taraf ayırt edilir.
    surface = f" background-color:{RT['surface_raised']};" if is_user else ""
    return (
        f"<div style='margin:0 0 14px 0; padding:8px 12px 8px 14px;{surface}"
        f" border-left:3px solid {stripe}; border-radius:{RT['radius_small']};'>"
        f"<div style='color:{stripe}; font-size:11px; font-weight:600; letter-spacing:1px;"
        f" margin-bottom:4px;'>{label}</div>"
        f"<div style='color:{RT['text_body']}; font-size:{RT['font_size_body']};"
        f" line-height:{RT['line_height']};'>{body}</div>"
        f"</div>"
    )


def _build_table_html(rows: List[List[str]]) -> str:
    """
    Modern, okunaklı tablo: hücre dolgusu yok; ince ayırıcı çizgiler,
    vurgulu başlık satırı, hafif zebra ve sayısal sütunlarda sağa hizalama.
    """
    if not rows:
        return ""
    header_row = rows[0]
    data_rows = rows[1:]

    def _is_numeric(value: str) -> bool:
        v = value.strip().replace("%", "").replace(",", ".").replace(" ", "")
        v = v.lstrip("+-$₺€£").rstrip("$₺€£")
        if not v:
            return False
        try:
            float(v)
            return True
        except ValueError:
            return False

    # Sütun sayısal mı: veri satırlarının çoğunluğuna bakılır.
    col_count = max([len(header_row)] + [len(r) for r in data_rows]) if data_rows else len(header_row)
    numeric_cols = set()
    for c in range(col_count):
        values = [r[c] for r in data_rows if c < len(r) and r[c].strip()]
        if values and sum(1 for v in values if _is_numeric(v)) >= max(1, len(values) * 0.6):
            numeric_cols.add(c)

    html_parts = [
        f'<table style="border-collapse:collapse; width:100%; margin:{RT["block_margin"]} 0;">'
    ]
    html_parts.append('<thead><tr>')
    for idx, col in enumerate(header_row):
        align = "right" if idx in numeric_cols else "left"
        html_parts.append(
            f'<th style="color:{RT["accent"]}; padding:9px 12px; text-align:{align};'
            f' border-bottom:2px solid {RT["divider"]}; font-size:{RT["font_size_small"]};'
            f' font-weight:600; letter-spacing:0.3px;">{_escape(col)}</th>'
        )
    html_parts.append('</tr></thead><tbody>')

    for r_idx, r in enumerate(data_rows):
        # Zebra: siyah dolgu değil, yüzeyden yalnızca bir kademe fark.
        row_style = f' style="background-color:{RT["surface_raised"]};"' if r_idx % 2 == 1 else ""
        html_parts.append(f'<tr{row_style}>')
        for c_idx, col in enumerate(r):
            align = "right" if c_idx in numeric_cols else "left"
            html_parts.append(
                f'<td style="padding:8px 12px; text-align:{align};'
                f' border-bottom:1px solid {RT["divider_soft"]}; color:{RT["text_body"]};'
                f' font-size:{RT["font_size_small"]};">{_escape(col)}</td>'
            )
        html_parts.append('</tr>')

    html_parts.append('</tbody></table>')
    return "".join(html_parts)
