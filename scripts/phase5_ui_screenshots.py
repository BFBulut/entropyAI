"""
Faz 5.5 / 5.6 ekran görüntüsü üreteci.

Çalıştırma (Windows, PowerShell/bash):
    QT_QPA_PLATFORM=offscreen QT_QPA_FONTDIR=C:/Windows/Fonts \
        python scripts/phase5_ui_screenshots.py

Çıktı: `scratch/ui/phase5/*.png`

Neden ayrı betik: ekran görüntüleri testin parçası değildir (yavaş ve makineye
bağımlı), ama tasarımın "okunabilirlik" iddiası ancak görülerek doğrulanır.
Sahte veri kullanılır; model çağrısı, ağ ve harness başlatma yoktur.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

OUT_DIR = ROOT / "scratch" / "ui" / "phase5"

# Konsol cp1254 olabilir: ok isareti ve Turkce karakterler patlamasin.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

from PySide6.QtCore import QSize  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


def shot(widget, name: str, size=(980, 700)) -> Path:
    """Widget'ı verilen ölçüde çizip PNG olarak kaydeder."""
    widget.resize(QSize(*size))
    widget.show()
    for _ in range(3):
        QApplication.processEvents()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{name}.png"
    widget.grab().save(str(path))
    print(f"  -> {path.relative_to(ROOT)}")
    return path


def fake_reports(directory: Path, count: int = 200):
    """200 sahte rapor: dört konu ailesi, farklı güven/aciliyet profilleri."""
    from entropy.ui.widgets.reports_viewer import read_report_meta

    directory.mkdir(parents=True, exist_ok=True)
    # On konu ailesi: gercek kasada basliklar bu kadar cesitli olur; hepsi ayni
    # kalibi tasisaydi kumeleme yapay biçimde iyi görünürdü.
    topics = [
        ("Q3 Finansal Denetim", "Nakit akışı beklenenin %12 altında.", "Bütçeyi kısmak gerekiyor."),
        ("Nakit Akışı Projeksiyonu", "Dört çeyreklik projeksiyon aşağı revize edildi.", "Yeniden fiyatlama gerekli."),
        ("Pazarlama Kampanyası Analizi", "Dönüşüm oranı %3,4'e çıktı.", "Bütçeyi ikinci kanala kaydır."),
        ("Kampanya Kreatif Testi", "B varyantı A'yı %18 geçti.", "B varyantına geç."),
        ("Altyapı İzleme", "Gecikme p95 değeri 480 ms.", "Önbellek katmanı eklenmeli."),
        ("Veritabanı Sağlık Taraması", "İndeks parçalanması %31.", "Gece bakımı planla."),
        ("Ofis Devri Özeti", "Kart zinciri değerlendiriciden döndü.", "Revizyon iste."),
        ("Ajan Performans Notu", "Ortalama tur maliyeti 14k token.", "Bütçe tavanını düşür."),
        ("Rakip Fiyat Takibi", "İki rakip fiyatını %5 indirdi.", "Fiyat bandını gözden geçir."),
        ("Müşteri Geri Bildirim Sentezi", "Şikayetlerin %40'ı teslimat süresi.", "Lojistik ile görüş."),
    ]
    entries = []
    now = time.time()
    for i in range(count):
        title_base, finding, decision = topics[i % len(topics)]
        # Her 17. rapor kusurlu: öne çıkan (düşük güvenli) bölümü doldursun.
        # Yalnizca iki konu ailesi kusurlu: sessiz bolum bos kalmasin.
        broken = (i % len(topics)) in (0, 4) and (i % 3 == 0)
        body = (
            f"{finding} Ölçüm {i} numaralı koşudan alındı.\n\n"
            + ("Görev failed durumunda kaldı; grade: 0.4.\n\n" if broken else "")
            + f"## Öneri\n{decision}\n"
        )
        path = directory / f"rapor_{i:03d}.md"
        path.write_text(
            f"---\ntitle: {title_base} Raporu {i}\n---\n\n{body}", encoding="utf-8"
        )
        stamp = now - (i * 120)
        os.utime(path, (stamp, stamp))
        entries.append(read_report_meta(path))
    return entries


