"""
Automated Test Suite: Entropy Agent Desk Pixel Canvas & UI Components.
Headless Offscreen Verification: 100% Pass Rate Required.
"""

import pytest
from PySide6.QtCore import Qt, QPoint, QPointF, QEvent
from PySide6.QtGui import QMouseEvent, QPaintEvent, QImage, QPainter
from PySide6.QtWidgets import QApplication
from src.entropy.agent_desk.core.models import (
    AgentPersona,
    AgentActivityState,
    DeskRole,
    OfficeConfig,
)
from src.entropy.agent_desk.core.office_orchestrator import OfficeOrchestrator
from src.entropy.agent_desk.core.office_manager import OfficeManager
from src.entropy.agent_desk.ui.pixel_canvas import PixelCanvas
from src.entropy.agent_desk.ui.agent_terminal_pane import AgentTerminalPane
from src.entropy.agent_desk.ui.office_detail_widget import OfficeDetailWidget
from src.entropy.agent_desk.ui.offices_overview_widget import OfficesOverviewWidget
from src.entropy.agent_desk.ui.agent_desk_window import AgentDeskWindow


def test_pixel_canvas_rendering_and_interaction(qapp):
    canvas = PixelCanvas()
    canvas.resize(800, 500)

    orch = AgentPersona(
        agent_id="orch_p1",
        name="Lead Architect",
        office_id="off_ui",
        role=DeskRole.ORCHESTRATOR,
        model="claude-sonnet-4-6",
        desk_index=0,
    )
    sub1 = AgentPersona(
        agent_id="sub_p1",
        name="Dev Bot",
        office_id="off_ui",
        role=DeskRole.DEVELOPER,
        model="gemini-3.8-flash-high",
        desk_index=1,
    )

    canvas.set_personas(orch, [sub1])
    assert canvas.desks[0].persona.name == "Lead Architect"
    assert canvas.desks[1].persona.name == "Dev Bot"

    # Aktivite güncelleme
    canvas.update_agent_activity("sub_p1", AgentActivityState.TYPING)
    assert canvas.desks[1].persona.activity_state == AgentActivityState.TYPING

    # Tıklama etkileşimi ve sinyal yayımı
    emitted_agents = []
    canvas.agent_selected.connect(lambda aid: emitted_agents.append(aid))

    # Desk 0 konumuna tıklama simülasyonu (x=270, y=30, w=160, h=130)
    pos_f = QPointF(300.0, 50.0)
    mouse_event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        pos_f,
        pos_f,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    canvas.mousePressEvent(mouse_event)
    assert "orch_p1" in emitted_agents

    # Çizim tetikleme (Headless crash kontrolü)
    canvas.repaint()


def test_pixel_canvas_all_activity_states_and_animation_frames(qapp):
    canvas = PixelCanvas()
    canvas.resize(900, 600)

    orch = AgentPersona(
        agent_id="orch_0",
        name="Lead Orchestrator",
        office_id="off_test",
        role=DeskRole.ORCHESTRATOR,
        model="claude-sonnet-4-6",
        desk_index=0,
    )
    sub1 = AgentPersona(
        agent_id="sub_dev",
        name="Developer Specialist",
        office_id="off_test",
        role=DeskRole.DEVELOPER,
        model="gemini-3.8-flash-high",
        desk_index=1,
    )
    sub2 = AgentPersona(
        agent_id="sub_thinker",
        name="Deep Thinker",
        office_id="off_test",
        role=DeskRole.RESEARCHER,
        model="gemini-2.5-pro",
        desk_index=2,
    )

    canvas.set_personas(orch, [sub1, sub2])

    # Test all activity states across different animation frames
    states = [
        AgentActivityState.TYPING,
        AgentActivityState.THINKING,
        AgentActivityState.READING,
        AgentActivityState.TESTING,
        AgentActivityState.ERROR,
        AgentActivityState.IDLE,
    ]

    for state in states:
        canvas.update_agent_activity("orch_0", state)
        canvas.update_agent_activity("sub_dev", state)
        canvas.update_agent_activity("sub_thinker", state)

        # Pulse frame cycles across odd/even frames to test keystroke alternations,
        # bobbing wave offsets, wave dots, sparkle twinkles, and scanline shaders
        for frame in range(12):
            canvas._pulse_frame = frame
            canvas.repaint()

    # Verify pulse frame property and tick progression
    assert canvas.pulse_frame >= 0
    prev_frame = canvas.pulse_frame
    canvas._on_tick()
    assert canvas.pulse_frame == (prev_frame + 1) % 60


