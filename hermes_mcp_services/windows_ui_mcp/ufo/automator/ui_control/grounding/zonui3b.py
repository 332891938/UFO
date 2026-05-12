# ZonUI-3B grounding模块
# 支持两种模式：
#   1. 本地加载（需要 torch + GPU）
#   2. HTTP远程调用（连接 WSL 中的 ZonUI-3B 服务）

import logging
import platform
from typing import Any, Dict, List, TYPE_CHECKING, Optional

from ufo.agents.processors.schemas.target import TargetInfo, TargetKind
from ufo.automator.ui_control.grounding.basic import BasicGrounding, VirtualUIAElementInfo

if TYPE_CHECKING or platform.system() == "Windows":
    from pywinauto.controls.uiawrapper import UIAWrapper
    from pywinauto.win32structures import RECT
else:
    UIAWrapper = Any
    RECT = Any

logger = logging.getLogger(__name__)

DEFAULT_MODEL_PATH = r"D:\open-source\ZonUI-3B\zonui-3b-model"
DEFAULT_SERVICE_URL = "http://localhost:8100"


class ZonUI3BGrounding(BasicGrounding):
    """基于ZonUI-3B的视觉定位器。

    支持两种模式：
    - 本地模式：直接加载模型（需要torch+CUDA）
    - HTTP模式：调用WSL中的ZonUI-3B HTTP服务
    """

    def __init__(self, model_path: str = DEFAULT_MODEL_PATH, service_url: Optional[str] = None):
        super().__init__(service=None)
        self.service_url = service_url
        self._local_service = None

        if service_url:
            import urllib.request, json as _json
            # Verify connection
            try:
                r = urllib.request.urlopen(f"{service_url}/health", timeout=5)
                logger.info(f"ZonUI-3B HTTP service ready at {service_url}")
            except Exception as e:
                logger.warning(f"ZonUI-3B HTTP service not reachable: {e}")
        else:
            # Local mode: lazy import to avoid torch dependency at module level
            from ufo.automator.ui_control.grounding.zonui3b_service import ZonUI3BService
            self._local_service = ZonUI3BService.get_instance(model_path)

    def _post_json(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        import json as _json
        import urllib.request

        data = _json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{self.service_url}{endpoint}",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            r = urllib.request.urlopen(req, timeout=120)
            return _json.loads(r.read().decode())
        except Exception as e:
            return {"success": False, "error": str(e)}

    def predict(
        self,
        image_path: str,
        query: str = "",
        annotate: bool = False,
        output_path: str = "",
    ) -> Dict[str, Any]:
        if not query:
            return {"success": False, "error": "Empty query"}

        if self.service_url:
            return self._predict_http(
                image_path,
                query,
                annotate=annotate,
                output_path=output_path,
            )
        else:
            return self._predict_local(image_path, query)

    def _predict_http(
        self,
        image_path: str,
        query: str,
        annotate: bool = False,
        output_path: str = "",
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "image_path": image_path,
            "query": query,
        }
        if annotate:
            payload["annotate"] = True
        if output_path:
            payload["output_path"] = output_path
        return self._post_json("/predict", payload)

    def _predict_local(self, image_path: str, query: str) -> Dict[str, Any]:
        try:
            norm_x, norm_y, abs_x, abs_y = self._local_service.predict(image_path, query)
            return {"success": True, "norm_x": norm_x, "norm_y": norm_y, "abs_x": abs_x, "abs_y": abs_y}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def describe_window(
        self,
        image_path: str,
        query: str = "",
        context: str = "",
    ) -> Dict[str, Any]:
        if self.service_url:
            payload: Dict[str, Any] = {"image_path": image_path}
            if query:
                payload["query"] = query
            if context:
                payload["context"] = context
            return self._post_json("/describe", payload)
        return {
            "success": False,
            "error": "describe_window requires ZonUI-3B HTTP service mode.",
        }

    def inspect_window(
        self,
        image_path: str,
        checks: List[str],
        context: str = "",
    ) -> Dict[str, Any]:
        if not checks:
            return {"success": False, "error": "Empty checks"}
        if self.service_url:
            payload: Dict[str, Any] = {
                "image_path": image_path,
                "checks": checks,
            }
            if context:
                payload["context"] = context
            return self._post_json("/inspect", payload)
        return {
            "success": False,
            "error": "inspect_window requires ZonUI-3B HTTP service mode.",
        }

    def find_element(
        self,
        screenshot_path,
        description,
        application_window_info=None,
        element_type="Button",
        annotate: bool = False,
        output_path: str = "",
    ):
        result = self.predict(
            screenshot_path,
            description,
            annotate=annotate,
            output_path=output_path,
        )
        if not result.get("success"):
            return None

        abs_x = result["abs_x"]
        abs_y = result["abs_y"]

        if application_window_info and application_window_info.rect:
            rect = application_window_info.rect
            if len(rect) >= 4:
                abs_x += rect[0]
                abs_y += rect[1]

        radius = 10
        return TargetInfo(
            kind=TargetKind.CONTROL,
            type=element_type,
            name=description,
            rect=(int(abs_x - radius), int(abs_y - radius), int(abs_x + radius), int(abs_y + radius)),
        )

    def parse_results(self, results, application_window=None):
        if not results:
            return []
        result = results[0] if isinstance(results, list) else results
        if not result.get("success"):
            return []
        abs_x, abs_y = result["abs_x"], result["abs_y"]
        radius = 8
        return [{"control_type": result.get("type", "Button"), "name": result.get("query", ""),
                 "x0": int(abs_x - radius), "y0": int(abs_y - radius),
                 "x1": int(abs_x + radius), "y1": int(abs_y + radius)}]

    def screen_parsing(
        self,
        screenshot_path,
        application_window_info=None,
        query="",
        annotate: bool = False,
        output_path: str = "",
    ):
        if not query:
            return []
        result = self.predict(
            screenshot_path,
            query,
            annotate=annotate,
            output_path=output_path,
        )
        if not result.get("success"):
            return []
        abs_x, abs_y = result["abs_x"], result["abs_y"]
        if application_window_info and application_window_info.rect:
            rect = application_window_info.rect
            if len(rect) >= 4:
                abs_x += rect[0]; abs_y += rect[1]
        radius = 8
        return [TargetInfo(kind=TargetKind.CONTROL, type="Button", name=query,
                rect=(int(abs_x - radius), int(abs_y - radius), int(abs_x + radius), int(abs_y + radius)))]
