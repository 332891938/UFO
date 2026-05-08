from conftest import require_env
from test_ui_real import _find_window


def test_real_omniparser_parse(real_service):
    endpoint = require_env("HERMES_OMNIPARSER_ENDPOINT")
    window_keyword = require_env("HERMES_TEST_UI_WINDOW_KEYWORD")

    window = _find_window(real_service, window_keyword)
    assert window is not None, f"Window containing '{window_keyword}' was not found."

    real_service.select_application_window(window["id"], window["name"])
    targets = real_service.parse_window_with_omniparser(
        endpoint=endpoint,
        inject_controls=False,
    )

    assert isinstance(targets, list)
    assert len(targets) >= 1


def test_real_hybrid_controls(real_service):
    endpoint = require_env("HERMES_OMNIPARSER_ENDPOINT")
    window_keyword = require_env("HERMES_TEST_UI_WINDOW_KEYWORD")

    window = _find_window(real_service, window_keyword)
    assert window is not None, f"Window containing '{window_keyword}' was not found."

    real_service.select_application_window(window["id"], window["name"])
    targets = real_service.list_controls_hybrid(endpoint=endpoint, max_uia_controls=200)

    assert isinstance(targets, list)
    assert len(targets) >= 1
