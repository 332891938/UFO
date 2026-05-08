import os
import time
from typing import List, Optional

from conftest import call_tool, run_async
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


def _center(rect: List[int]) -> tuple[float, float]:
    left, top, right, bottom = rect[:4]
    return (left + right) / 2.0, (top + bottom) / 2.0


def test_mcp_zonui3b_click_flow_real(server_url):
    app_command = os.environ.get("HERMES_TEST_UI_APP", "notepad.exe").strip() or "notepad.exe"
    window_keyword = os.environ.get("HERMES_TEST_UI_WINDOW_KEYWORD", "Notepad").strip() or "Notepad"
    require_found = _env_flag("HERMES_TEST_REQUIRE_ZONUI3B_FOUND", "0")
    require_visual_change = _env_flag("HERMES_TEST_REQUIRE_UI_CHANGED", "0")

    descriptions = [
        os.environ.get("HERMES_TEST_ZONUI3B_DESC", "").strip(),
        "File",
        "文件",
        "Edit",
        "编辑",
        "Help",
        "帮助",
    ]
    descriptions = [d for d in descriptions if d]

    windows, target_window, launched_handle = launch_test_window(
        server_url,
        app_command,
        lambda items: _find_window(items, window_keyword),
    )
    try:
        assert target_window is not None

        selected = run_async(
            call_tool(
                server_url,
                "select_application_window",
                {"id": target_window["id"], "name": target_window["name"]},
            )
        )
        assert selected.get("success") is True

        before = run_async(call_tool(server_url, "capture_window_screenshot", {}))
        assert isinstance(before, str)
        assert before.startswith("data:image/png;base64,")

        found = None
        for desc in descriptions:
            found = run_async(
                call_tool(
                    server_url,
                    "find_control_on_screen",
                    {"description": desc, "element_type": "Button"},
                )
            )
            if found:
                break

        if found is None:
            if require_found:
                raise AssertionError("ZonUI-3B did not find any target control.")
            return

        if isinstance(found, dict) and found.get("id"):
            run_async(
                call_tool(
                    server_url,
                    "click_control",
                    {"control_id": found["id"], "control_name": found.get("name", "")},
                )
            )
        elif isinstance(found, dict) and found.get("rect"):
            x, y = _center(found["rect"])
            run_async(call_tool(server_url, "click_on_coordinates", {"x": x, "y": y}))
        else:
            if require_found:
                raise AssertionError(f"Unexpected find_control_on_screen output: {found!r}")
            return

        time.sleep(0.3)
        after = run_async(call_tool(server_url, "capture_window_screenshot", {}))
        assert isinstance(after, str)
        assert after.startswith("data:image/png;base64,")
        if require_visual_change:
            assert after != before
    finally:
        close_test_window(launched_handle)
