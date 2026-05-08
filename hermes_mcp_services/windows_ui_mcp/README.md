# Windows UI MCP Service

Standalone Windows UI automation MCP server extracted for Hermes integration.
This project now vendors a local `ufo/automator` runtime and routes UI / Office actions through that automator layer.

## Structure
- `server.py`: thin startup entrypoint.
- `mcp_app.py`: FastMCP registration layer.
- `mcp_service.py`: core business logic, grouped by UI / vision / CLI / PDF / Office.
- `mcp_state.py`: shared runtime state.
- `mcp_models.py`: local response models.
- `tests/`: unit tests with mocks for UIA, Office, PDF, CLI, and OmniParser paths.

## Features
### UI
- `get_desktop_app_info`
- `get_desktop_app_target_info`
- `select_application_window`
- `get_app_window_info`
- `get_app_window_controls_info`
- `get_app_window_controls_target_info`
- `capture_window_screenshot`
- `capture_desktop_screenshot`
- `get_ui_tree`
- `add_control_list`
- `click_input`
- `click_control`
- `click_on_coordinates`
- `drag_on_coordinates`
- `set_edit_text`
- `keyboard_input`
- `wheel_mouse_input`
- `texts`
- `wait`
- `summary`

### Vision
- `parse_window_with_omniparser`
- `inject_omniparser_controls`
- `list_controls_hybrid`

### CLI
- `run_shell`

### PDF
- `extract_pdf_text`
- `list_pdfs_in_directory`
- `extract_all_pdfs_text`

### Word COM
- `word_insert_table`
- `word_select_text`
- `word_select_table`
- `word_select_paragraph`
- `word_save_as`
- `word_set_font`

### Excel COM
- `excel_table2markdown`
- `excel_insert_table`
- `excel_select_table_range`
- `excel_save_as`
- `excel_reorder_columns`
- `excel_get_range_values`

### PowerPoint COM
- `powerpoint_set_background_color`
- `powerpoint_save_as`

## Setup (PowerShell)
```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Test
```powershell
pytest
```

For real desktop validation, see [REAL_TESTING.md](file:///d:/open-source/UFO/hermes_mcp_services/windows_ui_mcp/REAL_TESTING.md).
- `tests/` are development regression tests and may use mocks.
- `integration/` is the real acceptance path and should be used to validate the final MCP server behavior.

## Run
```powershell
python server.py --host localhost --port 8030
```

## Notes
- Windows only.
- Derived from the capabilities exposed by UFO `client/mcp/local_servers/ui_mcp_server.py`.
- Also absorbs Windows-side capabilities from `cli_mcp_server.py`, `pdf_reader_mcp_server.py`, and the Office COM MCP servers.
- Bundles a local `ufo/automator` copy so the service can be copied out and run independently.
- Uses `pywinauto` and `pyautogui` for UI automation.
- OmniParser tools require a reachable Gradio endpoint; pass `endpoint` or set `HERMES_OMNIPARSER_ENDPOINT`.
- Word / Excel / PowerPoint tools require Microsoft Office installed and an open target document/workbook/presentation.
