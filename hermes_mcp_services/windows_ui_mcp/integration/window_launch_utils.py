import subprocess
import time
from typing import Any, Callable, Optional

from pywinauto import Application, Desktop

from conftest import call_tool, run_async


WindowPicker = Callable[[list[dict]], Optional[dict]]


def get_windows(server_url: str) -> list[dict]:
    windows = run_async(
        call_tool(
            server_url,
            "get_desktop_app_info",
            {"remove_empty": True, "refresh_app_windows": True},
        )
    )
    return windows if isinstance(windows, list) else []


def _rect_to_tuple(rect: dict[str, Any]) -> tuple[int, int, int, int]:
    try:
        x = int(rect.get("x", 0))
        y = int(rect.get("y", 0))
        width = int(rect.get("width", 0))
        height = int(rect.get("height", 0))
    except Exception:
        return (0, 0, 0, 0)
    return (x, y, width, height)


def _desktop_snapshot() -> dict[int, dict[str, Any]]:
    snapshot: dict[int, dict[str, Any]] = {}
    for window in Desktop(backend="win32").windows():
        try:
            if not window.is_visible():
                continue
            rect = window.rectangle()
            snapshot[int(window.handle)] = {
                "name": window.window_text() or "",
                "class_name": getattr(window.element_info, "class_name", "") or "",
                "rectangle": (rect.left, rect.top, rect.width(), rect.height()),
            }
        except Exception:
            continue
    return snapshot


def _match_mcp_window(
    windows: list[dict], handle_info: dict[str, Any], picker: WindowPicker
) -> Optional[dict]:
    matches = []
    for item in windows:
        rect = _rect_to_tuple(item.get("rectangle") or {})
        if (
            str(item.get("name") or "") == str(handle_info.get("name") or "")
            and str(item.get("class_name") or "") == str(handle_info.get("class_name") or "")
            and rect == tuple(handle_info.get("rectangle") or ())
        ):
            matches.append(item)
    if matches:
        picked = picker(matches)
        return picked or matches[0]
    return None


def _best_handle_match(
    windows: list[dict],
    handles: list[int],
    current_snapshot: dict[int, dict[str, Any]],
    fallback_snapshot: dict[int, dict[str, Any]],
    picker: WindowPicker,
) -> tuple[Optional[dict], Optional[int]]:
    for handle in reversed(handles):
        handle_info = current_snapshot.get(handle) or fallback_snapshot.get(handle)
        if not handle_info:
            continue
        target = _match_mcp_window(windows, handle_info, picker)
        if target is not None:
            return target, handle
    return None, None


def launch_test_window(
    server_url: str,
    app_command: str,
    picker: WindowPicker,
    launch_wait_seconds: float = 2.0,
) -> tuple[list[dict], Optional[dict], Optional[int]]:
    before_windows = get_windows(server_url)
    before_ids = {str(item.get("id") or "") for item in before_windows}
    before = _desktop_snapshot()
    subprocess.Popen(app_command, shell=True)
    time.sleep(launch_wait_seconds)

    windows = get_windows(server_url)
    after = _desktop_snapshot()

    new_handles = [handle for handle in after.keys() if handle not in before]
    target = None
    launched_handle = None
    deadline = time.time() + 5.0
    while time.time() < deadline and target is None:
        current_windows = get_windows(server_url)
        current_snapshot = _desktop_snapshot()
        current_handles = [
            handle for handle in current_snapshot.keys() if handle not in before
        ]
        new_mcp_windows = [
            item
            for item in current_windows
            if str(item.get("id") or "") and str(item.get("id") or "") not in before_ids
        ]
        if current_handles:
            new_handles = current_handles
        matched, matched_handle = _best_handle_match(
            current_windows,
            new_handles,
            current_snapshot,
            after,
            picker,
        )
        if matched is not None:
            target = matched
            launched_handle = matched_handle
            windows = current_windows
            break
        if new_mcp_windows:
            picked = picker(new_mcp_windows)
            if picked is not None:
                picked_name = str(picked.get("name") or "")
                picked_class = str(picked.get("class_name") or "")
                for handle in reversed(new_handles):
                    handle_info = current_snapshot.get(handle) or after.get(handle)
                    if not handle_info:
                        continue
                    if (
                        picked_name == str(handle_info.get("name") or "")
                        and picked_class == str(handle_info.get("class_name") or "")
                    ):
                        target = picked
                        launched_handle = handle
                        windows = current_windows
                        break
        if target is None:
            time.sleep(0.2)
    return windows, target, launched_handle


def _dismiss_notepad_save_dialog(timeout_seconds: float = 3.0) -> None:
    button_keywords = [
        "不保存",
        "don't save",
        "dont save",
        "don't_save",
        "don’t save",
    ]
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        for backend in ("uia", "win32"):
            try:
                desktop = Desktop(backend=backend)
                dialogs = desktop.windows()
            except Exception:
                continue
            for dialog in dialogs:
                try:
                    if not dialog.is_visible():
                        continue
                    buttons = dialog.descendants(control_type="Button")
                except Exception:
                    continue
                for button in buttons:
                    try:
                        text = (button.window_text() or "").strip()
                    except Exception:
                        continue
                    text_l = text.lower()
                    if any(keyword in text_l for keyword in button_keywords):
                        try:
                            button.click_input()
                            time.sleep(0.2)
                            return
                        except Exception:
                            try:
                                button.click()
                                time.sleep(0.2)
                                return
                            except Exception:
                                pass
        time.sleep(0.1)


def close_test_window(window_handle: Optional[int]) -> None:
    if not window_handle:
        return
    try:
        window = Application(backend="win32").connect(handle=window_handle).window(
            handle=window_handle
        )
    except Exception:
        return

    try:
        window.set_focus()
    except Exception:
        pass

    try:
        window.close()
    except Exception:
        try:
            window.type_keys("%{F4}")
        except Exception:
            return

    _dismiss_notepad_save_dialog()
