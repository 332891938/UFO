import json
import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
INTEGRATION_DIR = Path(__file__).resolve().parent
if str(INTEGRATION_DIR) not in sys.path:
    sys.path.insert(0, str(INTEGRATION_DIR))

from mcp_service import WindowsMCPService
from window_launch_utils import _desktop_snapshot, close_test_window


ARTIFACT_PATH = (
    Path(__file__).resolve().parent / "_artifacts" / "debug_document_readback.json"
)


def _safe(callable_obj):
    try:
        value = callable_obj()
        if isinstance(value, (list, tuple)):
            return [str(v) for v in value]
        return value
    except Exception:
        return {"error": traceback.format_exc()}


def main() -> None:
    service = WindowsMCPService()
    app_command = os.environ.get("HERMES_TEST_UI_APP", "notepad.exe").strip() or "notepad.exe"
    launched_handle = None
    windows = service.get_desktop_app_info(remove_empty=True, refresh_app_windows=True)
    target = next((w for w in windows if str(w.get("class_name")) == "Notepad"), None)
    if not target:
        before = _desktop_snapshot()
        service.run_shell(app_command)
        time.sleep(2)
        after = _desktop_snapshot()
        new_handles = [handle for handle in after.keys() if handle not in before]
        launched_handle = new_handles[-1] if new_handles else None
        windows = service.get_desktop_app_info(remove_empty=True, refresh_app_windows=True)
        target = next((w for w in windows if str(w.get("class_name")) == "Notepad"), None)
    out = {"windows_found": len(windows), "target": target}
    try:
        if not target:
            out["status"] = "failed"
            out["error"] = "No Notepad window found."
            ARTIFACT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
            print(ARTIFACT_PATH)
            return

        service.select_application_window(str(target["id"]), str(target["name"]))
        controls = service.get_app_window_controls_target_info([], 500)
        doc = next((c for c in controls if str(c.type).lower() in {"document", "edit"}), None)
        out["document_control"] = doc.model_dump() if doc else None
        if not doc:
            out["status"] = "failed"
            out["error"] = "No document/edit control found."
            ARTIFACT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
            print(ARTIFACT_PATH)
            return

        control = service.state.control_dict[str(doc.id)]
        out["reads"] = {
            "texts": _safe(lambda: control.texts()),
            "window_text": _safe(lambda: control.window_text()),
            "legacy_properties": _safe(lambda: control.legacy_properties()),
            "iface_value": _safe(lambda: control.iface_value.CurrentValue),
            "element_name": _safe(lambda: control.element_info.name),
            "rich_text": _safe(lambda: getattr(control.element_info, "rich_text", None)),
        }
        out["status"] = "passed"
        ARTIFACT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(ARTIFACT_PATH)
    finally:
        close_test_window(launched_handle)


if __name__ == "__main__":
    main()
