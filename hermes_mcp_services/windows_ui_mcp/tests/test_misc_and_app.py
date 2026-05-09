import asyncio

import pytest

from mcp_app import register_tools


class FakeMCP:
    def __init__(self):
        self.names = []
        self.funcs = {}

    def tool(self):
        def decorator(func):
            self.names.append(func.__name__)
            self.funcs[func.__name__] = func
            return func

        return decorator


def test_wait_and_summary(service, monkeypatch):
    waited = []
    async def fake_sleep(seconds):
        waited.append(seconds)

    monkeypatch.setattr("mcp_service.asyncio.sleep", fake_sleep)

    result = asyncio.run(service.wait(0.25))

    assert result == "Successfully waited for 0.25 second(s)"
    assert waited == [0.25]
    assert service.summary("done") == "done"


def test_wait_rejects_invalid_values(service):
    with pytest.raises(ValueError):
        asyncio.run(service.wait(-1))


def test_register_tools_exposes_core_methods(service):
    fake_mcp = FakeMCP()

    register_tools(fake_mcp, service)

    expected = {
        "get_desktop_app_info",
        "parse_window_with_zonui3b",
        "run_shell",
        "extract_pdf_text",
        "word_insert_table",
        "excel_get_range_values",
        "powerpoint_save_as",
    }
    assert expected.issubset(set(fake_mcp.names))


def test_find_control_on_screen_tool_serializes_targetinfo(service, monkeypatch):
    fake_mcp = FakeMCP()
    register_tools(fake_mcp, service)

    class DummyTarget:
        def model_dump(self):
            return {"id": "9", "name": "File", "type": "Button", "kind": "control"}

    monkeypatch.setattr(service, "find_control_on_screen", lambda description, element_type: DummyTarget())

    result = asyncio.run(fake_mcp.funcs["find_control_on_screen"]("File", "Button"))

    assert result == {"id": "9", "name": "File", "type": "Button", "kind": "control"}


def test_capture_window_screenshot_tool_passes_output_options(service, monkeypatch):
    fake_mcp = FakeMCP()
    register_tools(fake_mcp, service)
    captured = {}

    def fake_capture(output_mode="data_url", save_path=""):
        captured["output_mode"] = output_mode
        captured["save_path"] = save_path
        return "C:\\temp\\shot.png"

    monkeypatch.setattr(service, "capture_window_screenshot", fake_capture)

    result = fake_mcp.funcs["capture_window_screenshot"](
        output_mode="file_path",
        save_path="C:\\temp\\shot.png",
    )

    assert result == "C:\\temp\\shot.png"
    assert captured == {
        "output_mode": "file_path",
        "save_path": "C:\\temp\\shot.png",
    }


def test_capture_desktop_screenshot_tool_passes_output_options(service, monkeypatch):
    fake_mcp = FakeMCP()
    register_tools(fake_mcp, service)
    captured = {}

    def fake_capture(all_screens=True, output_mode="data_url", save_path=""):
        captured["all_screens"] = all_screens
        captured["output_mode"] = output_mode
        captured["save_path"] = save_path
        return "C:\\temp\\desktop.png"

    monkeypatch.setattr(service, "capture_desktop_screenshot", fake_capture)

    result = fake_mcp.funcs["capture_desktop_screenshot"](
        all_screens=False,
        output_mode="file_path",
        save_path="C:\\temp\\desktop.png",
    )

    assert result == "C:\\temp\\desktop.png"
    assert captured == {
        "all_screens": False,
        "output_mode": "file_path",
        "save_path": "C:\\temp\\desktop.png",
    }
