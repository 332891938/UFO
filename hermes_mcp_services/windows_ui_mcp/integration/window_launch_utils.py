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


def launch_test_window(
    server_url: str,
    app_command: str,
    picker: WindowPicker,
    launch_wait_seconds: float = 2.0,
) -> tuple[list[dict], Optional[dict], Optional[int]]:
    before = _desktop_snapshot()
    run_async(call_tool(server_url, "run_shell", {"bash_command": app_command}))
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
        if current_handles:
            new_handles = current_handles
        for handle in reversed(new_handles):
            launched_handle = handle
            handle_info = current_snapshot.get(handle) or after.get(handle)
            if not handle_info:
                continue
            target = _match_mcp_window(current_windows, handle_info, picker)
            if target is not None:
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
