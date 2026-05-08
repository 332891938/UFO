import json
import os
import sys
import time
import traceback
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from test_mcp_e2e_real import test_mcp_ui_flow_real
from test_mcp_strict_acceptance_e2e_real import test_mcp_strict_acceptance_real
from test_mcp_text_entry_e2e_real import test_mcp_text_entry_flow_real
from test_mcp_zonui3b_actions_e2e_real import test_mcp_zonui3b_click_flow_real
from test_mcp_zonui3b_e2e_real import test_mcp_zonui3b_deep_flow_real


ARTIFACT_DIR = Path(__file__).resolve().parent / "_artifacts"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_PATH = ARTIFACT_DIR / "final_real_regression_direct.json"


def _run_test(name: str, func, server_url: str) -> dict:
    started_at = int(time.time())
    try:
        func(server_url)
        return {
            "test_name": name,
            "status": "passed",
            "started_at": started_at,
            "finished_at": int(time.time()),
        }
    except pytest.skip.Exception as exc:  # type: ignore[attr-defined]
        return {
            "test_name": name,
            "status": "skipped",
            "message": str(exc),
            "started_at": started_at,
            "finished_at": int(time.time()),
        }
    except BaseException as exc:
        return {
            "test_name": name,
            "status": "failed",
            "error_type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
            "started_at": started_at,
            "finished_at": int(time.time()),
        }


def _write_report(server_url: str, results: list[dict]) -> None:
    summary = {
        "server_url": server_url,
        "generated_at": int(time.time()),
        "results": results,
    }
    REPORT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    os.environ.setdefault("HERMES_RUN_REAL_TESTS", "1")
    os.environ.setdefault("HERMES_TEST_SERVER_URL", "http://127.0.0.1:8037/mcp")
    os.environ.setdefault("HERMES_TEST_UI_APP", "notepad.exe")
    os.environ.setdefault("HERMES_TEST_UI_WINDOW_KEYWORD", "Notepad")
    os.environ.setdefault("HERMES_TEST_WINDOW_CLASS_NAME", "Notepad")
    os.environ.setdefault("HERMES_TEST_REQUIRE_UI_CHANGED", "1")
    os.environ.setdefault("HERMES_TEST_REQUIRE_ZONUI3B_FOUND", "1")
    os.environ.setdefault("HERMES_TEST_REQUIRE_TEXT_READBACK", "1")
    os.environ.setdefault("HERMES_TEST_SAVE_ARTIFACTS", "1")

    server_url = os.environ["HERMES_TEST_SERVER_URL"]
    tests = [
        ("test_mcp_ui_flow_real", test_mcp_ui_flow_real),
        ("test_mcp_text_entry_flow_real", test_mcp_text_entry_flow_real),
        ("test_mcp_zonui3b_click_flow_real", test_mcp_zonui3b_click_flow_real),
        ("test_mcp_zonui3b_deep_flow_real", test_mcp_zonui3b_deep_flow_real),
        ("test_mcp_strict_acceptance_real", test_mcp_strict_acceptance_real),
    ]

    results: list[dict] = []
    _write_report(server_url, results)
    for name, func in tests:
        results.append(_run_test(name, func, server_url))
        _write_report(server_url, results)
    print(REPORT_PATH)
    return 0 if all(item["status"] == "passed" for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
