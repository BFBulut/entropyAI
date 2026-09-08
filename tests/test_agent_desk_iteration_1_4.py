"""
Unit and Integration Test Suite: Agent Desk Iterations 1 & 4.
Validates:
- MediaPayloadHandler (PDF & Image inspection, clipboard persistence, drag-drop processing, markdown formatting)
- AgentActivityState (coffee_break, talking)
- AgentPersona (XP, level progression, badges, energy consumption and resting)
- TaskItem (media_attachments)
- ProjectExporter (clean ZIP export, Git checkpoint automation)
"""

import os
import io
import shutil
import tempfile
import zipfile
import subprocess
import pytest
from pathlib import Path

from src.entropy.agent_desk.core.models import (
    AgentActivityState,
    AgentPersona,
    TaskItem,
    DeskRole,
    TaskStatus,
)
from src.entropy.agent_desk.core.media_payload_handler import (
    MediaPayloadHandler,
    MediaPayloadInfo,
)
from src.entropy.agent_desk.core.project_exporter import (
    ProjectExporter,
)


# ---------------------------------------------------------------------------
# Test Fixtures & Dummy Binary Payloads
# ---------------------------------------------------------------------------

# Minimal 1x1 valid PNG (67 bytes)
TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)

# Minimal 1x1 GIF89a
TINY_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04"
    b"\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)

# Minimal 1x1 24bpp BMP
TINY_BMP = (
    b"BM\x3a\x00\x00\x00\x00\x00\x00\x00\x36\x00\x00\x00\x28\x00\x00\x00"
    b"\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x18\x00\x00\x00\x00\x00"
    b"\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\xff\xff\xff\x00"
)

# Minimal dummy PDF with 2 pages
DUMMY_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj\n"
    b"2 0 obj <</Type /Pages /Kids [3 0 R 4 0 R] /Count 2>> endobj\n"
    b"3 0 obj <</Type /Page /Parent 2 0 R /Contents 5 0 R>> endobj\n"
    b"4 0 obj <</Type /Page /Parent 2 0 R /Contents 6 0 R>> endobj\n"
    b"5 0 obj <</Length 20>> stream\n(First Page Text) Tj\nendstream endobj\n"
    b"6 0 obj <</Length 21>> stream\n(Second Page Text) Tj\nendstream endobj\n"
    b"xref\n0 7\ntrailer <</Root 1 0 R>>\nstartxref\n300\n%%EOF"
)


# ---------------------------------------------------------------------------
# 1. Models & AgentPersona Gamification / Energy Tests
# ---------------------------------------------------------------------------

def test_agent_activity_states_iteration4():
    assert AgentActivityState.COFFEE_BREAK == "coffee_break"
    assert AgentActivityState.TALKING == "talking"
    assert AgentActivityState.IDLE == "idle"
    assert AgentActivityState.TYPING == "typing"


def test_agent_persona_xp_and_level_progression():
    persona = AgentPersona(
        agent_id="ag_001",
        name="Neo Dev",
        office_id="off_hq",
        role=DeskRole.DEVELOPER,
    )
    assert persona.xp == 0
    assert persona.level == 1
    assert persona.specialization_badges == []
    assert persona.focus_energy_pct == 100.0

    # 1. Seviye artışı: +150 XP -> Level 2
    persona.add_xp(150)
    assert persona.xp == 150
    assert persona.level == 2
    assert "Junior Operative" in persona.specialization_badges

    # 2. Daha fazla XP: +350 XP -> Toplam 500 XP -> Level 6
    persona.add_xp(350)
    assert persona.xp == 500
    assert persona.level == 6
    assert "Senior Architect" in persona.specialization_badges
    assert "XP Veteran" in persona.specialization_badges

    # Negatif veya sıfır XP hiçbir şeyi bozmamalı
    persona.add_xp(0)
    assert persona.level == 6


def test_agent_persona_focus_energy_and_recharge():
    persona = AgentPersona(
        agent_id="ag_002",
        name="Energy Tester",
        office_id="off_hq",
    )
    assert persona.focus_energy_pct == 100.0

    # Enerji tüket
    remaining = persona.consume_energy(30.0)
    assert remaining == 70.0
    assert persona.focus_energy_pct == 70.0

    # Fazla enerji tüketince 0.0'ın altına düşmemeli
    persona.consume_energy(90.0)
    assert persona.focus_energy_pct == 0.0

    # Mola verip şarj ol
    recharged = persona.rest_and_recharge(40.0)
    assert recharged == 40.0
    assert persona.focus_energy_pct == 40.0

    # 100.0 tavan sınırı aşılmamalı
    persona.rest_and_recharge(150.0)
    assert persona.focus_energy_pct == 100.0


