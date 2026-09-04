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
            background: rgba(14, 20, 32, 0.92);
            border: 1px solid #1F2B42;
            border-radius: 6px;
            padding: 5px 10px;
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            backdrop-filter: blur(6px);
            z-index: 10;
            max-width: calc(100vw - 20px);
        }
        .legend-item {
            display: flex;
            align-items: center;
            gap: 5px;
            cursor: pointer;
            padding: 2px 5px;
            border-radius: 4px;
            transition: all 0.15s ease;
        }
        .legend-item:hover {
            background: rgba(0, 240, 255, 0.12);
        }
        .legend-item.dimmed {
            opacity: 0.30;
            text-decoration: line-through;
        }
        .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
        #controls {
            position: absolute;
            bottom: 12px;
            right: 12px;
            display: flex;
            gap: 6px;
            z-index: 10;
        }
        .ctrl-btn {
            background: rgba(14, 20, 32, 0.92);
            border: 1px solid #1F2B42;
            border-radius: 4px;
            color: #00F0FF;
            font-weight: bold;
            font-size: 13px;
            width: 28px;
            height: 28px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.15s ease;
            backdrop-filter: blur(4px);
        }
        .ctrl-btn:hover {
            background: #00F0FF;
            color: #080B10;
            border-color: #00F0FF;
        }
        #infoBox {
            position: absolute;
            bottom: 12px;
            left: 12px;
            right: 120px;
            background: rgba(14, 20, 32, 0.95);
            border: 1px solid #00F0FF;
            border-radius: 6px;
            padding: 8px 12px;
            font-size: 12px;
            color: #F0F6FC;
            display: none;
            z-index: 10;
            backdrop-filter: blur(6px);
        }
    </style>
