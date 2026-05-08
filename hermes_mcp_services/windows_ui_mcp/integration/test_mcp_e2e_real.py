import time

from conftest import call_tool, require_env, run_async


def _find_window(windows: list[dict], keyword: str):
    keyword = keyword.lower()
    for item in windows:
        if keyword in (item.get("name") or "").lower():
            return item
    return None


def test_mcp_server_lists_tools(server_url):
    data = run_async(call_tool(server_url, "summary", {"text": "ping"}))
    assert data == "ping"


def test_mcp_ui_flow_real(server_url):
    app_command = require_env("HERMES_TEST_UI_APP")
    window_keyword = require_env("HERMES_TEST_UI_WINDOW_KEYWORD")

    run_async(call_tool(server_url, "run_shell", {"bash_command": app_command}))
    time.sleep(2)

    windows = run_async(
        call_tool(
            server_url,
            "get_desktop_app_info",
            {"remove_empty": True, "refresh_app_windows": True},
        )
    )
    target_window = _find_window(windows, window_keyword)
    assert target_window is not None, f"Window containing '{window_keyword}' was not found."

    selected = run_async(
        call_tool(
            server_url,
            "select_application_window",
            {"id": target_window["id"], "name": target_window["name"]},
        )
    )
    assert selected["success"] is True

    screenshot = run_async(call_tool(server_url, "capture_window_screenshot", {}))
    assert isinstance(screenshot, str)
    assert screenshot.startswith("data:image/png;base64,")


def test_mcp_pdf_flow_real(server_url):
    pdf_path = require_env("HERMES_TEST_PDF_PATH")

    text = run_async(
        call_tool(
            server_url,
            "extract_pdf_text",
            {"pdf_path": pdf_path, "simulate_human": False},
        )
    )

    assert isinstance(text, str)
    assert text != ""


def test_mcp_omniparser_flow_real(server_url):
    endpoint = require_env("HERMES_OMNIPARSER_ENDPOINT")
    window_keyword = require_env("HERMES_TEST_UI_WINDOW_KEYWORD")

    windows = run_async(
        call_tool(
            server_url,
            "get_desktop_app_info",
            {"remove_empty": True, "refresh_app_windows": True},
        )
    )
    target_window = _find_window(windows, window_keyword)
    assert target_window is not None, f"Window containing '{window_keyword}' was not found."

    run_async(
        call_tool(
            server_url,
            "select_application_window",
            {"id": target_window["id"], "name": target_window["name"]},
        )
    )
    targets = run_async(
        call_tool(
            server_url,
            "parse_window_with_omniparser",
            {"endpoint": endpoint, "inject_controls": False},
        )
    )

    assert isinstance(targets, list)
    assert len(targets) >= 1
