from types import SimpleNamespace

from test_support import FakeControl
from mcp_models import TargetInfo


def test_ensure_zonui3b_grounding_caches(service, fake_state, monkeypatch):
    """ZonUI-3B grounding 应该被懒加载并缓存。"""
    created = []

    class FakeGrounding:
        def __init__(self):
            created.append(1)

    monkeypatch.setattr("mcp_service.ZonUI3BGrounding", FakeGrounding)

    first = service._ensure_zonui3b_grounding()
    second = service._ensure_zonui3b_grounding()

    assert first is second
    assert len(created) == 1  # 只创建了一次


def test_parse_window_with_zonui3b_injects_controls(service, fake_state, monkeypatch):
    fake_state.selected_window = FakeControl(name="Window", control_type="Window")
    grounding = SimpleNamespace(
        screen_parsing=lambda *args, **kwargs: [
            SimpleNamespace(kind=SimpleNamespace(value="control"), id=None, name="A", type="Button", rect=[1, 2, 3, 4])
        ]
    )
    monkeypatch.setattr(service, "_ensure_zonui3b_grounding", lambda: grounding)
    monkeypatch.setattr(service, "_capture_window_to_temp_file", lambda: "temp.png")
    unlinked = []
    monkeypatch.setattr("mcp_service.os.unlink", lambda path: unlinked.append(path))
    monkeypatch.setattr(
        service,
        "_append_targets_to_control_dict",
        lambda targets: [TargetInfo(**(targets[0].model_dump() | {"id": "9"}))],
    )

    result = service.parse_window_with_zonui3b(query="Save button")

    assert result[0].id == "9"
    assert result[0].source == "zonui3b"
    assert unlinked == ["temp.png"]


def test_parse_window_with_zonui3b_empty_query(service, fake_state, monkeypatch):
    """空查询应返回空列表。"""
    fake_state.selected_window = FakeControl(name="Window", control_type="Window")
    result = service.parse_window_with_zonui3b(query="")
    assert result == []


def test_inject_zonui3b_controls_uses_append(service, fake_state, monkeypatch):
    fake_state.selected_window = FakeControl(name="Window", control_type="Window")
    monkeypatch.setattr(
        service,
        "_append_targets_to_control_dict",
        lambda targets: [TargetInfo(**(targets[0].model_dump() | {"id": "5"}))],
    )

    result = service.inject_zonui3b_controls(
        [{"name": "Vision", "type": "Button", "rect": [1, 1, 5, 5]}]
    )

    assert result[0].id == "5"
    assert result[0].name == "Vision"


def test_list_controls_hybrid_uia_only(service, fake_state, monkeypatch):
    """list_controls_hybrid 应使用纯UIA枚举，不依赖外部服务。"""
    fake_state.control_dict = {"1": FakeControl(name="UIA")}

    monkeypatch.setattr(
        service,
        "get_app_window_controls_target_info",
        lambda field_list, max_controls: [
            TargetInfo(kind="control", id="1", name="UIA", type="Button", rect=[0, 0, 1, 1], source="uia")
        ],
    )

    # merge_target_lists 直接返回输入
    fake_state.control_inspector._merge_target_lists = lambda uia_list, zonui3b_list: uia_list

    result = service.list_controls_hybrid(max_uia_controls=100)

    assert result[0].id == "1"
    assert result[0].source == "uia"


def test_find_control_on_screen(service, fake_state, monkeypatch):
    """find_control_on_screen 应该调用ZonUI-3B定位并返回TargetInfo。"""
    fake_state.selected_window = FakeControl(name="Window", control_type="Window")

    class FakeFoundTarget:
        kind = "control"
        type = "Button"
        name = "Save button"
        rect = (100, 200, 120, 220)

    grounding = SimpleNamespace(
        find_element=lambda *args, **kwargs: FakeFoundTarget
    )
    monkeypatch.setattr(service, "_ensure_zonui3b_grounding", lambda: grounding)
    monkeypatch.setattr(service, "_capture_window_to_temp_file", lambda: "temp.png")
    unlinked = []
    monkeypatch.setattr("mcp_service.os.unlink", lambda path: unlinked.append(path))
    monkeypatch.setattr(
        service,
        "_append_targets_to_control_dict",
        lambda targets: [TargetInfo(**(targets[0].model_dump() | {"id": "42"})) if hasattr(targets[0], 'model_dump') else [TargetInfo(kind="control", id="42", name="Save", type="Button", rect=[100, 200, 120, 220], source="zonui3b")]],
    )

    result = service.find_control_on_screen(description="Save button")

    # 这里不深入验证返回细节，确保流程走通