def test_pixel_canvas_qpainter_offscreen_image_render(qapp):
    canvas = PixelCanvas()
    canvas.resize(800, 500)

    orch = AgentPersona(
        agent_id="orch_render",
        name="Master Architect",
        office_id="off_render",
        role=DeskRole.ORCHESTRATOR,
        model="claude-sonnet-4-6",
        desk_index=0,
        activity_state=AgentActivityState.THINKING,
    )
    sub1 = AgentPersona(
        agent_id="sub_render",
        name="Typing Specialist",
        office_id="off_render",
        role=DeskRole.DEVELOPER,
        model="gemini-3.8-flash-high",
        desk_index=1,
        activity_state=AgentActivityState.TYPING,
    )
    canvas.set_personas(orch, [sub1])

    # Direct offscreen rendering into QImage
    img = QImage(800, 500, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.black)

    canvas.render(img)

    # Image should not be null and should have dimensions
    assert not img.isNull()
    assert img.width() == 800
    assert img.height() == 500


def test_pixel_canvas_typing_animation_keystrokes_and_sparks(qapp):
    """Masa başında yazma animasyonu: Tuş vuruşları, eller, klavye aydınlatması ve sözdizimi kıvılcımları."""
    canvas = PixelCanvas()
    canvas.resize(800, 500)

    dev = AgentPersona(
        agent_id="dev_typing",
        name="Typing Pro",
        office_id="off_typing",
        role=DeskRole.DEVELOPER,
        model="gemini-3.8-flash-high",
        desk_index=1,
        activity_state=AgentActivityState.TYPING,
    )
    orch = AgentPersona(
        agent_id="orch_typing",
        name="Lead Orchestrator",
        office_id="off_typing",
        role=DeskRole.ORCHESTRATOR,
        model="claude-sonnet-4-6",
        desk_index=0,
        activity_state=AgentActivityState.TYPING,
    )
    canvas.set_personas(orch, [dev])

    # 16 karelik yazma ritmi döngüsü boyunca çizim ve offscreen render testi
    for frame in range(16):
        canvas._pulse_frame = frame
        img = QImage(800, 500, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.black)
        canvas.render(img)
        assert not img.isNull()

        # Masanın solundaki sarı Post-it not kağıdının (RGB ~ 254, 240, 138) varlığı
        # Desk 1 x=80, y=230 -> note_x = 94, note_y = 280
        color_note = img.pixelColor(95, 282)
        assert color_note.red() > 200 and color_note.green() > 200

        # Monitör içi terminal yeşili kod akışı (RGB ~ 8, 24, 14 veya 74, 222, 128)
        # Monitor 1 x=115, y=240
        color_screen = img.pixelColor(125, 248)
        assert color_screen.green() > 0


def test_pixel_canvas_thought_bubble_harmonic_floating_and_sparkles(qapp):
    """Düşünme balonu: 2D harmonik süzülme, baloncuk zinciri, dalgalanan düşünce noktaları ve dönen yıldız."""
    canvas = PixelCanvas()
    canvas.resize(800, 500)

    thinker = AgentPersona(
        agent_id="thinker_ag",
        name="Cognitive Thinker",
        office_id="off_think",
        role=DeskRole.RESEARCHER,
        model="gemini-2.5-pro",
        desk_index=2,
        activity_state=AgentActivityState.THINKING,
    )
    orch = AgentPersona(
        agent_id="orch_ag",
        name="Orchestrator Mind",
        office_id="off_think",
        role=DeskRole.ORCHESTRATOR,
        model="claude-sonnet-4-6",
        desk_index=0,
        activity_state=AgentActivityState.THINKING,
    )
    canvas.set_personas(orch, [thinker])

    # Süzülme döngüsündeki tüm karelerde render stabilitesi
    for frame in range(24):
        canvas._pulse_frame = frame
        img = QImage(800, 500, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.black)
        canvas.render(img)
        assert not img.isNull()

        # Düşünce balonunun lila/mor sınır aurası veya iç rengi
        # Desk 0 x=270, y=30, w=160 -> bubble x ~ 384, y ~ 20..30
        bubble_sample = img.pixelColor(390, 25)
        # Siyah zemin dışında çizilmiş piksel varlığı
        assert not (bubble_sample.red() == 0 and bubble_sample.green() == 0 and bubble_sample.blue() == 0)


