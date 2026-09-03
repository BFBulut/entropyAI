"""Interactive Cognitive Memory & Knowledge Graph Viewer using QWebEngineView with alpha-cooled physics."""

import json
from pathlib import Path
from typing import Optional, Dict, List
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage

from entropy.core.event_bus import bus
from entropy.memory.obsidian.vault_manager import ObsidianVaultManager
from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem
from entropy.ui.themes.cyber_theme import CYBER_THEME

GRAPH_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        * { box-sizing: border-box; }
        body {
            margin: 0;
            padding: 0;
            background: #080B10;
            overflow: hidden;
            color: #F0F6FC;
            font-family: 'Segoe UI', Consolas, sans-serif;
            user-select: none;
            width: 100vw;
            height: 100vh;
        }
        #canvas {
            display: block;
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
        }
        #legend {
            position: absolute;
            top: 10px;
            left: 10px;
            font-size: 11px;
            background: rgba(14, 20, 32, 0.88);
            border: 1px solid #1F2B42;
            border-radius: 6px;
            padding: 6px 10px;
            display: flex;
            gap: 12px;
            backdrop-filter: blur(4px);
            z-index: 10;
        }
        .legend-item { display: flex; align-items: center; gap: 5px; }
        .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
        #infoBox {
            position: absolute;
            bottom: 12px;
            left: 12px;
            right: 12px;
            background: rgba(14, 20, 32, 0.95);
            border: 1px solid #00F0FF;
            border-radius: 6px;
            padding: 8px 12px;
            font-size: 12px;
            color: #F0F6FC;
            display: none;
            z-index: 10;
        }
    </style>
