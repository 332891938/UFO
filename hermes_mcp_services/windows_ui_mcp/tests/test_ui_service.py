from test_support import FakeControl, FakeRect


def test_get_desktop_app_info_refreshes_cache(service, fake_state):
    window = FakeControl(name="Calculator", control_type="Window")
    window.element_info.class_name = "CalcWindow"
    fake_state.control_inspector.get_desktop_app_dict.return_value = {"1": window}

    result = service.get_desktop_app_info(remove_empty=True, refresh_app_windows=True)

    assert result[0]["id"] == "1"
    assert result[0]["name"] == "Calculator"
    fake_state.control_inspector.get_desktop_app_dict.assert_called_once_with(
        remove_empty=True
    )


def test_select_application_window_initializes_selection(service, fake_state, monkeypatch):
    window = FakeControl(name="Notepad", control_type="Window")
    fake_state.window_dict = {"7": window}
    marker = {}
    monkeypatch.setattr(
        service,
        "_initialize_puppeteer_for_window",
        lambda selected: marker.setdefault("window", selected),
    )

    result = service.select_application_window("7", "Notepad")

    assert result["success"] is True
    assert fake_state.selected_window is window
    assert fake_state.control_dict == {}
    assert marker["window"] is window


def test_get_app_window_controls_info_updates_control_cache(service, fake_state):
    window = FakeControl(name="Main", control_type="Window")
    child1 = FakeControl(name="Open")
    child2 = FakeControl(name="Save")
    fake_state.selected_window = window
    fake_state.control_inspector.find_control_elements_in_descendants.return_value = [
        child1,
        child2,
    ]
    fake_state.control_inspector.get_control_info_list_of_dict.return_value = [
        {"id": "1"},
        {"id": "2"},
    ]

    result = service.get_app_window_controls_info(["control_text"], max_controls=10)

    assert result == [{"id": "1"}, {"id": "2"}]
    assert fake_state.control_dict == {"1": child1, "2": child2}


def test_add_control_list_assigns_incremental_ids(service, fake_state, monkeypatch):
    fake_state.selected_window = FakeControl(name="Window", control_type="Window")
    fake_state.control_dict = {"3": FakeControl(name="Existing")}
    monkeypatch.setattr(
        "mcp_service.BasicGrounding.uia_wrapping",
        lambda payload: {"wrapped": payload["name"]},
    )

    message = service.add_control_list(
        [{"name": "Visual A", "type": "Button", "rect": [1, 2, 3, 4]}]
    )

    assert "Successfully added 1 controls" in message
    assert "4" in fake_state.control_dict
    assert fake_state.control_dict["4"] == {"wrapped": "Visual A"}


def test_click_input_delegates_to_executor(service, fake_state, monkeypatch):
    control = FakeControl(name="Submit")
    fake_state.control_dict = {"1": control}
    fake_state.selected_window = FakeControl(name="Window", control_type="Window")
    fake_state.puppeteer = object()
    captured = {}

    def fake_execute(function, arguments, target_id=None, target_name=""):
        captured["function"] = function
        captured["arguments"] = arguments
        captured["target_id"] = target_id
        captured["target_name"] = target_name
        return "ok"

    monkeypatch.setattr(service, "_execute_ui_action", fake_execute)

    result = service.click_input("1", "Submit", button="right", double=True)

    assert "Executed click_input on control 1:Submit" in result
    assert captured == {
        "function": "click_input",
        "arguments": {"button": "right", "double": True},
        "target_id": "1",
        "target_name": "Submit",
    }


def test_capture_window_screenshot_uses_photographer(service, fake_state):
    fake_state.selected_window = FakeControl(name="Window", control_type="Window")
    fake_state.photographer.capture_app_window_screenshot.return_value = "image"
    fake_state.photographer.encode_image.return_value = "encoded"

    result = service.capture_window_screenshot()

    assert result == "encoded"
    fake_state.photographer.capture_app_window_screenshot.assert_called_once()
    fake_state.photographer.encode_image.assert_called_once_with("image")
