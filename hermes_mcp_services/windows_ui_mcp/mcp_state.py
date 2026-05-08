from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from pywinauto.controls.uiawrapper import UIAWrapper

from ufo.automator.action_execution import ActionExecutor
from ufo.automator.puppeteer import AppPuppeteer
from ufo.automator.ui_control.inspector import ControlInspectorFacade
from ufo.automator.ui_control.screenshot import PhotographerFacade

# Lazy import: ZonUI-3B requires torch+transformers (only available in WSL)
_ZonUI3BGrounding = None

def _get_zonui3b_grounding():
    global _ZonUI3BGrounding
    if _ZonUI3BGrounding is None:
        from ufo.automator.ui_control.grounding.zonui3b import ZonUI3BGrounding
        _ZonUI3BGrounding = ZonUI3BGrounding
    return _ZonUI3BGrounding


@dataclass
class WindowsUIState:
    photographer: Any = field(default_factory=PhotographerFacade)
    control_inspector: Any = field(
        default_factory=lambda: ControlInspectorFacade("uia")
    )
    executor: Any = field(default_factory=ActionExecutor)
    puppeteer: Optional[AppPuppeteer] = None
    grounding_service: Optional["ZonUI3BGrounding"] = None
    selected_window: Optional[UIAWrapper] = None
    selected_window_info: Dict[str, Any] = field(default_factory=dict)
    window_dict: Dict[str, Any] = field(default_factory=dict)
    control_dict: Dict[str, Any] = field(default_factory=dict)