</head>
<body>
    <div id="legend">
        <div class="legend-item"><span class="dot" style="background:#00F0FF;"></span> Çekirdek</div>
        <div class="legend-item"><span class="dot" style="background:#00FF9D;"></span> Semantik Hafıza</div>
        <div class="legend-item"><span class="dot" style="background:#FFB300;"></span> Episodik Anı</div>
        <div class="legend-item"><span class="dot" style="background:#9D00FF;"></span> Obsidian Notu / Rapor</div>
    </div>
    <div id="infoBox"></div>
    <canvas id="canvas"></canvas>

    <script>
        window.onerror = function(msg, url, line) {
            console.error("Canvas Graph Error: " + msg + " line " + line);
            const box = document.getElementById('infoBox');
            if (box) {
                box.style.display = 'block';
                box.style.borderColor = '#FF4D4D';
                box.innerHTML = "Hafıza Haritası Hatası: " + msg;
            }
        };

        const nodes = __NODES__;
        const links = __LINKS__;

        const canvas = document.getElementById('canvas');
        const ctx = canvas.getContext('2d');
        const infoBox = document.getElementById('infoBox');

        let width = 600;
        let height = 400;

        function updateDimensions() {
            width = canvas.width = Math.max(window.innerWidth || 0, document.documentElement.clientWidth || 0, 300);
            height = canvas.height = Math.max(window.innerHeight || 0, document.documentElement.clientHeight || 0, 250);
        }
        window.addEventListener('resize', updateDimensions);
        updateDimensions();

        const colors = {
            'ego': '#00F0FF',
            'semantic': '#00FF9D',
            'episodic': '#FFB300',
            'obsidian': '#9D00FF',
            'Entropy': '#9D00FF',
            'DailyNotes': '#9D00FF',
            'Reports': '#FF0055'
        };

        // Initialize positions distributed evenly in an orbital circle
        function initNodePositions() {
            const cx = width / 2;
            const cy = height / 2;

            nodes.forEach((n, idx) => {
                if (n.group === 'ego') {
                    n.x = cx;
                    n.y = cy;
                } else {
                    const angle = (idx / Math.max(1, nodes.length - 1)) * Math.PI * 2;
                    const dist = 75 + (idx % 3) * 35;
                    n.x = cx + Math.cos(angle) * dist;
                    n.y = cy + Math.sin(angle) * dist;
                }
            });
        }
        initNodePositions();

        // Alpha decay simulation (Cools down in ~2 seconds to become 100% static)
        let alpha = 1.0;
        const alphaMin = 0.003;
        const alphaDecay = 0.025;

        function tickPhysics() {
            if (alpha < alphaMin && !draggedNode) {
                return; // Completely frozen in place, 0 vibration!
            }

            const cx = width / 2;
            const cy = height / 2;

            // Repulsion force between pairs
            for (let i = 0; i < nodes.length; i++) {
                for (let j = i + 1; j < nodes.length; j++) {
                    const a = nodes[i];
                    const b = nodes[j];
                    const dx = b.x - a.x;
                    const dy = b.y - a.y;
                    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                    if (dist < 130) {
                        const force = ((130 - dist) / 130) * 2.0 * alpha;
                        const fx = (dx / dist) * force;
                        const fy = (dy / dist) * force;
                        if (a.group !== 'ego' && a !== draggedNode) { a.x -= fx; a.y -= fy; }
                        if (b.group !== 'ego' && b !== draggedNode) { b.x += fx; b.y += fy; }
                    }
                }
            }

            // Spring link tension
            links.forEach(l => {
                const s = nodes.find(n => n.id === l.source);
                const t = nodes.find(n => n.id === l.target || n.name === l.target);
                if (s && t) {
                    const dx = t.x - s.x;
                    const dy = t.y - s.y;
                    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                    const force = (dist - 85) * 0.04 * alpha;
                    if (t.group !== 'ego' && t !== draggedNode) {
                        t.x -= (dx / dist) * force;
                        t.y -= (dy / dist) * force;
                    }
                }
            });

            // Center gravity
            nodes.forEach(n => {
                if (n.group !== 'ego' && n !== draggedNode) {
                    n.x += (cx - n.x) * 0.02 * alpha;
                    n.y += (cy - n.y) * 0.02 * alpha;

                    // Bounds clamp
                    if (n.x < 40) n.x = 40;
                    if (n.x > width - 40) n.x = width - 40;
                    if (n.y < 50) n.y = 50;
                    if (n.y > height - 45) n.y = height - 45;
                }
            });

            alpha *= (1 - alphaDecay);
        }

        let hoveredNode = null;
        let draggedNode = null;
        let isDragging = false;
        let startX = 0, startY = 0;

        canvas.addEventListener('mousedown', (e) => {
            if (hoveredNode) {
                draggedNode = hoveredNode;
                startX = e.clientX;
                startY = e.clientY;
                isDragging = false;
                alpha = 0.3;
            }
        });

        canvas.addEventListener('mousemove', (e) => {
            const rect = canvas.getBoundingClientRect();
            const mx = e.clientX - rect.left;
            const my = e.clientY - rect.top;

            if (draggedNode) {
                if (Math.hypot(e.clientX - startX, e.clientY - startY) > 5) {
                    isDragging = true;
                }
                draggedNode.x = mx;
                draggedNode.y = my;
                return;
            }

            hoveredNode = null;
            for (let n of nodes) {
                const r = n.val || 14;
                const dx = mx - n.x;
                const dy = my - n.y;
                if (dx * dx + dy * dy < (r + 6) * (r + 6)) {
                    hoveredNode = n;
                    break;
                }
            }

            if (hoveredNode) {
                canvas.style.cursor = 'pointer';
                infoBox.style.display = 'block';
                infoBox.innerHTML = `<b>${hoveredNode.name}</b> [${hoveredNode.group}] <span style="color:#00FF9D; font-size:11px;">(Görüntülemek için tıkla)</span><br/><span style="color:#8B949E;">${hoveredNode.info || ''}</span>`;
            } else {
                canvas.style.cursor = 'default';
                infoBox.style.display = 'none';
            }
        });

        canvas.addEventListener('mouseup', () => {
            draggedNode = null;
        });

        canvas.addEventListener('click', (e) => {
            if (hoveredNode && !isDragging) {
                window.location.href = "entropy-node://" + encodeURIComponent(hoveredNode.id);
            }
        });

        function render() {
            try {
                tickPhysics();

                ctx.fillStyle = '#080B10';
                ctx.fillRect(0, 0, width, height);

                // Draw Links
                ctx.lineWidth = 1;
                links.forEach(l => {
                    const s = nodes.find(n => n.id === l.source);
                    const t = nodes.find(n => n.id === l.target || n.name === l.target || (typeof l.target === 'string' && l.target && n.id.includes(l.target)));
                    if (s && t) {
                        try {
                            const grad = ctx.createLinearGradient(s.x, s.y, t.x, t.y);
                            grad.addColorStop(0, 'rgba(0, 240, 255, 0.45)');
                            grad.addColorStop(1, 'rgba(157, 0, 255, 0.25)');
                            ctx.strokeStyle = grad;
                        } catch (e) {
                            ctx.strokeStyle = 'rgba(0, 240, 255, 0.3)';
                        }
                        ctx.beginPath();
                        ctx.moveTo(s.x, s.y);
                        ctx.lineTo(t.x, t.y);
                        ctx.stroke();
                    }
                });

                // Draw Nodes
                nodes.forEach(n => {
                    const color = colors[n.group] || '#00F0FF';
                    const r = (n.val || 12) * (n === hoveredNode ? 1.25 : 1.0);

                    // Outer Glow
                    try {
                        const glow = ctx.createRadialGradient(n.x, n.y, r * 0.2, n.x, n.y, r * 2.2);
                        glow.addColorStop(0, color + '99');
                        glow.addColorStop(1, color + '00');
                        ctx.fillStyle = glow;
                    } catch (e) {
                        ctx.fillStyle = color;
                    }
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
                    ctx.fillStyle = n === hoveredNode ? '#00F0FF' : '#E6EDF3';
                    ctx.font = (n.group === 'ego' ? 'bold 11px' : '10px') + ' monospace';
                    ctx.fillText(n.name, n.x + r + 6, n.y + 4);
                });
            } catch (err) {
                console.error("Render loop error: " + err);
            }

            requestAnimationFrame(render);
        }

        setTimeout(() => {
            updateDimensions();
            initNodePositions();
            alpha = 1.0;
            render();
        }, 80);
    </script>
