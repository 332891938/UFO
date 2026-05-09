import asyncio
import os
import random
import re
import shlex
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional

import pyautogui
import ufo.automator.app_apis.factory  # Registers AppPuppeteer API receiver factories.
from PIL import Image
from pywinauto.controls.uiawrapper import UIAWrapper

from mcp_models import RectInfo, TargetInfo
from mcp_state import WindowsUIState
from path_utils import validate_path_not_sensitive
from ufo.agents.processors.schemas.actions import ActionCommandInfo
from ufo.agents.processors.schemas.target import TargetInfo as AutomatorTargetInfo
from ufo.agents.processors.schemas.target import TargetKind
from ufo.automator.puppeteer import AppPuppeteer
from ufo.automator.ui_control import ui_tree as automator_ui_tree
from ufo.automator.ui_control.grounding.basic import BasicGrounding

# Lazy: ZonUI3BGrounding requires torch+transformers (WSL GPU). Module-level var allows test monkeypatching.
ZonUI3BGrounding = None


ALLOWED_CLI_COMMANDS: FrozenSet[str] = frozenset(
    {
        "notepad",
        "notepad.exe",
        "calc",
        "calc.exe",
        "mspaint",
        "mspaint.exe",
        "wordpad",
        "wordpad.exe",
        "explorer",
        "explorer.exe",
        "msedge",
        "msedge.exe",
        "chrome",
        "chrome.exe",
        "firefox",
        "firefox.exe",
        "winword",
        "winword.exe",
        "excel",
        "excel.exe",
        "powerpnt",
        "powerpnt.exe",
        "outlook",
        "outlook.exe",
        "onenote",
        "onenote.exe",
        "code",
        "code.exe",
    }
)

_DANGEROUS_CLI_PATTERNS: List[re.Pattern] = [
    re.compile(r"Invoke-Expression|IEX\b", re.IGNORECASE),
    re.compile(r"Invoke-WebRequest|IWR\b|Invoke-RestMethod|IRM\b", re.IGNORECASE),
    re.compile(r"Start-Process\b", re.IGNORECASE),
    re.compile(r"New-Object\s+.*Net\.WebClient", re.IGNORECASE),
    re.compile(r"DownloadString|DownloadFile", re.IGNORECASE),
    re.compile(r"\bAdd-Type\b", re.IGNORECASE),
    re.compile(r"\b(cmd|powershell|pwsh)(\.exe)?\s+[/-]", re.IGNORECASE),
    re.compile(r"[|;&`]\s*(bash|sh|cmd|powershell|pwsh)", re.IGNORECASE),
    re.compile(r"\bNew-Service\b|\bsc\.exe\b", re.IGNORECASE),
    re.compile(r"\breg(\.exe)?\s+(add|delete|import)", re.IGNORECASE),
    re.compile(r"\bschtasks(\.exe)?\b", re.IGNORECASE),
    re.compile(r"\bnet\s+(user|localgroup)\b", re.IGNORECASE),
    re.compile(r"\bSet-ExecutionPolicy\b", re.IGNORECASE),
    re.compile(r"\bRemove-Item\b.*-Recurse", re.IGNORECASE),
    re.compile(r"\brm\s+-rf\b", re.IGNORECASE),
    re.compile(r"[`$]\(", re.IGNORECASE),
    re.compile(r"\bcurl\b|\bwget\b", re.IGNORECASE),
    re.compile(r"\brdp\b|\bmstsc\b", re.IGNORECASE),
    re.compile(r">{1,2}\s*[/\\]", re.IGNORECASE),
]

DEFAULT_CONTROL_LIST: List[str] = [
    "Button",
    "Edit",
    "TabItem",
    "Document",
    "ListItem",
    "MenuItem",
    "ScrollBar",
    "TreeItem",
    "Hyperlink",
    "ComboBox",
    "RadioButton",
    "Spinner",
    "CheckBox",
    "Group",
    "Text",
]


