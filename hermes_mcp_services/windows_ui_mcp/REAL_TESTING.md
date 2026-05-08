# Real Testing Guide

This document describes how to validate `windows_ui_mcp` against a real Windows desktop.

## Goal
- Keep `tests/` only as fast development regression tests.
- Use `integration/` as the real acceptance path.
- Treat real acceptance as the source of truth for final validation.
- Run real tests only when the desktop, Office apps, PDF files, and ZonUI-3B service are ready.

## 1. Install Dependencies
```powershell
cd d:\open-source\UFO\hermes_mcp_services\windows_ui_mcp
python -m pip install -r requirements.txt
```

## 2. Start the MCP Server
```powershell
python server.py --host localhost --port 8030
```

Expected endpoint:
- `http://localhost:8030/mcp`

## 3. Run Unit Tests
```powershell
python -m pytest tests
```

These tests do not touch the real desktop.

## 4. Enable Real Integration Tests
Set the shared switch first:

```powershell
$env:HERMES_RUN_REAL_TESTS="1"
```

## 5. Real UI Tests
Prepare a visible desktop app. `notepad.exe` is recommended.

```powershell
$env:HERMES_TEST_UI_APP="notepad.exe"
$env:HERMES_TEST_UI_WINDOW_KEYWORD="Notepad"
python -m pytest integration/test_ui_real.py -s
```

What this validates:
- app launch
- desktop window discovery
- window selection
- window screenshot
- UI tree dump
- control enumeration

Optional:
```powershell
$env:HERMES_TEST_MIN_CONTROLS="1"
```

Notes:
- some modern self-drawn apps expose zero or very few UIA descendants
- for strict control enumeration validation, prefer a classic Win32 app or an Office window

## 6. Real ZonUI-3B Tests
Make sure a reachable ZonUI-3B service is running.

```powershell
$env:ZONUI3B_SERVICE_URL="http://localhost:8100"
$env:HERMES_TEST_UI_WINDOW_KEYWORD="Notepad"
python -m pytest integration/test_mcp_zonui3b_e2e_real.py -s
python -m pytest integration/test_mcp_zonui3b_actions_e2e_real.py -s
python -m pytest integration/test_mcp_strict_acceptance_e2e_real.py -s
```

What this validates:
- window screenshot capture
- ZonUI-3B endpoint connectivity
- find-by-text to get a usable control id
- click flow
- strict acceptance flow (visual change + text write + text readback)

Tips for observation/debug:
```powershell
$env:HERMES_TEST_TEXT="I should appear in Notepad"
$env:HERMES_TEST_WINDOW_CLASS_NAME="Notepad"
$env:HERMES_TEST_WINDOW_EXCLUDE="notepad++|文件资源管理器"
$env:HERMES_TEST_PAUSE_SECONDS="20"
$env:HERMES_TEST_SAVE_ARTIFACTS="1"
python -m pytest integration/test_mcp_strict_acceptance_e2e_real.py -s
```

Artifacts are written to:
- `integration/_artifacts/`

## 7. Real PDF Tests
Prepare at least one text-based PDF and one directory containing PDFs.

```powershell
$env:HERMES_TEST_PDF_PATH="D:\data\sample.pdf"
$env:HERMES_TEST_PDF_DIR="D:\data\pdfs"
python -m pytest integration/test_pdf_real.py -s
```

What this validates:
- single PDF text extraction
- directory scanning

Notes:
- text PDFs are best for validation
- scanned PDFs may return poor text because `PyPDF2` is not OCR

## 8. Real Office Tests
Open real Office files before running these tests.

### Word
```powershell
$env:HERMES_TEST_WORD_PROCESS="WINWORD.EXE"
python -m pytest integration/test_office_real.py -k word -s
```

### Excel
```powershell
$env:HERMES_TEST_EXCEL_PROCESS="EXCEL.EXE"
$env:HERMES_TEST_EXCEL_SHEET="Sheet1"
python -m pytest integration/test_office_real.py -k excel -s
```

### PowerPoint
```powershell
$env:HERMES_TEST_POWERPOINT_PROCESS="POWERPNT.EXE"
python -m pytest integration/test_office_real.py -k powerpoint -s
```

What this validates:
- Word COM dispatch
- Excel COM dispatch
- PowerPoint COM dispatch

## 9. Run Everything Real
Only do this when your environment is fully prepared.

```powershell
python -m pytest integration -s
```

Or use the helper script:

```powershell
.\run_real_tests.ps1
```

## 10. Recommended Acceptance Checklist
- `run_shell` launches the target app.
- `get_desktop_app_info` finds the app window.
- `select_application_window` binds the window successfully.
- `capture_window_screenshot` returns a valid base64 image.
- `get_app_window_controls_target_info` returns at least one control for standard apps.
- for self-drawn or modernized apps, validate screenshot/UI tree first and prefer ZonUI-3B `find_control_on_screen`.
- `find_control_on_screen` returns a visual control target for self-drawn UIs.
- `list_controls_hybrid` returns the UIA-enumerated control list.
- `extract_pdf_text` returns non-empty text for a text PDF.
- Word/Excel/PowerPoint commands act on the intended document or workbook.

## 11. Known Limits
- UI automation can be flaky if the desktop focus changes during the test.
- Office COM tests require the target app to be installed and running.
- ZonUI-3B tests require a reachable service endpoint and stable model behavior.
- Some apps expose poor UIA trees; for those, use the ZonUI-3B path.
