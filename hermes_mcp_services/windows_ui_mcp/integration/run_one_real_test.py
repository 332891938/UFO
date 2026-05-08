import json
import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from test_mcp_e2e_real import test_mcp_ui_flow_real
from test_mcp_strict_acceptance_e2e_real import test_mcp_strict_acceptance_real
from test_mcp_text_entry_e2e_real import test_mcp_text_entry_flow_real
from test_mcp_zonui3b_actions_e2e_real import test_mcp_zonui3b_click_flow_real
from test_mcp_zonui3b_e2e_real import test_mcp_zonui3b_deep_flow_real


ARTIFACT_DIR = ROOT / "_artifacts"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

TESTS = {
    "test_mcp_ui_flow_real": test_mcp_ui_flow_real,
    "test_mcp_text_entry_flow_real": test_mcp_text_entry_flow_real,
    "test_mcp_zonui3b_click_flow_real": test_mcp_zonui3b_click_flow_real,
    "test_mcp_zonui3b_deep_flow_real": test_mcp_zonui3b_deep_flow_real,
    "test_mcp_strict_acceptance_real": test_mcp_strict_acceptance_real,
}


def _apply_default_env() -> str:
    os.environ.setdefault("HERMES_RUN_REAL_TESTS", "1")
    os.environ.setdefault("HERMES_TEST_SERVER_URL", "http://127.0.0.1:8037/mcp")
    os.environ.setdefault("HERMES_TEST_UI_APP", "notepad.exe")
    os.environ.setdefault("HERMES_TEST_UI_WINDOW_KEYWORD", "Notepad")
    os.environ.setdefault("HERMES_TEST_WINDOW_CLASS_NAME", "Notepad")
    os.environ.setdefault("HERMES_TEST_REQUIRE_UI_CHANGED", "1")
    os.environ.setdefault("HERMES_TEST_REQUIRE_ZONUI3B_FOUND", "1")
    os.environ.setdefault("HERMES_TEST_REQUIRE_TEXT_READBACK", "1")
    os.environ.setdefault("HERMES_TEST_SAVE_ARTIFACTS", "1")
    return os.environ["HERMES_TEST_SERVER_URL"]


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python run_one_real_test.py <test_name>")
        return 2

    test_name = sys.argv[1].strip()
    func = TESTS.get(test_name)
    if func is None:
        print(f"Unknown test: {test_name}")
        return 2

    server_url = _apply_default_env()
    out_path = ARTIFACT_DIR / f"single_{test_name}.json"
    started_at = int(time.time())
    try:
        func(server_url)
        payload = {
            "test_name": test_name,
            "status": "passed",
            "started_at": started_at,
            "finished_at": int(time.time()),
            "server_url": server_url,
        }
    except BaseException as exc:
        payload = {
            "test_name": test_name,
            "status": "failed",
            "error_type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
            "started_at": started_at,
            "finished_at": int(time.time()),
            "server_url": server_url,
        }

    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out_path)
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