</head>
<body>
    <div id="legend">
        <div class="legend-item" onclick="toggleCategory('ego', this)" title="Filtrele"><span class="dot" style="background:#00F0FF;"></span> Çekirdek</div>
        <div class="legend-item" onclick="toggleCategory('semantic', this)" title="Filtrele"><span class="dot" style="background:#00FF9D;"></span> Semantik Hafıza</div>
        <div class="legend-item" onclick="toggleCategory('episodic', this)" title="Filtrele"><span class="dot" style="background:#FFB300;"></span> Episodik Anı</div>
        <div class="legend-item" onclick="toggleCategory('obsidian', this)" title="Filtrele"><span class="dot" style="background:#9D00FF;"></span> Obsidian Notu / Rapor</div>
    </div>
    <div id="controls">
        <button class="ctrl-btn" onclick="zoomIn()" title="Yakınlaştır">+</button>
        <button class="ctrl-btn" onclick="zoomOut()" title="Uzaklaştır">-</button>
        <button class="ctrl-btn" onclick="resetZoom()" title="Görünümü Sıfırla">⟲</button>
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

        // Zoom & Pan state
        let zoom = 1.0;
        let panX = 0;
        let panY = 0;
        let isPanning = false;
        let panStartX = 0;
        let panStartY = 0;

        const activeCategories = {
            'ego': true,
            'semantic': true,
            'episodic': true,
            'obsidian': true,
            'Entropy': true,
            'DailyNotes': true,
            'Reports': true
        };

        function toggleCategory(cat, el) {
            const newState = !activeCategories[cat];
            activeCategories[cat] = newState;
            if (cat === 'obsidian') {
                activeCategories['Reports'] = newState;
                activeCategories['DailyNotes'] = newState;
            }
            el.classList.toggle('dimmed', !newState);
            alpha = 0.5;
        }

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

        function initNodePositions() {
            const cx = width / 2;
            const cy = height / 2;

            nodes.forEach((n, idx) => {
                if (n.group === 'ego') {
                    n.x = cx;
                    n.y = cy;
                } else {
                    const angle = (idx / Math.max(1, nodes.length - 1)) * Math.PI * 2;
                    const dist = 140 + (idx % 5) * 50;
                    n.x = cx + Math.cos(angle) * dist;
                    n.y = cy + Math.sin(angle) * dist;
                }
            });
        }
        initNodePositions();

        let alpha = 1.0;
        const alphaMin = 0.003;
        const alphaDecay = 0.020;

        function tickPhysics() {
            if (alpha < alphaMin && !draggedNode) {
                return;
            }

            const cx = width / 2;
            const cy = height / 2;

            // 1. Collision Prevention & Strong Repulsion
            for (let i = 0; i < nodes.length; i++) {
                const a = nodes[i];
                if (activeCategories[a.group] === false) continue;

                for (let j = i + 1; j < nodes.length; j++) {
                    const b = nodes[j];
                    if (activeCategories[b.group] === false) continue;

                    const dx = b.x - a.x;
                    const dy = b.y - a.y;
                    const dist = Math.sqrt(dx * dx + dy * dy) || 1;

                    // Hard collision buffer
                    const rA = a.val || 12;
                    const rB = b.val || 12;
                    const minDist = rA + rB + 48; // Generous safety buffer to prevent any overlap

                    if (dist < minDist) {
                        const overlap = (minDist - dist) / dist;
                        const pushX = dx * overlap * 0.6;
                        const pushY = dy * overlap * 0.6;
                        if (a.group !== 'ego' && a !== draggedNode) { a.x -= pushX; a.y -= pushY; }
                        if (b.group !== 'ego' && b !== draggedNode) { b.x += pushX; b.y += pushY; }
                    } else if (dist < 260) {
                        // Ambient celestial repulsion
                        const force = ((260 - dist) / 260) * 3.5 * alpha;
                        const fx = (dx / dist) * force;
                        const fy = (dy / dist) * force;
                        if (a.group !== 'ego' && a !== draggedNode) { a.x -= fx; a.y -= fy; }
                        if (b.group !== 'ego' && b !== draggedNode) { b.x += fx; b.y += fy; }
                    }
                }
            }

            // 2. Spring link tension
            links.forEach(l => {
                const s = nodes.find(n => n.id === l.source);
                const t = nodes.find(n => n.id === l.target || n.name === l.target);
                if (s && t && activeCategories[s.group] !== false && activeCategories[t.group] !== false) {
                    const dx = t.x - s.x;
                    const dy = t.y - s.y;
                    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                    const targetLen = 135;
                    const force = (dist - targetLen) * 0.028 * alpha;
                    if (t.group !== 'ego' && t !== draggedNode) {
                        t.x -= (dx / dist) * force;
                        t.y -= (dy / dist) * force;
                    }
                }
            });

            // 3. Gentle center gravity (loose celestial pull)
            nodes.forEach(n => {
                if (n.group !== 'ego' && n !== draggedNode && activeCategories[n.group] !== false) {
                    n.x += (cx - n.x) * 0.005 * alpha;
                    n.y += (cy - n.y) * 0.005 * alpha;
                }
            });

            alpha *= (1 - alphaDecay);
        }

        let hoveredNode = null;
        let draggedNode = null;
        let isDragging = false;
        let startX = 0, startY = 0;

        // Smooth mouse wheel zoom
        canvas.addEventListener('wheel', (e) => {
            e.preventDefault();
            const rect = canvas.getBoundingClientRect();
            const mx = e.clientX - rect.left;
            const my = e.clientY - rect.top;

            const zoomFactor = e.deltaY < 0 ? 1.15 : 0.87;
            const newZoom = Math.max(0.30, Math.min(4.0, zoom * zoomFactor));

            panX = mx - (mx - panX) * (newZoom / zoom);
            panY = my - (my - panY) * (newZoom / zoom);
            zoom = newZoom;
        }, { passive: false });

        canvas.addEventListener('mousedown', (e) => {
            const rect = canvas.getBoundingClientRect();
            const mx = e.clientX - rect.left;
            const my = e.clientY - rect.top;

            if (hoveredNode) {
                draggedNode = hoveredNode;
                startX = mx;
                startY = my;
                isDragging = false;
                alpha = 0.4;
            } else {
                isPanning = true;
                panStartX = e.clientX - panX;
                panStartY = e.clientY - panY;
            }
        });

        canvas.addEventListener('mousemove', (e) => {
            const rect = canvas.getBoundingClientRect();
            const mx = e.clientX - rect.left;
            const my = e.clientY - rect.top;

            if (isPanning) {
                panX = e.clientX - panStartX;
                panY = e.clientY - panStartY;
                return;
            }

            if (draggedNode) {
                isDragging = true;
                const wx = (mx - panX) / zoom;
                const wy = (my - panY) / zoom;
                draggedNode.x = wx;
                draggedNode.y = wy;
                alpha = 0.3;
                return;
            }

            // Hit test in world coords
            const wx = (mx - panX) / zoom;
            const wy = (my - panY) / zoom;
            hoveredNode = null;

            for (let i = nodes.length - 1; i >= 0; i--) {
                const n = nodes[i];
                if (activeCategories[n.group] === false) continue;
                const r = n.val || 12;
                const dx = n.x - wx;
                const dy = n.y - wy;
                if (dx * dx + dy * dy < (r + 10) * (r + 10)) {
                    hoveredNode = n;
                    break;
                }
            }

            if (hoveredNode) {
                canvas.style.cursor = 'pointer';
                infoBox.style.display = 'block';
                infoBox.innerHTML = `<b>${hoveredNode.name}</b> [${hoveredNode.group}] <span style="color:#00FF9D; font-size:11px;">(Detayları ve İlişkileri Açmak İçin Tıkla)</span><br/><span style="color:#8B949E;">${hoveredNode.info || ''}</span>`;
            } else {
                canvas.style.cursor = isPanning ? 'grabbing' : 'default';
                infoBox.style.display = 'none';
            }
        });

        canvas.addEventListener('mouseup', () => {
            draggedNode = null;
            isPanning = false;
        });

        canvas.addEventListener('dblclick', () => {
            resetZoom();
        });

        canvas.addEventListener('click', (e) => {
            if (hoveredNode && !isDragging) {
                window.location.href = "entropy-node://" + encodeURIComponent(hoveredNode.id);
            }
        });

        function zoomIn() {
            const cx = width / 2;
            const cy = height / 2;
            const newZoom = Math.min(4.0, zoom * 1.25);
            panX = cx - (cx - panX) * (newZoom / zoom);
            panY = cy - (cy - panY) * (newZoom / zoom);
            zoom = newZoom;
        }

        function zoomOut() {
            const cx = width / 2;
            const cy = height / 2;
            const newZoom = Math.max(0.30, zoom * 0.8);
            panX = cx - (cx - panX) * (newZoom / zoom);
            panY = cy - (cy - panY) * (newZoom / zoom);
            zoom = newZoom;
        }

        function resetZoom() {
            zoom = 1.0;
            panX = 0;
            panY = 0;
            alpha = 0.6;
        }

        function render() {
            try {
                tickPhysics();

                ctx.fillStyle = '#080B10';
                ctx.fillRect(0, 0, width, height);

                ctx.save();
                ctx.translate(panX, panY);
                ctx.scale(zoom, zoom);

                // 1. Draw Links
                ctx.lineWidth = 1;
                links.forEach(l => {
                    const s = nodes.find(n => n.id === l.source);
                    const t = nodes.find(n => n.id === l.target || n.name === l.target || (typeof l.target === 'string' && l.target && n.id.includes(l.target)));
                    if (s && t && activeCategories[s.group] !== false && activeCategories[t.group] !== false) {
                        try {
                            const grad = ctx.createLinearGradient(s.x, s.y, t.x, t.y);
                            grad.addColorStop(0, 'rgba(0, 240, 255, 0.40)');
                            grad.addColorStop(1, 'rgba(157, 0, 255, 0.20)');
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

                // 2. Draw Nodes and Anti-Collision Pill Labels
                nodes.forEach(n => {
                    if (activeCategories[n.group] === false) return;

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

                    // Inner Solid Circle
                    ctx.fillStyle = color;
                    ctx.beginPath();
                    ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
                    ctx.fill();

                    // White Core Pulse Center
                    ctx.fillStyle = '#FFFFFF';
                    ctx.beginPath();
                    ctx.arc(n.x, n.y, r * 0.35, 0, Math.PI * 2);
                    ctx.fill();

                    // Clean Pill Label Rendering
                    let labelText = n.name || '';
                    const isHovered = (n === hoveredNode);
                    if (!isHovered && labelText.length > 18) {
                        labelText = labelText.substring(0, 16) + '..';
                    }

                    ctx.font = (n.group === 'ego' ? 'bold 11px' : '10px') + ' "Segoe UI", Consolas, monospace';
                    const textWidth = ctx.measureText(labelText).width;
                    const pillX = n.x + r + 6;
                    const pillY = n.y - 9;
                    const pillW = textWidth + 10;
                    const pillH = 18;

                    // Translucent dark pill backing to prevent text overlap and line collision
                    ctx.fillStyle = isHovered ? 'rgba(0, 240, 255, 0.22)' : 'rgba(8, 11, 16, 0.88)';
                    ctx.strokeStyle = isHovered ? '#00F0FF' : 'rgba(31, 43, 66, 0.85)';
                    ctx.lineWidth = 1;
                    ctx.beginPath();
                    if (ctx.roundRect) {
                        ctx.roundRect(pillX, pillY, pillW, pillH, 4);
                    } else {
                        ctx.rect(pillX, pillY, pillW, pillH);
                    }
                    ctx.fill();
                    ctx.stroke();

                    // Text inside pill
                    ctx.fillStyle = isHovered ? '#00F0FF' : '#E6EDF3';
                    ctx.fillText(labelText, pillX + 5, pillY + 13);
                });

                ctx.restore();
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

        # Auto-refresh on new reports, turns, cognitive memory, or explicit graph updates
        bus.report_created.connect(lambda _: self.refresh_graph())
        bus.agent_turn_completed.connect(lambda _: self.refresh_graph())
        bus.knowledge_graph_updated.connect(self.refresh_graph)
        bus.cognitive_memory_updated.connect(self.refresh_graph)

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

        # 2. Cognitive Memory Nodes (from SQLite / pgvector) - Ordered by recency
        try:
            import sqlite3
            if self.cognitive_memory.db_path.exists():
                with sqlite3.connect(self.cognitive_memory.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT id, category, content, importance FROM cognitive_nodes ORDER BY created_at DESC LIMIT 60")
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
