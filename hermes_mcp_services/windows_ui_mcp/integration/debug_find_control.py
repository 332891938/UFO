import asyncio
import json
import os
import traceback
from pathlib import Path

from fastmcp import Client


ARTIFACT_DIR = Path(__file__).resolve().parent / "_artifacts"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


async def main() -> None:
    server_url = os.environ.get("HERMES_TEST_SERVER_URL", "http://127.0.0.1:8031/mcp")
    desc = os.environ.get("HERMES_TEST_ZONUI3B_DESC", "File")
    result = {
        "server_url": server_url,
        "description": desc,
        "status": "running",
    }
    out_path = ARTIFACT_DIR / "debug_find_control_result.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        async with Client(server_url) as client:
            windows = (
                await client.call_tool(
                    "get_desktop_app_info",
                    {"remove_empty": True, "refresh_app_windows": True},
                )
            ).data
            result["windows_count"] = len(windows)

            target = None
            for item in windows:
                if str(item.get("class_name", "")) == "Notepad" and "Notepad" in str(item.get("name", "")):
                    target = item
                    break
            result["target"] = target
            if target is None:
                raise RuntimeError("Notepad window not found.")

            selected = (
                await client.call_tool(
                    "select_application_window",
                    {"id": target["id"], "name": target["name"]},
                )
            ).data
            result["selected"] = selected
            out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

            result["find_control_on_screen_started"] = True
            out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

            found = (
                await asyncio.wait_for(
                    client.call_tool(
                        "find_control_on_screen",
                        {"description": desc, "element_type": "Button"},
                    ),
                    timeout=30.0,
                )
            ).data
            result["find_control_on_screen_finished"] = True
            result["found"] = found
            result["status"] = "passed"
    except Exception:
        result["status"] = "failed"
        result["traceback"] = traceback.format_exc()
    finally:
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
