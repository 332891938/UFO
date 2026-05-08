import time

from conftest import get_env_int, require_env


def _find_window(service, keyword: str):
    windows = service.get_desktop_app_info(remove_empty=True, refresh_app_windows=True)
    keyword = keyword.lower()
    for item in windows:
        if keyword in (item.get("name") or "").lower():
            return item
    return None


def test_notepad_window_discovery_and_capture(real_service):
    app_command = require_env("HERMES_TEST_UI_APP")
    window_keyword = require_env("HERMES_TEST_UI_WINDOW_KEYWORD")

    real_service.run_shell(app_command)
    time.sleep(2)

    window = _find_window(real_service, window_keyword)
    assert window is not None, f"Window containing '{window_keyword}' was not found."

    selected = real_service.select_application_window(window["id"], window["name"])
    assert selected["success"] is True

    screenshot = real_service.capture_window_screenshot()
    assert screenshot.startswith("data:image/png;base64,")

    tree = real_service.get_ui_tree()
    assert isinstance(tree, dict)
    assert tree


def test_real_controls_listing(real_service):
    window_keyword = require_env("HERMES_TEST_UI_WINDOW_KEYWORD")
    min_controls = get_env_int("HERMES_TEST_MIN_CONTROLS", 0)
    window = _find_window(real_service, window_keyword)
    if window is None:
        raise AssertionError(f"Window containing '{window_keyword}' was not found.")

    real_service.select_application_window(window["id"], window["name"])
    controls = real_service.get_app_window_controls_target_info([], max_controls=200)
    tree = real_service.get_ui_tree()

    assert isinstance(controls, list)
    assert isinstance(tree, dict)
    assert tree
    assert len(controls) >= min_controls
