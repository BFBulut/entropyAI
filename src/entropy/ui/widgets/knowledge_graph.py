"""Interactive Cognitive Memory & Knowledge Graph Viewer using QWebEngineView."""

import json
from pathlib import Path
from typing import Optional, Dict, List
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout
from PySide6.QtWebEngineWidgets import QWebEngineView

from entropy.memory.obsidian.vault_manager import ObsidianVaultManager
from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem
from entropy.ui.themes.cyber_theme import CYBER_THEME

class KnowledgeGraphWidget(QFrame):
    """Visualizes Cognitive Memory (Ego, Episodic, Semantic) and Obsidian Knowledge Graph."""

    def __init__(
        self,
        parent=None,
        vault_manager: Optional[ObsidianVaultManager] = None,
        cognitive_memory: Optional[CognitiveMemorySystem] = None
    ):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self.vault_manager = vault_manager or ObsidianVaultManager()
        self.cognitive_memory = cognitive_memory or CognitiveMemorySystem()

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(6)

        # Header bar
        header = QHBoxLayout()
        title_label = QLabel("<b style='color:#00F0FF; font-size:13px;'>🧠 BİLİŞSEL HAFIZA VE BİLGİ HARİTASI</b>")
        header.addWidget(title_label)

        header.addStretch()

        self.refresh_btn = QPushButton("Yenile")
        self.refresh_btn.setFixedHeight(22)
        self.refresh_btn.clicked.connect(self.refresh_graph)
        header.addWidget(self.refresh_btn)

        self.layout.addLayout(header)

        # WebEngine View
        self.web_view = QWebEngineView()
        self.web_view.setStyleSheet("background: #080B10; border-radius: 6px;")
        self.layout.addWidget(self.web_view)

        self.refresh_graph()

    def build_unified_graph(self) -> Dict[str, List[Dict[str, str]]]:
        """Aggregate Obsidian notes, cognitive memory nodes, and project context into a unified graph."""
        nodes = []
        links = []
        node_ids = set()

        # 1. Central Ego Node
        ego_id = "ego-entropy-core"
        node_ids.add(ego_id)
        nodes.append({
            "id": ego_id,
            "name": "Entropy AI Çekirdeği",
            "group": "ego",
            "info": "Otonom Ajan İşletim Sistemi Kimlik Düğümü",
            "val": 22
        })

        # 2. Cognitive Memory Nodes (from SQLite / pgvector)
        try:
            with self.cognitive_memory.db_path.open() as _:
                pass  # check existence
            import sqlite3
            with sqlite3.connect(self.cognitive_memory.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, category, content, importance FROM cognitive_nodes LIMIT 30")
                for row in cursor.fetchall():
                    c_id, cat, content, imp = row[0], row[1], row[2], row[3]
                    if c_id not in node_ids:
                        node_ids.add(c_id)
                        short_name = content[:28] + ("..." if len(content) > 28 else "")
                        nodes.append({
                            "id": c_id,
                            "name": short_name,
                            "group": cat,
                            "info": content,
                            "val": max(10, int(imp * 18))
                        })
                        # Link to Ego
                        links.append({"source": ego_id, "target": c_id})
        except Exception:
            pass

        # 3. Obsidian Vault Markdown Nodes
        obsidian_data = self.vault_manager.build_knowledge_graph()
        for o_node in obsidian_data["nodes"]:
            o_id = o_node["id"]
            if o_id not in node_ids:
                node_ids.add(o_id)
                nodes.append({
                    "id": o_id,
                    "name": o_node["name"],
                    "group": "obsidian",
                    "info": f"Obsidian Dosyası: {o_node['path']}",
                    "val": 14
                })
                links.append({"source": ego_id, "target": o_id})

        for link in obsidian_data["links"]:
            links.append(link)

        # 4. If fewer than 5 nodes, add representative memory nodes
        if len(nodes) < 5:
            default_nodes = [
                ("sem-01", "semantic", "Zero-API Antigravity CLI Politikası", "Harici API anahtarı olmadan yerel CLI üzerinden çalışma."),
                ("sem-02", "semantic", "Obsidian Exocortex Bellek Yapısı", "Yerel Markdown dosyalarında bilgi ağı saklama."),
                ("sem-03", "semantic", "Supabase pgvector Mem0 Entegrasyonu", "12 katmanlı unutma eğrisi ve semantik geri çağırma."),
                ("epi-01", "episodic", "Son Kodlama ve Test Seansı", "29 otomatik test başarıyla yürütüldü."),
            ]
            for n_id, grp, name, info in default_nodes:
                if n_id not in node_ids:
                    node_ids.add(n_id)
                    nodes.append({"id": n_id, "name": name, "group": grp, "info": info, "val": 14})
                    links.append({"source": ego_id, "target": n_id})

        return {"nodes": nodes, "links": links}

    def refresh_graph(self):
        """Re-generate unified graph JSON and inject into WebEngine canvas."""
        graph_data = self.build_unified_graph()
        nodes_json = json.dumps(graph_data["nodes"], ensure_ascii=False)
        links_json = json.dumps(graph_data["links"], ensure_ascii=False)

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                * {{ box-sizing: border-box; }}
                body {{
                    margin: 0;
                    padding: 0;
                    background: #080B10;
                    overflow: hidden;
                    color: #F0F6FC;
                    font-family: 'Segoe UI', Consolas, sans-serif;
                    user-select: none;
                }}
                #canvas {{
                    width: 100vw;
                    height: 100vh;
                    display: block;
                }}
                #legend {{
                    position: absolute;
                    top: 10px;
                    left: 10px;
                    font-size: 11px;
                    background: rgba(14, 20, 32, 0.85);
                    border: 1px solid #1F2B42;
                    border-radius: 6px;
                    padding: 6px 10px;
                    display: flex;
                    gap: 12px;
                    backdrop-filter: blur(4px);
                }}
                .legend-item {{ display: flex; items-center; gap: 5px; }}
                .dot {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; }}
                #infoBox {{
                    position: absolute;
                    bottom: 12px;
                    left: 12px;
                    right: 12px;
                    background: rgba(14, 20, 32, 0.9);
                    border: 1px solid #00F0FF;
                    border-radius: 6px;
                    padding: 8px 12px;
                    font-size: 12px;
                    color: #F0F6FC;
                    display: none;
                }}
            </style>
        </head>
        <body>
            <div id="legend">
                <div class="legend-item"><span class="dot" style="background:#00F0FF;"></span> Çekirdek</div>
                <div class="legend-item"><span class="dot" style="background:#00FF9D;"></span> Semantik Hafıza</div>
                <div class="legend-item"><span class="dot" style="background:#FFB300;"></span> Episodik Anı</div>
                <div class="legend-item"><span class="dot" style="background:#9D00FF;"></span> Obsidian Notu</div>
            </div>
            <div id="infoBox"></div>
            <canvas id="canvas"></canvas>

            <script>
                const nodes = {nodes_json};
                const links = {links_json};

                const canvas = document.getElementById('canvas');
                const ctx = canvas.getContext('2d');
                const infoBox = document.getElementById('infoBox');

                let width = 600;
                let height = 400;

                function updateDimensions() {{
                    width = canvas.width = Math.max(window.innerWidth, 300);
                    height = canvas.height = Math.max(window.innerHeight, 200);
                }}
                window.addEventListener('resize', updateDimensions);
                updateDimensions();

                const colors = {{
                    'ego': '#00F0FF',
                    'semantic': '#00FF9D',
                    'episodic': '#FFB300',
                    'obsidian': '#9D00FF',
                    'DailyNotes': '#9D00FF',
                    'Reports': '#38BDF8'
                }};

                // Initialize physics positions
                const centerX = width / 2;
                const centerY = height / 2;

                nodes.forEach((n, idx) => {{
                    if (n.group === 'ego') {{
                        n.x = centerX;
                        n.y = centerY;
                        n.vx = 0;
                        n.vy = 0;
                    }} else {{
                        const angle = (idx / Math.max(1, nodes.length - 1)) * Math.PI * 2;
                        const dist = 90 + (idx % 3) * 45;
                        n.x = centerX + Math.cos(angle) * dist;
                        n.y = centerY + Math.sin(angle) * dist;
                        n.vx = (Math.random() - 0.5) * 0.4;
                        n.vy = (Math.random() - 0.5) * 0.4;
                    }}
                }});

                let hoveredNode = null;
                let draggedNode = null;

                canvas.addEventListener('mousemove', (e) => {{
                    const rect = canvas.getBoundingClientRect();
                    const mx = e.clientX - rect.left;
                    const my = e.clientY - rect.top;

                    if (draggedNode) {{
                        draggedNode.x = mx;
                        draggedNode.y = my;
                        return;
                    }}

                    hoveredNode = null;
                    for (let n of nodes) {{
                        const r = n.val || 12;
                        const dx = mx - n.x;
                        const dy = my - n.y;
                        if (dx * dx + dy * dy < (r + 4) * (r + 4)) {{
                            hoveredNode = n;
                            break;
                        }}
                    }}

                    if (hoveredNode) {{
                        canvas.style.cursor = 'pointer';
                        infoBox.style.display = 'block';
                        infoBox.innerHTML = `<b>${{hoveredNode.name}}</b> [${{hoveredNode.group}}]<br/><span style="color:#8B949E;">${{hoveredNode.info || ''}}</span>`;
                    }} else {{
                        canvas.style.cursor = 'default';
                        infoBox.style.display = 'none';
                    }}
                }});

                canvas.addEventListener('mousedown', (e) => {{
                    if (hoveredNode) draggedNode = hoveredNode;
                }});

                window.addEventListener('mouseup', () => {{
                    draggedNode = null;
                }});

                function render() {{
                    ctx.fillStyle = '#080B10';
                    ctx.fillRect(0, 0, width, height);

                    // Physics update
                    nodes.forEach(n => {{
                        if (n !== draggedNode && n.group !== 'ego') {{
                            n.x += n.vx;
                            n.y += n.vy;

                            // Gentle centering gravity
                            n.vx += (width / 2 - n.x) * 0.0003;
                            n.vy += (height / 2 - n.y) * 0.0003;

                            // Bounce edges
                            if (n.x < 30 || n.x > width - 30) n.vx *= -0.9;
                            if (n.y < 40 || n.y > height - 40) n.vy *= -0.9;
                        }}
                    }});

                    // Draw Links
                    ctx.lineWidth = 1;
                    links.forEach(l => {{
                        const s = nodes.find(n => n.id === l.source);
                        const t = nodes.find(n => n.id === l.target || n.name === l.target || n.id.includes(l.target));
                        if (s && t) {{
                            const grad = ctx.createLinearGradient(s.x, s.y, t.x, t.y);
                            grad.setColorAt(0, 'rgba(0, 240, 255, 0.4)');
                            grad.setColorAt(1, 'rgba(157, 0, 255, 0.2)');
                            ctx.strokeStyle = grad;
                            ctx.beginPath();
                            ctx.moveTo(s.x, s.y);
                            ctx.lineTo(t.x, t.y);
                            ctx.stroke();
                        }}
                    }});

                    // Draw Nodes
                    nodes.forEach(n => {{
                        const color = colors[n.group] || '#00F0FF';
                        const r = (n.val || 12) * (n === hoveredNode ? 1.25 : 1.0);

                        // Outer Glow
                        const glow = ctx.createRadialGradient(n.x, n.y, r * 0.2, n.x, n.y, r * 2.2);
                        glow.setColorAt(0, color + '99');
                        glow.setColorAt(1, color + '00');
                        ctx.fillStyle = glow;
                        ctx.beginPath();
                        ctx.arc(n.x, n.y, r * 2.2, 0, Math.PI * 2);
                        ctx.fill();

                        // Inner Node
                        ctx.fillStyle = color;
                        ctx.beginPath();
                        ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
                        ctx.fill();

                        // White Core Center
                        ctx.fillStyle = '#FFFFFF';
                        ctx.beginPath();
                        ctx.arc(n.x, n.y, r * 0.35, 0, Math.PI * 2);
                        ctx.fill();

                        // Label
                        ctx.fillStyle = n === hoveredNode ? '#00F0FF' : '#C9D1D9';
                        ctx.font = (n.group === 'ego' ? 'bold 11px' : '10px') + ' monospace';
                        ctx.fillText(n.name, n.x + r + 6, n.y + 4);
                    }});

                    requestAnimationFrame(render);
                }}

                // Start after layout settles
                setTimeout(() => {{
                    updateDimensions();
                    render();
                }}, 60);
            </script>
        </body>
        </html>
        """
        self.web_view.setHtml(html_content)