def test_pixel_canvas_speech_bubble_and_custom_sizes_headless_stress(qapp):
    """Ekstrem çözünürlükler, çoklu ajanlar, konuşma balonları ve hızlı saat döngüsü stres testi."""
    canvas = PixelCanvas()

    # Ekstrem küçük ve büyük boyutlar
    for w, h in [(100, 100), (300, 200), (1920, 1080), (2560, 1440)]:
        canvas.resize(w, h)
        img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        canvas.render(img)
        assert not img.isNull()
        assert img.width() == w
        assert img.height() == h

    # 8 dinamik alt ajan yerleşimi ve konuşma balonu
    orch = AgentPersona(
        agent_id="orch_stress",
        name="Stress Lead",
        office_id="off_stress",
        role=DeskRole.ORCHESTRATOR,
        model="claude-sonnet-4-6",
        desk_index=0,
        activity_state=AgentActivityState.TALKING,
        active_speech_text="Mimari senkronizasyon aktif.",
    )
    sub_agents = [
        AgentPersona(
            agent_id=f"sub_stress_{i}",
            name=f"Agent Specialist {i}",
            office_id="off_stress",
            role=DeskRole.DEVELOPER,
            desk_index=i + 1,
            activity_state=AgentActivityState.TYPING if i % 2 == 0 else AgentActivityState.THINKING,
        )
        for i in range(8)
    ]
    canvas.set_personas(orch, sub_agents)
    assert len(canvas.desks) >= 9

    # Hızlı 120 tick döngüsü
    for _ in range(120):
        canvas._on_tick()

    img = QImage(1200, 700, QImage.Format.Format_ARGB32_Premultiplied)
    canvas.render(img)
    assert not img.isNull()
    persona = AgentPersona(
        agent_id="term_ag_01",
        name="Security Sentinel",
        office_id="off_term",
        role=DeskRole.TESTER,
        model="gemini-3.8-flash-high",
    )
    pane = AgentTerminalPane(persona=persona)

    # Başlık ve model badge kontrolü
    assert "Security Sentinel" in pane.lbl_title.text()
    assert "Gemini" in pane.lbl_model_badge.text()

    # Delta Token güncelleme
    pane.update_token_meter(delta_in=120, delta_out=85, tot_in=1200, tot_out=850)
    assert "+120 / +85" in pane.lbl_tokens.text()

    # Metin ekleme
    pane.append_chunk("Line 1: Test initialized.\n")
    pane.append_chunk("Line 2: All assertions passed.\n")
    output_text = pane.terminal_output.toPlainText()
    assert "Test initialized" in output_text
    assert "All assertions passed" in output_text

    # Temizleme
    pane.clear_terminal()
    assert pane.terminal_output.toPlainText() == ""


def test_offices_overview_and_detail_flow(qapp):
    mgr = OfficeManager()
    o1 = mgr.create_office(name="Core Desk", project_root="C:/proj_core")
    o2 = mgr.create_office(name="UI Desk", project_root="C:/proj_ui")

    # Genel bakış bileşeni
    overview = OfficesOverviewWidget(mgr)
    assert overview.grid_layout.count() == 2

    # Seçim sinyali testi
    selected_offices = []
    overview.office_selected.connect(lambda oid: selected_offices.append(oid))

    # Detay bileşeni
    detail = OfficeDetailWidget(orchestrator=o1)
    assert detail.lbl_office_name.text() == "🏢 Core Desk"
    assert len(detail.terminal_panes) >= 4

    # Ana Pencere (AgentDeskWindow)
    win = AgentDeskWindow(office_manager=mgr)
    assert win.stack.count() >= 1
    assert win.stack.currentIndex() == 0  # Başlangıçta genel bakış

    # Ofise geçiş
    win.open_office_detail(o1.config.office_id)
    assert win.stack.currentIndex() == 1  # Detay sayfası aktif

    # Geri dön
    win.show_overview()
    assert win.stack.currentIndex() == 0  # Tekrar genel bakış


def test_pixel_canvas_update_office_method_and_dynamic_refresh(qapp):
    """PixelCanvas.update_office metodunun orkestratör ile entegrasyonu ve dinamik yenileme."""
    mgr = OfficeManager()
    orch = mgr.create_office(name="Dynamic Office", project_root="C:/proj_dyn")
    canvas = PixelCanvas()
    canvas.resize(800, 500)

    # Başlangıçta orkestratörden güncelle
    canvas.update_office(orch)
    assert canvas.desks[0].persona.name == orch.persona.name

    # Yeni alt ajan ekle ve update_office ile tekrar senkronize et
    orch.create_sub_agent(
        name="Auto Developer",
        role=DeskRole.DEVELOPER,
        model="gemini-3.8-flash-high",
    )
    canvas.update_office(orch)
    found_dev = any(d.persona and d.persona.name == "Auto Developer" for d in canvas.desks.values())
    assert found_dev

    # Headless render testi
    img = QImage(800, 500, QImage.Format.Format_ARGB32_Premultiplied)
    canvas.render(img)
    assert not img.isNull()


