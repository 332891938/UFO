import json
import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp_service import WindowsMCPService


ARTIFACT_DIR = Path(__file__).resolve().parent / "_artifacts"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


def main() -> None:
    desc = os.environ.get("HERMES_TEST_ZONUI3B_DESC", "File")
    out = {
        "description": desc,
        "status": "running",
    }
    out_path = ARTIFACT_DIR / "debug_service_find_control_result.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        service = WindowsMCPService()
        windows = service.get_desktop_app_info(remove_empty=True, refresh_app_windows=True)
        out["windows_count"] = len(windows)

        target = None
        for item in windows:
            if str(item.get("class_name", "")) == "Notepad" and "Notepad" in str(item.get("name", "")):
                target = item
                break
        out["target"] = target
        if target is None:
            raise RuntimeError("Notepad window not found.")

        selected = service.select_application_window(target["id"], target["name"])
        out["selected"] = selected
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

        out["find_control_on_screen_started"] = True
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

        found = service.find_control_on_screen(description=desc)
        out["find_control_on_screen_finished"] = True
        out["found"] = found.model_dump() if hasattr(found, "model_dump") else found
        out["status"] = "passed"
    except Exception:
        out["status"] = "failed"
        out["traceback"] = traceback.format_exc()
    finally:
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
