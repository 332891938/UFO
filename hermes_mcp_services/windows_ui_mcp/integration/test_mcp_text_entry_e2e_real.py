import os
import time
from typing import List, Optional, Tuple

import pytest

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


def _area(rect: List[int]) -> int:
    if not rect or len(rect) < 4:
        return 0
    left, top, right, bottom = rect[:4]
    return max(0, right - left) * max(0, bottom - top)


def _pick_text_control(controls: List[dict]) -> Optional[dict]:
    candidates: List[Tuple[int, int, dict]] = []
    for idx, item in enumerate(controls):
        ctype = str(item.get("type") or "").lower()
        rect = item.get("rect") or [0, 0, 0, 0]
        score = 0
        if ctype in {"edit", "document"}:
            score += 100
        if ctype in {"pane", "text"}:
            score += 10
        score += min(50, _area(rect) // 5000)
        candidates.append((score, idx, item))
    if not candidates:
        return None
    candidates.sort(key=lambda t: (t[0], -t[1]), reverse=True)
    return candidates[0][2]


def test_mcp_text_entry_flow_real(server_url):
    require_text_entry = _env_flag("HERMES_TEST_REQUIRE_TEXT_ENTRY", "0")
    require_text_readback = _env_flag("HERMES_TEST_REQUIRE_TEXT_READBACK", "0")
    require_visual_change = _env_flag("HERMES_TEST_REQUIRE_UI_CHANGED", "0")

    app_command = os.environ.get("HERMES_TEST_UI_APP", "notepad.exe").strip() or "notepad.exe"
    window_keyword = os.environ.get("HERMES_TEST_UI_WINDOW_KEYWORD", "Notepad").strip() or "Notepad"
    text = os.environ.get("HERMES_TEST_TEXT", "").strip() or f"hello-zonui3b-{int(time.time())}"

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

        before = run_async(call_tool(server_url, "capture_window_screenshot", {}))
        assert isinstance(before, str)
        assert before.startswith("data:image/png;base64,")

        controls = run_async(
            call_tool(server_url, "get_app_window_controls_target_info", {"field_list": [], "max_controls": 500})
        )
        assert isinstance(controls, list)
        control = _pick_text_control(controls)
        if control is None:
            if require_text_entry:
                raise AssertionError("No candidate text control found via UIA.")
            pytest.skip("No candidate text control found; skipping text entry test.")

        control_id = str(control.get("id") or "")
        control_name = str(control.get("name") or "")
        if not control_id:
            if require_text_entry:
                raise AssertionError(f"Invalid control id: {control!r}")
            pytest.skip("Invalid control id; skipping text entry test.")

        run_async(call_tool(server_url, "click_input", {"id": control_id, "name": control_name}))
        run_async(
            call_tool(
                server_url,
                "set_edit_text",
                {"id": control_id, "name": control_name, "text": text, "clear_current_text": True},
            )
        )
        time.sleep(0.3)

        after = run_async(call_tool(server_url, "capture_window_screenshot", {}))
        assert isinstance(after, str)
        assert after.startswith("data:image/png;base64,")
        if require_visual_change:
            assert after != before

        try:
            readback = run_async(call_tool(server_url, "texts", {"id": control_id, "name": control_name}))
        except Exception:
            readback = ""

        if require_text_readback:
            assert isinstance(readback, str)
            assert text in readback
    finally:
        close_test_window(launched_handle)