def main() -> int:
    app = QApplication.instance() or QApplication([])
    scratch = ROOT / "scratch" / "phase5_fixture"
    print("Faz 5 ekran görüntüleri:")

    # 1. Rapor Merkezi — 200 sahte rapor
    from entropy.ui.widgets.report_center import ReportCenterWidget
    from entropy.ui.widgets.report_inbox import ReportInboxStore

    entries = fake_reports(scratch / "reports")
    store = ReportInboxStore(path=scratch / "inbox.json")
    center = ReportCenterWidget(store=store)
    center.set_entries(entries)
    result = {
        "kart": len(center.cards()),
        "sessiz": len(center.quiet_cards()),
        "toplam": 200,
    }
    print(f"  Rapor Merkezi: {result}")
    shot(center, "report_center_200", size=(760, 820))
    center.toggle_quiet()
    shot(center, "report_center_quiet_expanded", size=(760, 820))
    center.close()

    # 2. Komut paleti
    from entropy.ui.widgets.command_palette import CommandPalette

    palette_items = [
        {"kind": "command", "label": "/handoff", "subtitle": "Aktarım sayfası yazar ve bağlamı devreder", "payload": "/handoff"},
        {"kind": "command", "label": "/ask", "subtitle": "Bir ofis orkestratörüne soru sorar", "payload": "/ask <ofis> "},
        {"kind": "command", "label": "/desk", "subtitle": "Ofisler ve süren ofis kartları", "payload": "/desk"},
        {"kind": "skill", "label": "financial-auditor", "subtitle": "Finansal denetim ve kantitatif analiz", "payload": "/financial-auditor"},
        {"kind": "skill", "label": "autonomous-agent", "subtitle": "Otonom ajan mimarisi araştırması", "payload": "/autonomous-agent"},
        {"kind": "agent", "label": "Researcher", "subtitle": "Kaynak tarar ve özet çıkarır", "payload": "/agent Researcher"},
        {"kind": "agent", "label": "CodeArchitect", "subtitle": "Mimari kararlar ve kod incelemesi", "payload": "/agent CodeArchitect"},
        {"kind": "office", "label": "Finans", "subtitle": "Mali işler ofisi", "payload": "/ask Finans "},
        {"kind": "office", "label": "Medya", "subtitle": "Kampanya ve içerik ofisi", "payload": "/ask Medya "},
        {"kind": "report", "label": "Q3 Finansal Denetim Raporu 0", "subtitle": "financial-auditor", "payload": "C:/r0.md"},
        {"kind": "report", "label": "Altyapı İzleme Raporu 2", "subtitle": "devops", "payload": "C:/r2.md"},
    ]
    palette = CommandPalette(items=palette_items)
    palette.apply_filter("fin")
    shot(palette, "command_palette", size=(620, 420))
    palette.close()

    # 3. Odak modu — önce/sonra
    from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

    from entropy.ui.widgets.focus_mode import install_focus_mode

    demo = QWidget()
    demo.setStyleSheet("background:#080B10;")
    layout = QHBoxLayout(demo)
    panels = []
    for text, color in (
        ("📚 Raporlar", "#00F0FF"), ("💬 Sohbet (odak)", "#00FF9D"),
        ("🌐 Bellek Haritası", "#BC8CFF"), (">_ Terminal", "#E3B341"),
    ):
        label = QLabel(text)
        label.setStyleSheet(
            f"color:{color}; border:1px solid {color}; border-radius:8px;"
            " padding:40px; font-size:16px; font-weight:bold;"
        )
        layout.addWidget(label)
        panels.append(label)
    primary = panels[1]
    controller = install_focus_mode(demo, primary=primary, secondary=[panels[0], panels[2], panels[3]])
    shot(demo, "focus_mode_off", size=(900, 240))
    controller.activate()
    shot(demo, "focus_mode_on", size=(900, 240))
    demo.close()

    # 4. Zaman çizelgesi
    from entropy.ui.widgets.timeline_panel import TimelinePanel, day_bounds

    now = time.time()
    start, _ = day_bounds(now)
    events = [
        {"kind": "task", "ts": start + 8 * 3600, "title": "Sabah bülteni", "detail": "success", "target": "t1"},
        {"kind": "report", "ts": start + 9 * 3600, "title": "Q3 Finansal Denetim Raporu 0", "detail": "financial-auditor", "target": "C:/r0.md"},
        {"kind": "office", "ts": start + 10 * 3600, "title": "Finans ofisi kart planını gönderdi", "detail": "office/Finans · report · completed", "target": "m1"},
        {"kind": "handoff", "ts": start + 11 * 3600, "title": "Handoff — bağlam %62", "detail": "", "target": "C:/h.md"},
        {"kind": "task", "ts": start + 12 * 3600, "title": "Kasa yedeği", "detail": "failed", "target": "t2"},
        {"kind": "report", "ts": start + 13 * 3600, "title": "Altyapı İzleme Raporu 2", "detail": "devops", "target": "C:/r2.md"},
        {"kind": "office", "ts": start + 14 * 3600, "title": "Medya ofisi revizyon istedi", "detail": "office/Medya · question", "target": "m2"},
    ]
    timeline = TimelinePanel(events=events, now=now)
    shot(timeline, "timeline_today", size=(680, 340))
    timeline.close()

    # 5. Bildirim merkezi
    from entropy.ui.widgets.notification_center import NotificationCenter

    notifications = NotificationCenter()
    for kind, title, target in (
        ("report", "Q3 Finansal Denetim Raporu 0", "C:/r0.md"),
        ("task_done", "Sabah bülteni", "t1"),
        ("task_failed", "Kasa yedeği", "t2"),
        ("mailbox", "office/Finans kutusu güncellendi", "Finans"),
        ("playbook", "financial-auditor yordamı güncellendi", "financial-auditor"),
        ("skill", "financial-auditor (güven 0.87)", "financial-auditor"),
        ("provider", "claude: giriş yok", "claude"),
        ("office", "Medya değişti", "Medya"),
    ):
        notifications.add(kind, title, target)
    shot(notifications, "notification_center", size=(680, 340))
    notifications.close()

    # 6. Sağlayıcı rozeti
    from entropy.ui.widgets.provider_badge import ProviderStatusBadge

    badge = ProviderStatusBadge()
    badge.set_status("agy", {"logged_in": True, "plan": "Pro", "session_window": "3 sa 12 dk", "quota_hint": "%38"})
    badge.set_status("claude", {"logged_in": False, "last_error": "oturum bulunamadı"})
    shot(badge, "provider_badge", size=(420, 40))
    badge.close()

    # 7. Graf kontrol şeridi (QtWebEngine varsa gerçek çizim)
    try:
        shot_graph_controls()
    except Exception as exc:  # pragma: no cover
        print(f"  ! Graf kontrol şeridi görüntüsü alınamadı: {exc}")

    print("Bitti.")
    return 0