def test_agent_persona_badges_and_tasks_completed():
    persona = AgentPersona(
        agent_id="ag_003",
        name="Task Master",
        office_id="off_hq",
    )
    persona.tasks_completed = 1
    persona._check_and_update_badges()
    assert "First Mission" in persona.specialization_badges

    persona.tasks_completed = 5
    persona._check_and_update_badges()
    assert "Task Sprinter" in persona.specialization_badges

    persona.tasks_completed = 25
    persona._check_and_update_badges()
    assert "Centurion Worker" in persona.specialization_badges


def test_task_item_media_attachments():
    task = TaskItem(
        task_id="t_media_01",
        office_id="off_hq",
        title="UI Screen Design Implementation",
        media_attachments=[
            "/path/to/mockup.png",
            "/path/to/specs.pdf",
        ],
    )
    assert len(task.media_attachments) == 2
    assert "/path/to/mockup.png" in task.media_attachments
    assert "/path/to/specs.pdf" in task.media_attachments


# ---------------------------------------------------------------------------
# 2. MediaPayloadHandler Tests
# ---------------------------------------------------------------------------

def test_media_payload_handler_inspect_png(tmp_path: Path):
    png_file = tmp_path / "sample.png"
    png_file.write_bytes(TINY_PNG)

    info = MediaPayloadHandler.inspect_file(str(png_file))
    assert info.file_name == "sample.png"
    assert info.is_image is True
    assert info.is_pdf is False
    assert info.image_dimensions == (1, 1)
    assert info.mime_type == "image/png"
    assert "sample.png" in info.md_reference
    assert info.md_reference.startswith("![")


def test_media_payload_handler_inspect_svg(tmp_path: Path):
    svg_file = tmp_path / "diagram.svg"
    svg_file.write_text(
        '<svg width="800" height="600" viewBox="0 0 800 600"><title>Architecture Flow</title></svg>',
        encoding="utf-8",
    )

    info = MediaPayloadHandler.inspect_file(str(svg_file))
    assert info.file_name == "diagram.svg"
    assert info.is_image is True
    assert info.is_pdf is False
    assert info.image_dimensions == (800, 600)
    assert info.mime_type == "image/svg+xml"
    assert "Architecture Flow" in info.text_preview


def test_media_payload_handler_inspect_pdf(tmp_path: Path):
    pdf_file = tmp_path / "document.pdf"
    pdf_file.write_bytes(DUMMY_PDF)

    info = MediaPayloadHandler.inspect_file(str(pdf_file))
    assert info.file_name == "document.pdf"
    assert info.is_pdf is True
    assert info.is_image is False
    assert info.pdf_page_count == 2
    assert info.mime_type == "application/pdf"
    assert "PDF: 2 sayfa" in info.md_reference
    assert info.md_reference.startswith("[")


def test_media_payload_handler_binary_fallback_gif_bmp(tmp_path: Path):
    gif_file = tmp_path / "anim.gif"
    gif_file.write_bytes(TINY_GIF)
    bmp_file = tmp_path / "raw.bmp"
    bmp_file.write_bytes(TINY_BMP)

    gif_info = MediaPayloadHandler.inspect_file(str(gif_file))
    assert gif_info.is_image is True
    assert gif_info.image_dimensions == (1, 1)
    assert gif_info.mime_type == "image/gif"

    bmp_info = MediaPayloadHandler.inspect_file(str(bmp_file))
    assert bmp_info.is_image is True
    assert bmp_info.image_dimensions == (1, 1)
    assert bmp_info.mime_type == "image/bmp"


def test_media_payload_handler_save_clipboard_image(tmp_path: Path):
    target_media_dir = tmp_path / ".entropy" / "media" / "office_101"
    saved_path = MediaPayloadHandler.save_clipboard_image(TINY_PNG, str(target_media_dir))

    assert os.path.exists(saved_path)
    assert Path(saved_path).name.startswith("clipboard_")
    assert Path(saved_path).suffix == ".png"

    # Dosyanın okunabilir olduğunu doğrula
    info = MediaPayloadHandler.inspect_file(saved_path)
    assert info.image_dimensions == (1, 1)