def test_pixel_canvas_typing_full_animation_cycle_and_particle_decay(qapp):
    """Masa başında yazma animasyonu: 60 karelik tam döngü, mekanik tuş vuruşları, sözdizimi parçacıkları ve headless kararlılık."""
    canvas = PixelCanvas()
    canvas.resize(800, 500)

    dev = AgentPersona(
        agent_id="dev_specialist",
        name="Developer Specialist",
        office_id="off_typing_full",
        role=DeskRole.DEVELOPER,
        model="gemini-3.8-flash-high",
        desk_index=1,
        activity_state=AgentActivityState.TYPING,
    )
    orch = AgentPersona(
        agent_id="orch_lead",
        name="Lead Orchestrator",
        office_id="off_typing_full",
        role=DeskRole.ORCHESTRATOR,
        model="claude-sonnet-4-6",
        desk_index=0,
        activity_state=AgentActivityState.TYPING,
    )
    canvas.set_personas(orch, [dev])

    # 60 karelik tam döngüde render stabilitesi
    for frame in range(60):
        canvas._pulse_frame = frame
        img = QImage(800, 500, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.black)
        canvas.render(img)
        assert not img.isNull()
        assert img.width() == 800 and img.height() == 500

        # Monitör 1 içindeki kod akışı yeşili
        screen_color = img.pixelColor(125, 248)
        assert screen_color.green() > 0

        # Sarı Post-it notu
        note_color = img.pixelColor(95, 282)
        assert note_color.red() > 200 and note_color.green() > 200


def test_pixel_canvas_thought_bubble_conduit_and_breathing_full_cycle(qapp):
    """Düşünme balonu: 60 karelik döngü, 4 baloncuklu iletken kanalı, nefes alan puf lobları ve nöral kıvılcımlar."""
    canvas = PixelCanvas()
    canvas.resize(800, 500)

    thinker = AgentPersona(
        agent_id="thinker_lead",
        name="Cognitive Architect",
        office_id="off_thought_full",
        role=DeskRole.ORCHESTRATOR,
        model="claude-sonnet-4-6",
        desk_index=0,
        activity_state=AgentActivityState.THINKING,
    )
    dev_thinker = AgentPersona(
        agent_id="dev_think",
        name="Algorithm Thinker",
        office_id="off_thought_full",
        role=DeskRole.DEVELOPER,
        model="gemini-3.8-flash-high",
        desk_index=1,
        activity_state=AgentActivityState.THINKING,
    )
    canvas.set_personas(thinker, [dev_thinker])

    for frame in range(60):
        canvas._pulse_frame = frame
        img = QImage(800, 500, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.black)
        canvas.render(img)
        assert not img.isNull()

        # Düşünce bulutu çekirdeğinde çizilmiş piksel varlığı (Desk 0: x=270, y=30)
        bubble_pixel = img.pixelColor(390, 25)
        assert not (bubble_pixel.red() == 0 and bubble_pixel.green() == 0 and bubble_pixel.blue() == 0)


def test_pixel_canvas_rapid_state_switching_stress_headless(qapp):
    """Hızlı durum geçişleri ve aşırı çözünürlüklerde QPainter headless offscreen stres testi."""
    canvas = PixelCanvas()
    canvas.resize(700, 450)

    orch = AgentPersona(
        agent_id="orch_stress_2",
        name="Orchestrator Stress",
        office_id="off_stress_2",
        role=DeskRole.ORCHESTRATOR,
        desk_index=0,
    )
    devs = [
        AgentPersona(
            agent_id=f"dev_s_{i}",
            name=f"Developer {i}",
            office_id="off_stress_2",
            role=DeskRole.DEVELOPER,
            desk_index=i + 1,
        )
        for i in range(4)
    ]
    canvas.set_personas(orch, devs)

    states = list(AgentActivityState)
    for tick in range(120):
        canvas._pulse_frame = tick % 60
        # Dinamik durum geçişleri
        st = states[tick % len(states)]
        canvas.update_agent_activity("orch_stress_2", st)
        canvas.update_agent_activity("dev_s_0", states[(tick + 1) % len(states)])
        canvas.update_agent_activity("dev_s_1", states[(tick + 2) % len(states)])

        if tick % 20 == 0:
            img = QImage(700, 450, QImage.Format.Format_ARGB32_Premultiplied)
            canvas.render(img)
            assert not img.isNull()