def shot_graph_controls() -> None:
    """
    Grafik HTML'ini sahte cift zamanli veriyle cizip yakalar.

    QtWebEngine offscreen platformda GPU baglamini kaybediyor ve `grab()` bos
    kare veriyor (olculdu: tamamen siyah PNG). Bu yuzden HTML diske yazilip
    Chrome/Edge'in headless ekran goruntusu kullaniliyor. Tarayici bulunamazsa
    yalnizca HTML birakilir ve durum bildirilir.
    """
    import json
    import shutil
    import subprocess

    from entropy.ui.widgets.knowledge_graph import GRAPH_HTML_TEMPLATE

    now_ms = int(time.time() * 1000)
    old_ms = now_ms - 120 * 86400 * 1000
    nodes = [
        {"id": "ego-entropy-core", "name": "Entropy AI Çekirdeği", "group": "ego", "val": 22, "x": 0, "y": 0},
    ]
    links = []
    labels = ["Finans", "Pazarlama", "Altyapı", "Ofisler"]
    for c in range(4):
        cid = f"com-{c}"
        nodes.append({
            "id": cid, "name": f"🔮 {labels[c]} Topluluğu", "group": "community",
            "val": 12, "member_count": 12 + c * 9, "x": 220 * (c - 1.5), "y": 150,
            "t_valid_from": old_ms, "type": "community", "importance": 0.7,
        })
        links.append({"source": "ego-entropy-core", "target": cid, "is_tree_link": True})
        for i in range(12):
            nid = f"{cid}-n{i}"
            nodes.append({
                "id": nid, "name": f"Olgu {c}.{i}", "group": "semantic", "type": "fact",
                "importance": 0.2 + (i % 8) / 10.0, "val": 9,
                "x": 220 * (c - 1.5) + (i % 4) * 34, "y": 260 + (i // 4) * 34,
                "community_id": cid, "t_valid_from": old_ms + i * 86400000,
                "t_valid_to": (old_ms + 10 * 86400000) if i == 0 else None,
            })
            links.append({"source": cid, "target": nid, "type": "member_of"})
    html = (
        GRAPH_HTML_TEMPLATE
        .replace("__NODES__", json.dumps(nodes, ensure_ascii=False))
        .replace("__LINKS__", json.dumps(links, ensure_ascii=False))
        .replace("__INITIAL_SCOPE__", "all")
        .replace("__ACTIVE_PROJECT_SLUG__", "entropiai")
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    html_path = OUT_DIR / "graph_control_strip.html"
    html_path.write_text(html, encoding="utf-8")

    browser = None
    for candidate in (
        shutil.which("chrome"), shutil.which("msedge"),
        r"C:/Program Files/Google/Chrome/Application/chrome.exe",
        r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    ):
        if candidate and Path(candidate).exists():
            browser = candidate
            break
    if not browser:
        print(f"  ! Tarayıcı bulunamadı; yalnızca HTML: {html_path.relative_to(ROOT)}")
        return
    png = OUT_DIR / "graph_control_strip.png"
    subprocess.run(
        [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
         "--window-size=1200,760", f"--screenshot={png}",
         "--virtual-time-budget=6000", html_path.as_uri()],
        capture_output=True, timeout=120,
    )
    if png.exists():
        print(f"  -> {png.relative_to(ROOT)}")
    else:
        print(f"  ! Ekran görüntüsü alınamadı; HTML: {html_path.relative_to(ROOT)}")

    # Ikinci kare: bir topluluk acik + zaman kaydiricisi gecmise cekili.
    # Kademeli acilmanin ve zaman penceresinin ayni ekranda gorulmesi icin.
    demo_script = (
        "<script>setTimeout(function(){"
        " toggleCommunity('com-0');"
        " var s=document.getElementById('timeSlider'); if(s) s.value=45;"
        " onTimeSlider(45); resetView();"
        "}, 1200);</script>"
    )
    html2_path = OUT_DIR / "graph_community_expanded.html"
    html2_path.write_text(html.replace("</body>", demo_script + "</body>"), encoding="utf-8")
    png2 = OUT_DIR / "graph_community_expanded.png"
    subprocess.run(
        [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
         "--window-size=1200,760", f"--screenshot={png2}",
         "--virtual-time-budget=9000", html2_path.as_uri()],
        capture_output=True, timeout=120,
    )
    if png2.exists():
        print(f"  -> {png2.relative_to(ROOT)}")


if __name__ == "__main__":
    raise SystemExit(main())