def test_media_payload_handler_process_dropped_files(tmp_path: Path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    f1 = source_dir / "asset1.png"
    f1.write_bytes(TINY_PNG)
    f2 = source_dir / "brief.pdf"
    f2.write_bytes(DUMMY_PDF)

    target_dir = tmp_path / "desk_inbox"
    payloads = MediaPayloadHandler.process_dropped_files(
        [str(f1), str(f2)],
        str(target_dir),
    )

    assert len(payloads) == 2
    p1 = next(p for p in payloads if p.file_name == "asset1.png")
    p2 = next(p for p in payloads if p.file_name == "brief.pdf")

    assert p1.is_image is True
    assert p2.is_pdf is True
    assert os.path.exists(p1.file_path)
    assert os.path.exists(p2.file_path)


def test_media_payload_handler_format_markdown(tmp_path: Path):
    png_file = tmp_path / "snapshot.png"
    png_file.write_bytes(TINY_PNG)
    pdf_file = tmp_path / "report.pdf"
    pdf_file.write_bytes(DUMMY_PDF)

    info_png = MediaPayloadHandler.inspect_file(str(png_file))
    info_pdf = MediaPayloadHandler.inspect_file(str(pdf_file))

    md = MediaPayloadHandler.format_markdown_attachments([info_png, info_pdf])
    assert "### 📎 İliştirilmiş Medya ve Belgeler" in md
    assert "snapshot.png" in md
    assert "report.pdf" in md
    assert "PDF: 2 sayfa" in md


def test_media_payload_handler_errors(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        MediaPayloadHandler.inspect_file(str(tmp_path / "non_existing.png"))

    with pytest.raises(ValueError):
        MediaPayloadHandler.save_clipboard_image(b"", str(tmp_path))


# ---------------------------------------------------------------------------
# 3. ProjectExporter Tests
# ---------------------------------------------------------------------------

def test_project_exporter_zip_clean_packaging(tmp_path: Path):
    workspace = tmp_path / "test_workspace"
    workspace.mkdir()

    # Temiz proje dosyaları
    (workspace / "main.py").write_text("print('hello')", encoding="utf-8")
    (workspace / "README.md").write_text("# Project Docs", encoding="utf-8")
    src_sub = workspace / "src"
    src_sub.mkdir()
    (src_sub / "module.py").write_text("X = 42", encoding="utf-8")

    # Atlanması gereken gereksiz klasör ve dosyalar
    pycache = workspace / "__pycache__"
    pycache.mkdir()
    (pycache / "main.cpython-313.pyc").write_bytes(b"dummy pyc bytecode")

    pytest_cache = workspace / ".pytest_cache"
    pytest_cache.mkdir()
    (pytest_cache / "cache.json").write_text("{}", encoding="utf-8")

    git_dir = workspace / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main", encoding="utf-8")

    venv_dir = workspace / ".venv"
    venv_dir.mkdir()
    (venv_dir / "pyvenv.cfg").write_text("home = /bin", encoding="utf-8")

    target_zip = tmp_path / "exports" / "workspace_clean.zip"

    zip_path = ProjectExporter.export_office_to_zip(
        office_id="off_demo",
        project_root=str(workspace),
        target_zip_path=str(target_zip),
    )

    assert os.path.exists(zip_path)
    assert zipfile.is_zipfile(zip_path)

    # Zip içeriğini doğrula
    with zipfile.ZipFile(zip_path, "r") as zf:
        namelist = zf.namelist()

        # Dahil edilenler
        assert "main.py" in namelist
        assert "README.md" in namelist
        assert any(name.startswith("src/") for name in namelist)

        # Hariç tutulanlar (ASLA olmamalı)
        for name in namelist:
            assert "__pycache__" not in name
            assert ".pytest_cache" not in name
            assert ".git" not in name
            assert ".venv" not in name
            assert not name.endswith(".pyc")


def test_project_exporter_git_checkpoint(tmp_path: Path):
    # Git yüklü mü kontrol et
    git_check = subprocess.run(["git", "--version"], capture_output=True, text=True)
    if git_check.returncode != 0:
        pytest.skip("Git bu ortamda kurulu değil, git checkpoint testi atlanıyor.")

    repo_dir = tmp_path / "git_test_repo"
    repo_dir.mkdir()

    # 1. Dosya oluştur
    (repo_dir / "code.py").write_text("print('v1')", encoding="utf-8")

    # Checkpoint oluştur
    res1 = ProjectExporter.create_git_checkpoint(
        project_root=str(repo_dir),
        message="feat: initial checkpoint",
        auto_init_if_missing=True,
    )

    assert res1["success"] is True
    assert res1["commit_hash"] is not None
    assert len(res1["commit_hash"]) >= 7
    assert res1["is_clean"] is False
    assert res1["changed_files_count"] >= 1

    # 2. Değişiklik yapmadan tekrar çağır -> is_clean == True
    res2 = ProjectExporter.create_git_checkpoint(
        project_root=str(repo_dir),
        message="checkpoint without changes",
    )
    assert res2["success"] is True
    assert res2["is_clean"] is True
    assert res2["changed_files_count"] == 0
    assert res2["commit_hash"] == res1["commit_hash"]

    # 3. Yeni dosya ekle ve checkpoint al
    (repo_dir / "new_file.txt").write_text("New data", encoding="utf-8")
    res3 = ProjectExporter.create_git_checkpoint(
        project_root=str(repo_dir),
        message="docs: added new file",
    )
    assert res3["success"] is True
    assert res3["is_clean"] is False
    assert res3["commit_hash"] != res1["commit_hash"]