class WindowsMCPService:
    def __init__(self, state: Optional[WindowsUIState] = None):
        self.state = state or WindowsUIState()

    @staticmethod
    def _to_rect(control: Any) -> List[int]:
        rect = control.rectangle()
        return [rect.left, rect.top, rect.right, rect.bottom]

    @classmethod
    def _rect_info(cls, control: Any) -> RectInfo:
        rect = control.rectangle()
        return RectInfo(x=rect.left, y=rect.top, width=rect.width(), height=rect.height())

    @staticmethod
    def _window_name(window: Any) -> str:
        try:
            return window.window_text() or window.element_info.name or ""
        except Exception:
            return ""

    @staticmethod
    def _control_name(control: Any) -> str:
        try:
            return control.element_info.name or control.window_text() or ""
        except Exception:
            return ""

    @staticmethod
    def _control_type(control: Any) -> str:
        try:
            return control.element_info.control_type or control.class_name() or ""
        except Exception:
            try:
                return control.class_name() or ""
            except Exception:
                return ""

    @staticmethod
    def _normalize_text_output(value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, (list, tuple)):
            return "\n".join(str(item) for item in value)
        return str(value or "")

    @staticmethod
    def _window_class_name(window: Any) -> str:
        try:
            return getattr(window.element_info, "class_name", "") or ""
        except Exception:
            try:
                return window.class_name() or ""
            except Exception:
                return ""

    @staticmethod
    def _resolve_screenshot_save_path(save_path: str = "") -> str:
        if not save_path:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            temp_file.close()
            return temp_file.name

        resolved = Path(save_path).expanduser().resolve()
        target = resolved
        if not resolved.suffix:
            validate_path_not_sensitive(str(resolved))
            resolved.mkdir(parents=True, exist_ok=True)
            target = resolved / f"screenshot_{int(time.time() * 1000)}.png"
        else:
            validate_path_not_sensitive(str(resolved.parent))
            resolved.parent.mkdir(parents=True, exist_ok=True)

        if target.suffix.lower() != ".png":
            raise ValueError("Screenshot save_path must end with .png")
        return str(target)

    def _format_screenshot_result(
        self, screenshot: Any, output_mode: str = "data_url", save_path: str = ""
    ) -> str:
        mode = (output_mode or "data_url").strip().lower()
        if mode == "data_url":
            return self.state.photographer.encode_image(screenshot)
        if mode == "file_path":
            path = self._resolve_screenshot_save_path(save_path)
            screenshot.save(path, format="PNG")
            return path
        raise ValueError("output_mode must be 'data_url' or 'file_path'")

    def _selected_window_required(self) -> Any:
        if getattr(self.state, "selected_window_info", {}):
            refreshed = self._resolve_selected_window()
            if refreshed is not None:
                self.state.selected_window = refreshed
        if self.state.selected_window is None:
            raise ValueError(
                "No selected window. Please call select_application_window first."
            )
        return self.state.selected_window

    def _resolve_selected_window(self) -> Any:
        info = getattr(self.state, "selected_window_info", {}) or {}
        if not info:
            return self.state.selected_window

        selected_name = str(info.get("name") or info.get("title") or "")
        selected_title = str(info.get("title") or info.get("name") or "")
        selected_class = str(info.get("class_name") or "")

        try:
            self.state.window_dict = self.state.control_inspector.get_desktop_app_dict(
                remove_empty=False
            )
        except Exception:
            return self.state.selected_window

        best_window = None
        best_score = -1
        for _, window in self.state.window_dict.items():
            name = self._window_name(window)
            title = name
            class_name = self._window_class_name(window)
            score = 0
            if selected_class and class_name == selected_class:
                score += 100
            if selected_name and name == selected_name:
                score += 100
            if selected_title and title == selected_title:
                score += 100
            if selected_name and selected_name in name:
                score += 10
            if score > best_score:
                best_score = score
                best_window = window

        if best_window is not None and best_score > 0:
            return best_window
        return self.state.selected_window

    @staticmethod
    def _verify_name(actual_name: str, requested_name: str) -> Optional[str]:
        if actual_name != requested_name:
            return (
                f"Name mismatch: expected '{requested_name}', actual '{actual_name}'. "
                "The action is executed by id."
            )
        return None

    def _control_required(self, control_id: str) -> Any:
        control = self.state.control_dict.get(control_id)
        if control is None:
            raise ValueError(f"Control id '{control_id}' not found.")
        return control

    def _looks_like_placeholder_readback(
        self, text: str, control: Any, requested_name: str
    ) -> bool:
        normalized = (text or "").strip()
        if not normalized:
            return True

        control_name = (self._control_name(control) or "").strip()
        requested_name = (requested_name or "").strip()
        candidates = {
            control_name,
            requested_name,
            f"['{control_name}']" if control_name else "",
            f'["{control_name}"]' if control_name else "",
            f"['{requested_name}']" if requested_name else "",
            f'["{requested_name}"]' if requested_name else "",
        }
        return normalized in {item for item in candidates if item}

    @staticmethod
    def _clipboard_get_text() -> str:
        import win32clipboard

        win32clipboard.OpenClipboard()
        try:
            try:
                data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            except TypeError:
                data = win32clipboard.GetClipboardData()
            return str(data or "")
        finally:
            win32clipboard.CloseClipboard()

    @staticmethod
    def _clipboard_set_text(text: str) -> None:
        import win32clipboard

        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text or "", win32clipboard.CF_UNICODETEXT)
        finally:
            win32clipboard.CloseClipboard()

    def _read_control_text_via_clipboard(self, control: Any) -> str:
        previous_clipboard: Optional[str]
        try:
            previous_clipboard = self._clipboard_get_text()
        except Exception:
            previous_clipboard = None

        try:
            self._clipboard_set_text("")
            control.set_focus()
            time.sleep(0.05)
            pyautogui.hotkey("ctrl", "a")
            time.sleep(0.05)
            pyautogui.hotkey("ctrl", "c")
            time.sleep(0.15)
            return self._clipboard_get_text().strip()
        finally:
            if previous_clipboard is not None:
                try:
                    self._clipboard_set_text(previous_clipboard)
                except Exception:
                    pass

    def _initialize_puppeteer_for_window(self, window: UIAWrapper) -> None:
        self.state.puppeteer = AppPuppeteer(
            process_name=window.window_text(),
            app_root_name=self.state.control_inspector.get_application_root_name(window),
        )

    def _execute_ui_action(
        self,
        function: str,
        arguments: Dict[str, Any],
        target_id: Optional[str] = None,
        target_name: str = "",
    ) -> Any:
        if self.state.puppeteer is None or self.state.selected_window is None:
            raise ValueError(
                "UI state not initialized. Please select an application window first."
            )

        target = None
        if target_id is not None:
            control = self.state.control_dict.get(target_id)
            rect = self._to_rect(control) if control is not None else None
            target = AutomatorTargetInfo(
                id=target_id,
                name=target_name,
                kind=TargetKind.CONTROL,
                type=self._control_type(control) if control is not None else None,
                rect=rect,
            )

        action = ActionCommandInfo(function=function, arguments=arguments, target=target)
        return self.state.executor.execute(
            action,
            self.state.puppeteer,
            self.state.control_dict or {},
            self.state.selected_window,
        )

    @staticmethod
    def _create_office_puppeteer(
        process_name: Optional[str], app_root_name: str
    ) -> AppPuppeteer:
        name = process_name or app_root_name
        puppeteer = AppPuppeteer(process_name=name, app_root_name=app_root_name)
        puppeteer.receiver_manager.create_api_receiver(
            app_root_name=app_root_name,
            process_name=name,
        )
        return puppeteer

    def _execute_office_command(
        self,
        app_root_name: str,
        function: str,
        arguments: Dict[str, Any],
        process_name: Optional[str] = None,
    ) -> Any:
        puppeteer = self._create_office_puppeteer(process_name, app_root_name)
        return puppeteer.execute_command(function, arguments)

    def _window_target(self) -> AutomatorTargetInfo:
        window = self._selected_window_required()
        return AutomatorTargetInfo(
            kind=TargetKind.WINDOW,
            id="window",
            name=self._window_name(window),
            type=self._control_type(window),
            rect=self._to_rect(window),
        )

    @staticmethod
    def _local_target_from_automator(
        target: AutomatorTargetInfo,
        target_id: Optional[str] = None,
        source: Optional[str] = None,
    ) -> TargetInfo:
        return TargetInfo(
            kind=target.kind.value if hasattr(target.kind, "value") else str(target.kind),
            id=target_id or getattr(target, "id", None),
            name=getattr(target, "name", ""),
            type=getattr(target, "type", None),
            rect=list(getattr(target, "rect", None) or []) or None,
            source=source,
        )

    @staticmethod
    def _control_info_from_target(target: TargetInfo) -> Dict[str, Any]:
        rect = target.rect or [0, 0, 0, 0]
        return {
            "control_type": target.type or "Button",
            "name": target.name or "",
            "x0": rect[0],
            "y0": rect[1],
            "x1": rect[2],
            "y1": rect[3],
        }

    def _ensure_zonui3b_grounding(self) -> "ZonUI3BGrounding":
        """Ensure ZonUI-3B grounding is initialized (lazy load)."""
        global ZonUI3BGrounding
        if self.state.grounding_service is None:
            if ZonUI3BGrounding is None:
                from ufo.automator.ui_control.grounding.zonui3b import ZonUI3BGrounding as _ZG
                ZonUI3BGrounding = _ZG
            # Use HTTP service in WSL (has GPU), fallback to local
            service_url = os.environ.get("ZONUI3B_SERVICE_URL", "http://localhost:8100")
            self.state.grounding_service = ZonUI3BGrounding(service_url=service_url)
        return self.state.grounding_service

    def _capture_window_to_temp_file(self) -> str:
        window = self._selected_window_required()
        screenshot = self.state.photographer.capture_app_window_screenshot(window)
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        temp_file.close()
        screenshot.save(temp_file.name, format="PNG")
        return temp_file.name

    def _append_targets_to_control_dict(
        self, targets: List[TargetInfo]
    ) -> List[TargetInfo]:
        if self.state.control_dict is None:
            self.state.control_dict = {}

        existing_ids = [
            int(k) for k in self.state.control_dict.keys() if str(k).isdigit()
        ]
        next_id = max(existing_ids) + 1 if existing_ids else 1
        added_targets: List[TargetInfo] = []

        for target in targets:
            target_id = str(target.id or next_id)
            if target.id is None:
                next_id += 1
            self.state.control_dict[target_id] = BasicGrounding.uia_wrapping(
                self._control_info_from_target(target)
            )
            added_targets.append(
                TargetInfo(
                    kind=target.kind,
                    id=target_id,
                    name=target.name,
                    type=target.type,
                    rect=target.rect,
                    source=getattr(target, "source", None) or "uia",
                )
            )

        return added_targets

    @staticmethod
    def is_cli_command_allowed(command_str: str) -> bool:
        if not command_str or not command_str.strip():
            return False
        try:
            tokens = shlex.split(command_str)
        except ValueError:
            return False
        if not tokens:
            return False
        base = tokens[0].strip().lower()
        if not any(base == allowed.lower() for allowed in ALLOWED_CLI_COMMANDS):
            return False
        for pattern in _DANGEROUS_CLI_PATTERNS:
            if pattern.search(command_str):
                return False
        return True

    @staticmethod
    def extract_text_from_pdf(pdf_path: str, simulate_human: bool = True) -> str:
        import PyPDF2

        validate_path_not_sensitive(pdf_path)
        if simulate_human:
            try:
                os.startfile(pdf_path)
                time.sleep(random.uniform(2.0, 5.0))
            except Exception:
                pass
        with open(pdf_path, "rb") as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text_content = ""
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text()
                text_content += f"\n--- Page {page_num + 1} ---\n"
                text_content += page_text or ""
                if simulate_human and len(pdf_reader.pages) > 1:
                    time.sleep(random.uniform(0.5, 1.5))
        return text_content.strip()

    @staticmethod
    def get_pdf_files_in_directory(directory_path: str) -> List[str]:
        validate_path_not_sensitive(directory_path)
        directory = Path(directory_path)
        if not directory.exists():
            return []
        pdf_files = [
            str(file_path)
            for file_path in directory.iterdir()
            if file_path.is_file() and file_path.suffix.lower() == ".pdf"
        ]
        return sorted(pdf_files)

    @classmethod
    def extract_text_from_pdf_batch(
        cls, pdf_paths: List[str], simulate_human: bool = True
    ) -> Dict[str, str]:
        results = {}
        for i, pdf_path in enumerate(pdf_paths, 1):
            if simulate_human and i > 1:
                time.sleep(random.uniform(1.0, 3.0))
            results[os.path.basename(pdf_path)] = cls.extract_text_from_pdf(
                pdf_path, simulate_human
            )
        return results

    def _window_to_dict(self, window_id: str, window: Any) -> Dict[str, Any]:
        return {
            "id": window_id,
            "name": self._window_name(window),
            "title": self._window_name(window),
            "class_name": getattr(window.element_info, "class_name", ""),
            "control_type": self._control_type(window),
            "rectangle": self._rect_info(window).model_dump(),
            "kind": "window",
        }

    def get_desktop_app_info(
        self, remove_empty: bool = True, refresh_app_windows: bool = True
    ) -> List[Dict[str, Any]]:
        if refresh_app_windows or not self.state.window_dict:
            self.state.window_dict = self.state.control_inspector.get_desktop_app_dict(
                remove_empty=remove_empty
            )
        return [
            self._window_to_dict(window_id, win)
            for window_id, win in self.state.window_dict.items()
        ]

    def get_desktop_app_target_info(
        self, remove_empty: bool = True, refresh_app_windows: bool = True
    ) -> List[TargetInfo]:
        windows = self.get_desktop_app_info(remove_empty, refresh_app_windows)
        return [
            TargetInfo(
                id=item["id"],
                name=item["name"],
                type=item.get("control_type"),
                kind="window",
                source="uia",
            )
            for item in windows
        ]

    def select_application_window(self, id: str, name: str) -> Dict[str, Any]:
        window = self.state.window_dict.get(id)
        if window is None:
            return {"success": False, "error": f"Window id '{id}' not found."}
        warning = self._verify_name(self._window_name(window), name)
        try:
            window.set_focus()
        except Exception:
            pass
        self.state.selected_window = window
        setattr(self.state, "selected_window_info", self._window_to_dict(id, window))
        self.state.control_dict = {}
        self._initialize_puppeteer_for_window(window)
        result = {
            "success": True,
            "root_name": self._window_name(window),
            "window_info": self._window_to_dict(id, window),
        }
        if warning:
            result["warning"] = warning
        return result

    def get_app_window_info(self, field_list: List[str]) -> Dict[str, Any]:
        window = self._selected_window_required()
        return self.state.control_inspector.get_control_info(window, field_list=field_list)

    def get_app_window_controls_info(
        self, field_list: List[str], max_controls: int = 500
    ) -> List[Dict[str, Any]]:
        window = self._selected_window_required()
        controls_list = self.state.control_inspector.find_control_elements_in_descendants(
            window,
            control_type_list=DEFAULT_CONTROL_LIST,
            class_name_list=DEFAULT_CONTROL_LIST,
        )
        if max_controls > 0:
            controls_list = controls_list[:max_controls]
        self.state.control_dict = {
            str(i + 1): control for i, control in enumerate(controls_list)
        }
        return self.state.control_inspector.get_control_info_list_of_dict(
            self.state.control_dict, field_list=field_list
        )

    def get_app_window_controls_target_info(
        self, field_list: List[str], max_controls: int = 500
    ) -> List[TargetInfo]:
        _ = field_list
        self.get_app_window_controls_info(
            field_list=["control_text", "control_type", "control_rect"],
            max_controls=max_controls,
        )
        return [
            TargetInfo(
                kind="control",
                id=control_id,
                name=self._control_name(control),
                type=self._control_type(control),
                rect=self._to_rect(control),
                source="uia",
            )
            for control_id, control in self.state.control_dict.items()
        ]

    def capture_window_screenshot(
        self, output_mode: str = "data_url", save_path: str = ""
    ) -> str:
        window = self._selected_window_required()
        screenshot = self.state.photographer.capture_app_window_screenshot(window)
        return self._format_screenshot_result(screenshot, output_mode, save_path)

    def capture_desktop_screenshot(
        self,
        all_screens: bool = True,
        output_mode: str = "data_url",
        save_path: str = "",
    ) -> str:
        screenshot = self.state.photographer.capture_desktop_screen_screenshot(
            all_screens=all_screens
        )
        return self._format_screenshot_result(screenshot, output_mode, save_path)

    def get_ui_tree(self) -> Dict[str, Any]:
        window = self._selected_window_required()
        return automator_ui_tree.UITree(window).ui_tree

    def add_control_list(self, control_list: List[Dict[str, Any]]) -> str:
        self._selected_window_required()
        if not control_list:
            return "No controls to add."
        normalized_targets = [
            TargetInfo(
                kind=item.get("kind", "control"),
                id=item.get("id"),
                name=item.get("name", ""),
                type=item.get("type", "Button"),
                rect=item.get("rect") or [0, 0, 0, 0],
                source=item.get("source", "external"),
            )
            for item in control_list
        ]
        added_targets = self._append_targets_to_control_dict(normalized_targets)
        added_ids = [target.id for target in added_targets if target.id]
        return (
            f"Successfully added {len(added_ids)} controls. "
            f"Added IDs: {', '.join(added_ids)}"
        )

    def find_control_on_screen(
        self,
        description: str,
        element_type: str = "Button",
    ) -> Optional[TargetInfo]:
        """用ZonUI-3B视觉定位屏幕上的控件。

        这是ZonUI-3B的核心能力：截图+文字描述→坐标。

        Args:
            description: 要查找的UI元素描述，如 'Save button', '关闭按钮'
            element_type: 元素类型标签

        Returns:
            TargetInfo 或 None（未找到）
        """
        self._selected_window_required()
        grounding = self._ensure_zonui3b_grounding()
        screenshot_path = self._capture_window_to_temp_file()
        try:
            target = grounding.find_element(
                screenshot_path,
                description,
                self._window_target(),
                element_type=element_type,
            )
            if target is not None:
                local_target = self._local_target_from_automator(target, source="zonui3b")
                return self._append_targets_to_control_dict([local_target])[0]
            return None
        finally:
            try:
                os.unlink(screenshot_path)
            except OSError:
                pass

    def parse_window_with_zonui3b(
        self,
        query: str = "",
    ) -> List[TargetInfo]:
        """用ZonUI-3B解析窗口。

        仅做定点查找（给定query），不枚举全部控件。
        如需枚举，请使用 list_controls_hybrid（UIA+ZonUI-3B混合）。

        Args:
            query: 要查找的元素描述，为空则返回空列表

        Returns:
            TargetInfo列表（最多1个元素）
        """
        if not query:
            return []
        self._selected_window_required()
        grounding = self._ensure_zonui3b_grounding()
        screenshot_path = self._capture_window_to_temp_file()
        try:
            targets = grounding.screen_parsing(
                screenshot_path,
                self._window_target(),
                query=query,
            )
        finally:
            try:
                os.unlink(screenshot_path)
            except OSError:
                pass

        local_targets = [
            self._local_target_from_automator(target, source="zonui3b")
            for target in targets
        ]
        return self._append_targets_to_control_dict(local_targets)

    def inject_zonui3b_controls(
        self, control_list: List[Dict[str, Any]]
    ) -> List[TargetInfo]:
        self._selected_window_required()
        normalized_targets = [
            TargetInfo(
                kind=item.get("kind", "control"),
                id=item.get("id"),
                name=item.get("name", ""),
                type=item.get("type", "Button"),
                rect=item.get("rect") or [0, 0, 0, 0],
                source=item.get("source", "zonui3b"),
            )
            for item in control_list
        ]
        return self._append_targets_to_control_dict(normalized_targets)

    def list_controls_hybrid(
        self,
        max_uia_controls: int = 500,
    ) -> List[TargetInfo]:
        """列出窗口控件（纯UIA枚举，ZonUI-3B用于定点查找）。

        ZonUI-3B不做全屏枚举（那是OmniParser的活）。
        控件枚举由Windows UIA完成；ZonUI-3B通过
        find_control_on_screen()提供精准视觉定位。

        Args:
            max_uia_controls: UIA枚举的最大控件数

        Returns:
            TargetInfo列表
        """
        uia_targets = self.get_app_window_controls_target_info(
            field_list=[],
            max_controls=max_uia_controls,
        )
        # ZonUI-3B在当前方案中只负责定点查找，不参与全量枚举。
        return uia_targets

    def click_input(
        self, id: str, name: str, button: str = "left", double: bool = False
    ) -> str:
        control = self._control_required(id)
        warning = self._verify_name(self._control_name(control), name)
        self._execute_ui_action(
            "click_input",
            {"button": button, "double": double},
            target_id=id,
            target_name=name,
        )
        result = f"Executed click_input on control {id}:{self._control_name(control)}"
        return f"{warning} {result}".strip() if warning else result

    def click_control(
        self,
        control_id: str,
        control_name: str,
        button: str = "left",
        double: bool = False,
    ) -> Dict[str, Any]:
        message = self.click_input(
            id=control_id,
            name=control_name,
            button=button,
            double=double,
        )
        return {"success": True, "message": message}

    def click_on_coordinates(
        self, x: float, y: float, button: str = "left", double: bool = False
    ) -> str:
        return str(
            self._execute_ui_action(
                "click_on_coordinates",
                {"x": x, "y": y, "button": button, "double": double},
            )
        )

    def drag_on_coordinates(
        self,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        button: str = "left",
        duration: float = 1.0,
        key_hold: Optional[str] = None,
    ) -> str:
        return str(
            self._execute_ui_action(
                "drag_on_coordinates",
                {
                    "start_x": start_x,
                    "start_y": start_y,
                    "end_x": end_x,
                    "end_y": end_y,
                    "button": button,
                    "duration": duration,
                    "key_hold": key_hold,
                },
            )
        )

    def set_edit_text(
        self,
        id: str,
        name: str,
        text: str,
        clear_current_text: bool = False,
    ) -> str:
        control = self._control_required(id)
        warning = self._verify_name(self._control_name(control), name)
        self._execute_ui_action(
            "set_edit_text",
            {"text": text, "clear_current_text": clear_current_text},
            target_id=id,
            target_name=name,
        )
        result = f"Set text on control {id}:{self._control_name(control)}"
        return f"{warning} {result}".strip() if warning else result

    def keyboard_input(
        self, id: str, name: str, keys: str, control_focus: bool = True
    ) -> str:
        control = self._control_required(id)
        warning = self._verify_name(self._control_name(control), name)
        self._execute_ui_action(
            "keyboard_input",
            {"keys": keys, "control_focus": control_focus},
            target_id=id,
            target_name=name,
        )
        result = f"Sent keys to control {id}:{self._control_name(control)}"
        return f"{warning} {result}".strip() if warning else result

    def wheel_mouse_input(self, id: str, name: str, wheel_dist: int) -> str:
        control = self._control_required(id)
        warning = self._verify_name(self._control_name(control), name)
        self._execute_ui_action(
            "wheel_mouse_input",
            {"wheel_dist": wheel_dist},
            target_id=id,
            target_name=name,
        )
        result = f"Scrolled control {id}:{self._control_name(control)} by {wheel_dist}"
        return f"{warning} {result}".strip() if warning else result

    def texts(self, id: str, name: str) -> str:
        control = self._control_required(id)
        warning = self._verify_name(self._control_name(control), name)
        text = self._normalize_text_output(
            self._execute_ui_action("texts", {}, target_id=id, target_name=name) or ""
        )
        control_type = self._control_type(control).lower()
        if control_type in {"document", "edit"} and self._looks_like_placeholder_readback(
            text, control, name
        ):
            try:
                clipboard_text = self._read_control_text_via_clipboard(control)
            except Exception:
                clipboard_text = ""
            if clipboard_text:
                text = clipboard_text
        return f"{warning} {text}".strip() if warning else text

    async def wait(self, seconds: float) -> str:
        if seconds < 0:
            raise ValueError("Wait time must be a positive number.")
        if seconds > 300:
            raise ValueError("Wait time cannot exceed 300 seconds.")
        await asyncio.sleep(seconds)
        return f"Successfully waited for {seconds} second(s)"

    @staticmethod
    def summary(text: str) -> str:
        return text

    def run_shell(self, bash_command: str) -> str:
        if not bash_command:
            raise ValueError("Bash command cannot be empty.")
        if not self.is_cli_command_allowed(bash_command):
            raise ValueError(
                "Command blocked by security policy. Only allow-listed applications may be launched."
            )
        # Use os.startfile for Windows Shell resolution (handles PATH correctly from WSL)
        os.startfile(bash_command)
        time.sleep(2)
        return f"Launched command: {bash_command}"

    def extract_pdf_text(self, pdf_path: str, simulate_human: bool = True) -> str:
        if not os.path.exists(pdf_path):
            return f"Error: PDF file not found at {pdf_path}"
        if not pdf_path.lower().endswith(".pdf"):
            return f"Error: File {pdf_path} is not a PDF file"
        return self.extract_text_from_pdf(pdf_path, simulate_human)

    def list_pdfs_in_directory(self, directory_path: str) -> List[str]:
        if not os.path.exists(directory_path) or not os.path.isdir(directory_path):
            return []
        return self.get_pdf_files_in_directory(directory_path)

    def extract_all_pdfs_text(
        self, directory_path: str, simulate_human: bool = True
    ) -> Dict[str, str]:
        if not os.path.exists(directory_path):
            return {"error": f"Directory not found: {directory_path}"}
        if not os.path.isdir(directory_path):
            return {"error": f"Path is not a directory: {directory_path}"}
        pdf_files = self.get_pdf_files_in_directory(directory_path)
        if not pdf_files:
            return {"message": f"No PDF files found in directory: {directory_path}"}
        return self.extract_text_from_pdf_batch(pdf_files, simulate_human)

    def word_insert_table(
        self, rows: int, columns: int, process_name: Optional[str] = None
    ) -> str:
        return str(
            self._execute_office_command(
                "WINWORD.EXE",
                "insert_table",
                {"rows": rows, "columns": columns},
                process_name,
            )
        )

    def word_select_text(self, text: str, process_name: Optional[str] = None) -> str:
        return str(
            self._execute_office_command(
                "WINWORD.EXE", "select_text", {"text": text}, process_name
            )
        )

    def word_select_table(self, number: int, process_name: Optional[str] = None) -> str:
        return str(
            self._execute_office_command(
                "WINWORD.EXE", "select_table", {"number": number}, process_name
            )
        )

    def word_select_paragraph(
        self,
        start_index: int,
        end_index: int,
        non_empty: bool = True,
        process_name: Optional[str] = None,
    ) -> str:
        return str(
            self._execute_office_command(
                "WINWORD.EXE",
                "select_paragraph",
                {
                    "start_index": start_index,
                    "end_index": end_index,
                    "non_empty": non_empty,
                },
                process_name,
            )
        )

    def word_save_as(
        self,
        file_dir: str = "",
        file_name: str = "",
        file_ext: str = "",
        process_name: Optional[str] = None,
    ) -> str:
        return str(
            self._execute_office_command(
                "WINWORD.EXE",
                "save_as",
                {"file_dir": file_dir, "file_name": file_name, "file_ext": file_ext},
                process_name,
            )
        )

    def word_set_font(
        self,
        font_name: Optional[str] = None,
        font_size: Optional[int] = None,
        process_name: Optional[str] = None,
    ) -> str:
        return str(
            self._execute_office_command(
                "WINWORD.EXE",
                "set_font",
                {"font_name": font_name, "font_size": font_size},
                process_name,
            )
        )

    def excel_table2markdown(
        self, sheet_name: Any, process_name: Optional[str] = None
    ) -> str:
        return str(
            self._execute_office_command(
                "EXCEL.EXE",
                "table2markdown",
                {"sheet_name": sheet_name},
                process_name,
            )
        )

    def excel_insert_table(
        self,
        table: List[List[Any]],
        sheet_name: str,
        start_row: int,
        start_col: Any,
        process_name: Optional[str] = None,
    ) -> str:
        return str(
            self._execute_office_command(
                "EXCEL.EXE",
                "insert_excel_table",
                {
                    "table": table,
                    "sheet_name": sheet_name,
                    "start_row": start_row,
                    "start_col": start_col,
                },
                process_name,
            )
        )

    def excel_select_table_range(
        self,
        sheet_name: str,
        start_row: int,
        start_col: Any,
        end_row: int,
        end_col: Any,
        process_name: Optional[str] = None,
    ) -> str:
        return str(
            self._execute_office_command(
                "EXCEL.EXE",
                "select_table_range",
                {
                    "sheet_name": sheet_name,
                    "start_row": start_row,
                    "start_col": start_col,
                    "end_row": end_row,
                    "end_col": end_col,
                },
                process_name,
            )
        )

    def excel_save_as(
        self,
        file_dir: str = "",
        file_name: str = "",
        file_ext: str = "",
        process_name: Optional[str] = None,
    ) -> str:
        return str(
            self._execute_office_command(
                "EXCEL.EXE",
                "save_as",
                {"file_dir": file_dir, "file_name": file_name, "file_ext": file_ext},
                process_name,
            )
        )

    def excel_reorder_columns(
        self,
        sheet_name: str,
        desired_order: List[str],
        process_name: Optional[str] = None,
    ) -> str:
        return str(
            self._execute_office_command(
                "EXCEL.EXE",
                "reorder_columns",
                {"sheet_name": sheet_name, "desired_order": desired_order},
                process_name,
            )
        )

    def excel_get_range_values(
        self,
        sheet_name: str,
        start_row: int,
        start_col: int,
        end_row: int = -1,
        end_col: int = -1,
        process_name: Optional[str] = None,
    ) -> List[List[Any]]:
        return self._execute_office_command(
            "EXCEL.EXE",
            "get_range_values",
            {
                "sheet_name": sheet_name,
                "start_row": start_row,
                "start_col": start_col,
                "end_row": end_row,
                "end_col": end_col,
            },
            process_name,
        )

    def powerpoint_set_background_color(
        self,
        color: str,
        slide_index: Optional[List[int]] = None,
        process_name: Optional[str] = None,
    ) -> str:
        return str(
            self._execute_office_command(
                "POWERPNT.EXE",
                "set_background_color",
                {"color": color, "slide_index": slide_index},
                process_name,
            )
        )

    def powerpoint_save_as(
        self,
        file_dir: str = "",
        file_name: str = "",
        file_ext: str = "",
        current_slide_only: bool = False,
        process_name: Optional[str] = None,
    ) -> str:
        return str(
            self._execute_office_command(
                "POWERPNT.EXE",
                "save_as",
                {
                    "file_dir": file_dir,
                    "file_name": file_name,
                    "file_ext": file_ext,
                    "current_slide_only": current_slide_only,
                },
                process_name,
            )
        )