</body>
</html>
"""

class GraphWebEnginePage(QWebEnginePage):
    """Custom WebEnginePage intercepting entropy-node:// clicks."""

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        if url.scheme() == "entropy-node":
            node_id = url.host()
            if not node_id:
                node_id = url.path().lstrip("/")
            bus.node_selected.emit(node_id)
            return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)

class KnowledgeGraphWidget(QFrame):
    """Interactive Node-Link Knowledge Graph Viewer displaying Obsidian notes & cognitive nodes."""

    def __init__(self, parent=None, vault_manager: Optional[ObsidianVaultManager] = None):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self.vault_manager = vault_manager or ObsidianVaultManager()
        self.cognitive_memory = CognitiveMemorySystem()

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(6)

        # Header with Title and Legend
        header = QHBoxLayout()
        title_label = QLabel("<b style='color:#00F0FF; font-size:13px;'>🌐 BİLİŞSEL HAFIZA VE BİLGİ HARİTASI</b>")
        header.addWidget(title_label)
        header.addStretch()

        self.refresh_btn = QPushButton("Yenile")
        self.refresh_btn.setFixedHeight(24)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #141C2C;
                color: #00F0FF;
                border: 1px solid #00F0FF;
                border-radius: 4px;
                padding: 2px 14px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00F0FF;
                color: #080B10;
            }
        """)
        self.refresh_btn.clicked.connect(self.refresh_graph)
        header.addWidget(self.refresh_btn)

        self.layout.addLayout(header)

        # WebEngine View with custom Navigation Page
        self.web_view = QWebEngineView()
        self.web_page = GraphWebEnginePage(self.web_view)
        self.web_view.setPage(self.web_page)
        self.web_view.setStyleSheet("background: #080B10; border-radius: 6px;")
        self.layout.addWidget(self.web_view)

        # Auto-refresh on new reports or turns
        bus.report_created.connect(lambda _: self.refresh_graph())
        bus.agent_turn_completed.connect(lambda _: self.refresh_graph())

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
            import sqlite3
            if self.cognitive_memory.db_path.exists():
                with sqlite3.connect(self.cognitive_memory.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT id, category, content, importance FROM cognitive_nodes LIMIT 30")
                    for row in cursor.fetchall():
                        c_id, cat, content, imp = row[0], row[1], row[2], row[3]
                        if c_id not in node_ids:
                            node_ids.add(c_id)
                            short_name = content[:26] + ("..." if len(content) > 26 else "")
                            nodes.append({
                                "id": c_id,
                                "name": short_name,
                                "group": cat,
                                "info": content,
                                "val": max(12, int(imp * 18))
                            })
                            links.append({"source": ego_id, "target": c_id})
        except Exception:
            pass

        # 3. Obsidian Vault Markdown Nodes & Reports
        obsidian_data = self.vault_manager.build_knowledge_graph()
        for o_node in obsidian_data["nodes"]:
            o_id = o_node["id"]
            if o_id not in node_ids:
                node_ids.add(o_id)
                nodes.append({
                    "id": o_id,
                    "name": o_node["name"],
                    "group": o_node.get("group", "obsidian"),
                    "info": f"Obsidian Dosyası: {o_node['path']}",
                    "val": 14
                })
                links.append({"source": ego_id, "target": o_id})

        for link in obsidian_data["links"]:
            links.append(link)

        # 4. If fewer than 5 nodes, provide foundational semantic/episodic memory nodes
        if len(nodes) < 5:
            default_nodes = [
                ("sem-01", "semantic", "Zero-API Antigravity CLI Politikası", "Harici API anahtarı olmadan yerel CLI üzerinden çalışma."),
                ("sem-02", "semantic", "Obsidian Exocortex Bellek Yapısı", "Yerel Markdown dosyalarında bilgi ağı saklama."),
                ("sem-03", "semantic", "Supabase pgvector Mem0 Entegrasyonu", "12 katmanlı unutma eğrisi ve semantik geri çağırma."),
                ("epi-01", "episodic", "Son Kodlama ve Test Seansı", "Otomatik testler başarıyla yürütüldü."),
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

        html_content = GRAPH_HTML_TEMPLATE.replace("__NODES__", nodes_json).replace("__LINKS__", links_json)
        self.web_view.setHtml(html_content)
