from pathlib import Path

import pytest


def test_is_cli_command_allowed_accepts_safe_and_blocks_dangerous(service):
    assert service.is_cli_command_allowed("notepad.exe")
    assert not service.is_cli_command_allowed("powershell -Command calc")
    assert not service.is_cli_command_allowed("curl https://example.com")


def test_run_shell_launches_allowed_command(service, monkeypatch):
    launched = {}
    monkeypatch.setattr("mcp_service.subprocess.Popen", lambda args, shell=False: launched.setdefault("args", args))
    monkeypatch.setattr("mcp_service.time.sleep", lambda seconds: None)

    result = service.run_shell("notepad.exe")

    assert result == "Launched command: notepad.exe"
    assert launched["args"] == ["notepad.exe"]


def test_run_shell_rejects_blocked_command(service):
    with pytest.raises(ValueError):
        service.run_shell("powershell -Command whoami")


def test_extract_pdf_text_validates_path_and_extension(service, monkeypatch):
    monkeypatch.setattr("mcp_service.os.path.exists", lambda path: False)
    assert service.extract_pdf_text("missing.pdf") == "Error: PDF file not found at missing.pdf"

    monkeypatch.setattr("mcp_service.os.path.exists", lambda path: True)
    assert service.extract_pdf_text("note.txt") == "Error: File note.txt is not a PDF file"


def test_list_pdfs_in_directory_filters_entries(service, monkeypatch, tmp_path):
    pdf = tmp_path / "a.pdf"
    txt = tmp_path / "b.txt"
    pdf.write_text("x")
    txt.write_text("y")

    result = service.list_pdfs_in_directory(str(tmp_path))

    assert result == [str(pdf)]


def test_extract_all_pdfs_text_handles_missing_and_empty(service, monkeypatch, tmp_path):
    missing = service.extract_all_pdfs_text(str(tmp_path / "missing"))
    assert missing == {"error": f"Directory not found: {tmp_path / 'missing'}"}

    monkeypatch.setattr(service, "get_pdf_files_in_directory", lambda path: [])
    empty = service.extract_all_pdfs_text(str(tmp_path))
    assert empty == {"message": f"No PDF files found in directory: {tmp_path}"}


def test_extract_all_pdfs_text_batches_results(service, monkeypatch, tmp_path):
    monkeypatch.setattr(service, "get_pdf_files_in_directory", lambda path: ["a.pdf", "b.pdf"])
    monkeypatch.setattr(
        service,
        "extract_text_from_pdf_batch",
        lambda paths, simulate_human: {"a.pdf": "A", "b.pdf": "B"},
    )

    result = service.extract_all_pdfs_text(str(tmp_path), simulate_human=False)

    assert result == {"a.pdf": "A", "b.pdf": "B"}


def test_word_and_excel_and_powerpoint_dispatch(service, monkeypatch):
    calls = []

    def fake_execute(app_root_name, function, arguments, process_name=None):
        calls.append((app_root_name, function, arguments, process_name))
        return "ok"

    monkeypatch.setattr(service, "_execute_office_command", fake_execute)

    assert service.word_insert_table(2, 3, "doc") == "ok"
    assert service.excel_get_range_values("Sheet1", 1, 1, 2, 2, "book") == "ok"
    assert service.powerpoint_save_as("d", "name", ".pptx", True, "deck") == "ok"

    assert calls[0] == ("WINWORD.EXE", "insert_table", {"rows": 2, "columns": 3}, "doc")
    assert calls[1] == (
        "EXCEL.EXE",
        "get_range_values",
        {"sheet_name": "Sheet1", "start_row": 1, "start_col": 1, "end_row": 2, "end_col": 2},
        "book",
    )
    assert calls[2] == (
        "POWERPNT.EXE",
        "save_as",
        {
            "file_dir": "d",
            "file_name": "name",
            "file_ext": ".pptx",
            "current_slide_only": True,
        },
        "deck",
    )
