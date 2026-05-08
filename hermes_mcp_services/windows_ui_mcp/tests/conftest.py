import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp_service import WindowsMCPService


@pytest.fixture()
def fake_state():
    inspector = MagicMock()
    photographer = MagicMock()
    executor = MagicMock()
    return SimpleNamespace(
        photographer=photographer,
        control_inspector=inspector,
        executor=executor,
        puppeteer=None,
        grounding_service=None,
        selected_window=None,
        window_dict={},
        control_dict={},
    )


@pytest.fixture()
def service(fake_state):
    return WindowsMCPService(state=fake_state)
