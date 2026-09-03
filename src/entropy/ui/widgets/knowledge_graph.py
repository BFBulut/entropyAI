"""Interactive Force-Directed Knowledge Graph Viewer using QWebEngineView."""

import json
from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout
from PySide6.QtWebEngineWidgets import QWebEngineView

from entropy.memory.obsidian.vault_manager import ObsidianVaultManager
from entropy.ui.themes.cyber_theme import CYBER_THEME

class KnowledgeGraphWidget(QFrame):
    """Visualizes Obsidian wikilinks and Supabase entities using force-directed interactive canvas."""

    def __init__(self, parent=None, vault_manager: Optional[ObsidianVaultManager] = None):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self.vault_manager = vault_manager or ObsidianVaultManager()

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(6)

        # Header
        title_label = QLabel("<b>🕸️ EXOCORTEX KNOWLEDGE GRAPH</b>")
        title_label.setStyleSheet(f"color: {CYBER_THEME['accent_cyan']}; font-size: 13px;")
        self.layout.addWidget(title_label)

        # WebEngine View
        self.web_view = QWebEngineView()
        self.web_view.setStyleSheet("background: #080B10; border-radius: 6px;")
        self.layout.addWidget(self.web_view)

        self.refresh_graph()

    def refresh_graph(self):
        """Re-generate graph JSON from vault and inject into WebEngine canvas."""
        graph_data = self.vault_manager.build_knowledge_graph()
        nodes_json = json.dumps(graph_data["nodes"])
        links_json = json.dumps(graph_data["links"])

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ margin: 0; background: #080B10; overflow: hidden; color: #F0F6FC; font-family: monospace; }}
                #canvas {{ width: 100vw; height: 100vh; display: block; }}
                #info {{ position: absolute; bottom: 10px; left: 10px; font-size: 11px; color: #00F0FF; background: rgba(5,7,10,0.8); padding: 4px 8px; border-radius: 4px; }}
            </style>
        </head>
        <body>
            <canvas id="canvas"></canvas>
            <div id="info">Nodes: <span id="nodeCount">0</span> | Links: <span id="linkCount">0</span></div>
            <script>
                const nodes = {nodes_json};
                const links = {links_json};
                document.getElementById('nodeCount').innerText = nodes.length;
                document.getElementById('linkCount').innerText = links.length;

                const canvas = document.getElementById('canvas');
                const ctx = canvas.getContext('2d');
                let width = window.innerWidth;
                let height = window.innerHeight;

                function resize() {{
                    width = canvas.width = window.innerWidth;
                    height = canvas.height = window.innerHeight;
                }}
                window.addEventListener('resize', resize);
                resize();

                // Assign positions if not preset
                nodes.forEach((n, idx) => {{
                    const angle = (idx / Math.max(1, nodes.length)) * Math.PI * 2;
                    n.x = (width / 2) + Math.cos(angle) * (120 + Math.random() * 60);
                    n.y = (height / 2) + Math.sin(angle) * (120 + Math.random() * 60);
                    n.vx = (Math.random() - 0.5) * 0.5;
                    n.vy = (Math.random() - 0.5) * 0.5;
                }});

                function draw() {{
                    ctx.fillStyle = '#080B10';
                    ctx.fillRect(0, 0, width, height);

                    // Draw Links
                    ctx.strokeStyle = 'rgba(0, 240, 255, 0.25)';
                    ctx.lineWidth = 1;
                    ctx.beginPath();
                    links.forEach(l => {{
                        const source = nodes.find(n => n.id === l.source);
                        const target = nodes.find(n => n.name === l.target || n.id.includes(l.target));
                        if (source && target) {{
                            ctx.moveTo(source.x, source.y);
                            ctx.lineTo(target.x, target.y);
                        }}
                    }});
                    ctx.stroke();

                    // Draw Nodes
                    nodes.forEach(n => {{
                        n.x += n.vx;
                        n.y += n.vy;
                        if (n.x < 30 || n.x > width - 30) n.vx *= -1;
                        if (n.y < 30 || n.y > height - 30) n.vy *= -1;

                        // Outer Glow
                        const grad = ctx.createRadialGradient(n.x, n.y, 2, n.x, n.y, 16);
                        grad.setColorAt(0, 'rgba(0, 240, 255, 0.8)');
                        grad.setColorAt(1, 'rgba(0, 240, 255, 0)');
                        ctx.fillStyle = grad;
                        ctx.beginPath();
                        ctx.arc(n.x, n.y, 16, 0, Math.PI * 2);
                        ctx.fill();

                        // Inner Circle
                        ctx.fillStyle = n.group === 'DailyNotes' ? '#9D00FF' : '#00F0FF';
                        ctx.beginPath();
                        ctx.arc(n.x, n.y, 6, 0, Math.PI * 2);
                        ctx.fill();

                        // Label
                        ctx.fillStyle = '#C9D1D9';
                        ctx.font = '10px monospace';
                        ctx.fillText(n.name, n.x + 9, n.y + 3);
                    }});

                    requestAnimationFrame(draw);
                }}
                draw();
            </script>
        </body>
        </html>
        """
        self.web_view.setHtml(html_content)
