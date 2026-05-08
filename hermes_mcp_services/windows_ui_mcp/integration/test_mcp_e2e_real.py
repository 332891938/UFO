import time

from conftest import call_tool, require_env, run_async
from success_artifact_utils import write_success_artifact
from window_launch_utils import close_test_window, launch_test_window


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

    windows, target_window, launched_handle = launch_test_window(
        server_url,
        app_command,
        lambda items: _find_window(items, window_keyword),
    )
    try:
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
    finally:
        close_test_window(launched_handle)
    write_success_artifact("test_mcp_ui_flow_real", server_url=server_url)


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
