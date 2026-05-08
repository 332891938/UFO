import os
import time
from typing import List, Optional

from conftest import call_tool, run_async
from success_artifact_utils import write_success_artifact
from window_launch_utils import close_test_window, launch_test_window


def _env_flag(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _find_window(windows: List[dict], keyword: str) -> Optional[dict]:
    keyword_l = (keyword or "").strip().lower()
    preferred_class = (os.environ.get("HERMES_TEST_WINDOW_CLASS_NAME", "Notepad") or "Notepad").strip()
    preferred_class_l = preferred_class.lower()
    exclude_substrings = [
        s.strip().lower()
        for s in (os.environ.get("HERMES_TEST_WINDOW_EXCLUDE", "notepad++|文件资源管理器") or "").split("|")
        if s.strip()
    ]
    exclude_class_names = {
        s.strip()
        for s in (os.environ.get("HERMES_TEST_WINDOW_EXCLUDE_CLASS", "CabinetWClass|Notepad++") or "").split("|")
        if s.strip()
    }

    best = None
    best_score = -10**9
    for item in windows:
        name = str(item.get("name") or "")
        class_name = str(item.get("class_name") or "")
        rect = item.get("rectangle") or {}
        try:
            area = int(rect.get("width", 0)) * int(rect.get("height", 0))
        except Exception:
            area = 0
        if area <= 0:
            continue
        if class_name in exclude_class_names:
            continue
        name_l = name.lower()
        if any(ex in name_l for ex in exclude_substrings):
            continue

        score = 0
        if keyword_l and keyword_l in name_l:
            score += 10
        if preferred_class and class_name.lower() == preferred_class_l:
            score += 100
        if preferred_class and name_l.endswith(f" - {preferred_class_l}"):
            score += 50
        if score > best_score:
            best_score = score
            best = item
    return best


def test_mcp_zonui3b_deep_flow_real(server_url):
    app_command = os.environ.get("HERMES_TEST_UI_APP", "notepad.exe").strip() or "notepad.exe"
    window_keyword = os.environ.get("HERMES_TEST_UI_WINDOW_KEYWORD", "Notepad").strip() or "Notepad"
    require_found = _env_flag("HERMES_TEST_REQUIRE_ZONUI3B_FOUND", "0")
    query = os.environ.get("HERMES_TEST_ZONUI3B_QUERY", "Save button").strip() or "Save button"

    windows, target_window, launched_handle = launch_test_window(
        server_url,
        app_command,
        lambda items: _find_window(items, window_keyword),
    )
    try:
        assert isinstance(windows, list)
        assert target_window is not None

        selected = run_async(
            call_tool(
                server_url,
                "select_application_window",
                {"id": target_window["id"], "name": target_window["name"]},
            )
        )
        assert isinstance(selected, dict)
        assert selected.get("success") is True

        screenshot = run_async(call_tool(server_url, "capture_window_screenshot", {}))
        assert isinstance(screenshot, str)
        assert screenshot.startswith("data:image/png;base64,")

        uia_targets = run_async(call_tool(server_url, "list_controls_hybrid", {"max_uia_controls": 200}))
        assert isinstance(uia_targets, list)

        candidates = [
            os.environ.get("HERMES_TEST_ZONUI3B_DESC", "").strip(),
            "File",
            "文件",
            "Edit",
            "编辑",
            "Help",
            "帮助",
        ]
        found = None
        for desc in [c for c in candidates if c]:
            found = run_async(
                call_tool(
                    server_url,
                    "find_control_on_screen",
                    {"description": desc, "element_type": "Button"},
                )
            )
            if found:
                break

        if require_found:
            assert found is not None

        parsed = run_async(call_tool(server_url, "parse_window_with_zonui3b", {"query": query}))
        assert isinstance(parsed, list)
    finally:
        close_test_window(launched_handle)
    write_success_artifact("test_mcp_zonui3b_deep_flow_real", server_url=server_url, query=query)
