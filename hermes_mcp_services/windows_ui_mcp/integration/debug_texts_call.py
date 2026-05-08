import asyncio
import json
import os
import traceback
from pathlib import Path

from fastmcp import Client


ARTIFACT_DIR = Path(__file__).resolve().parent / "_artifacts"


async def main() -> None:
    server_url = os.environ.get("HERMES_TEST_SERVER_URL", "http://127.0.0.1:8037/mcp")
    control_id = os.environ.get("HERMES_TEST_CONTROL_ID", "1")
    control_name = os.environ.get("HERMES_TEST_CONTROL_NAME", "文本编辑器")
    out = {
        "server_url": server_url,
        "control_id": control_id,
        "control_name": control_name,
        "status": "running",
    }
    path = ARTIFACT_DIR / "debug_texts_call.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        async with Client(server_url) as client:
            result = await client.call_tool(
                "texts",
                {"id": control_id, "name": control_name},
            )
            out["status"] = "passed"
            out["result"] = result.data
    except Exception:
        out["status"] = "failed"
        out["traceback"] = traceback.format_exc()
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    asyncio.run(main())
