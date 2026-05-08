from types import SimpleNamespace


class FakeRect:
    def __init__(self, left=0, top=0, right=100, bottom=100):
        self.left = left
        self.top = top
        self.right = right
        self.bottom = bottom

    def width(self):
        return self.right - self.left

    def height(self):
        return self.bottom - self.top


class FakeControl:
    def __init__(self, name="Control", control_type="Button", rect=None):
        self._name = name
        self._control_type = control_type
        self._rect = rect or FakeRect()
        self.element_info = SimpleNamespace(
            name=name,
            control_type=control_type,
            class_name=control_type,
        )

    def rectangle(self):
        return self._rect

    def window_text(self):
        return self._name

    def class_name(self):
        return self._control_type

    def is_enabled(self):
        return True

    def is_visible(self):
        return True

    def set_focus(self):
        return None
