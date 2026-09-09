"""Faz 7 Desk ekran goruntuleri: 10 ajanli sahne, Bellek grafi, Projeler,
kart diyalogu ve 1920x1040'ta yarim ekran Desk + Zen yan yana.

Offscreen ekran boyutu degistirilemedigi icin pencereler setGeometry ile hedef
cozunurluge kurulur; yan yana kare iki pencerenin gorseli birlestirilerek
uretilir.
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from PySide6.QtCore import QRect  # noqa: E402
from PySide6.QtGui import QColor, QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

OUT = os.path.dirname(__file__)


class Spec(dict):
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc


def grab(widget, name):
    widget.show()
    QApplication.processEvents()
    pix = widget.grab()
    path = os.path.join(OUT, name)
    pix.save(path)
    print(name, pix.width(), "x", pix.height())
    return pix


def main():
    app = QApplication.instance() or QApplication(sys.argv)

    # --- 1) 10 ajanli sahne
    from entropy.desk.scene import OfficeScene

    members = [f"ajan-{i}" for i in range(1, 9)]
    office = Spec({
        "name": "arastirma", "orchestrator": "lider", "evaluator": "denetci",
        "members": ["lider"] + members + ["denetci"], "purpose": "10 ajanli ofis",
    })
    scene = OfficeScene()
    scene.set_office(office)
    scene.resize(1100, 640)
    scene.fit_to_view()
    print("koltuklar:", scene.seat_assignments())
    grab(scene, "scene_10_agents.png")

    # --- 2) Bellek mini grafi
    from entropy.desk.memory_panel import OfficeMemoryPanel

    data = {
        "nodes": [
            {"id": "ofis-x", "name": "arastirma", "kind": "ofis", "degree": 6, "note": ""},
            {"id": "karar-1", "name": "Kaynak secimi", "kind": "karar", "degree": 3,
             "note": "Birincil kaynak X secildi; Y ikincil."},
            {"id": "bulgu-1", "name": "Pazar buyuklugu", "kind": "bulgu", "degree": 2,
             "note": "2026 pazari 4.2 milyar USD."},
            {"id": "rapor-1", "name": "Faz raporu", "kind": "rapor", "degree": 2,
             "note": "reports/faz.md", "virtual": True},
            {"id": "ajan-1", "name": "arastirmaci", "kind": "ajan", "degree": 1,
             "note": "agents/arastirmaci", "virtual": True},
            {"id": "ajan-2", "name": "yazar", "kind": "ajan", "degree": 1,
             "note": "agents/yazar", "virtual": True},
        ],
        "links": [
            {"source": "karar-1", "target": "ofis-x", "type": "member_of"},
            {"source": "bulgu-1", "target": "karar-1", "type": "related"},
            {"source": "rapor-1", "target": "ofis-x", "type": "member_of"},
            {"source": "ajan-1", "target": "ofis-x", "type": "member_of"},
            {"source": "ajan-2", "target": "ofis-x", "type": "member_of"},
        ],
    }
    memory = OfficeMemoryPanel(office="")
    memory.canvas.set_data(data)
    memory.show_node("karar-1")
    memory.resize(900, 520)
    grab(memory, "memory_graph.png")

    # --- 3) Projeler sekmesi
    from entropy.desk.projects_panel import ProjectsPanel

    class FakeProject(dict):
        def __getattr__(self, item):
            return self[item]

    class FakeDesk:
        def __init__(self):
            self.projects = {"arastirma": [
                FakeProject({"name": "site", "office": "arastirma",
                             "goal": "Kurumsal site icerigi", "charter": ""}),
                FakeProject({"name": "rapor-2026", "office": "arastirma",
                             "goal": "Yillik pazar raporu", "charter": ""}),
            ]}

        def list_projects(self, office):
            return list(self.projects.get(office, []))

    class FakeBoard:
        def __init__(self, cards):
            self._cards = cards

        def list(self):
            return list(self._cards)

    cards = [
        Spec({"id": "c1", "office": "arastirma", "project": "site", "status": "running"}),
        Spec({"id": "c2", "office": "arastirma", "project": "site", "status": "done"}),
        Spec({"id": "c3", "office": "arastirma", "project": "rapor-2026", "status": "backlog"}),
    ]
    projects = ProjectsPanel(office="arastirma", desk=FakeDesk(), board=FakeBoard(cards))
    projects.list_widget.setCurrentRow(0)
    projects.resize(760, 360)
    grab(projects, "projects_tab.png")

    # --- 4) Gorev ver diyalogu (saglayici/model/efor/butce)
    from entropy.ui.widgets.agents_widget import AssignTaskDialog

    dialog = AssignTaskDialog(agent_name="arastirmaci", skills=["arastirma", "yazim"],
                              provider="claude", model="opus", effort="medium",
                              budget_tokens=12000)
    dialog.title_input.setText("Pazar raporu")
    dialog.goal_input.setPlainText("2026 pazarini kaynakli ozetle.")
    dialog.criteria_input.setPlainText("En az 5 kaynak\nTablo iceren ozet")
    dialog.resize(560, 620)
    grab(dialog, "assign_dialog.png")

    # --- 5) Yarim ekran Desk + Zen yan yana (1920x1040)
    from entropy.core.provider import create_bridge
    from entropy.desk.window import AgentDeskWindow
    from entropy.ui.modes.zen_mode import ZenModeWindow
    from entropy.ui.window_sizing import half_screen_geometry

    area = QRect(0, 0, 1920, 1040)
    desk_geom = half_screen_geometry(area, width_ratio=0.5, height_ratio=0.9, side="right")
    zen_geom = half_screen_geometry(area, width_ratio=0.5, height_ratio=0.9, side="left")

    desk = AgentDeskWindow()
    desk.setGeometry(desk_geom)
    zen = ZenModeWindow(bridge=create_bridge())
    zen.setGeometry(zen_geom)
    desk.show()
    zen.show()
    QApplication.processEvents()

    canvas = QPixmap(1920, 1040)
    canvas.fill(QColor("#05070A"))
    painter = QPainter(canvas)
    painter.drawPixmap(zen_geom.x(), zen_geom.y(), zen.grab())
    painter.drawPixmap(desk_geom.x(), desk_geom.y(), desk.grab())
    painter.end()
    canvas.save(os.path.join(OUT, "desk_zen_side_by_side_1920x1040.png"))
    print("yan yana:", zen_geom, desk_geom, "kesisim:",
          zen_geom.intersects(desk_geom))
    desk.close()
    zen.close()


if __name__ == "__main__":
    main()
