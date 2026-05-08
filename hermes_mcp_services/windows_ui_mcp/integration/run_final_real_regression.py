import json
import os
from pathlib import Path
from typing import Any

import pytest


ARTIFACT_DIR = Path(__file__).resolve().parent / "_artifacts"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_PATH = ARTIFACT_DIR / "final_real_regression_report.json"


class ReportPlugin:
    def __init__(self) -> None:
        self.reports: list[dict[str, Any]] = []

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        self.reports.append(
            {
                "nodeid": report.nodeid,
                "when": report.when,
                "outcome": report.outcome,
                "longreprtext": getattr(report, "longreprtext", "") or "",
            }
        )


def main() -> int:
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    os.environ.setdefault("HERMES_RUN_REAL_TESTS", "1")
    os.environ.setdefault("HERMES_TEST_SERVER_URL", "http://127.0.0.1:8037/mcp")
    os.environ.setdefault("HERMES_TEST_UI_APP", "notepad.exe")
    os.environ.setdefault("HERMES_TEST_UI_WINDOW_KEYWORD", "Notepad")
    os.environ.setdefault("HERMES_TEST_WINDOW_CLASS_NAME", "Notepad")
    os.environ.setdefault("HERMES_TEST_REQUIRE_UI_CHANGED", "1")
    os.environ.setdefault("HERMES_TEST_REQUIRE_ZONUI3B_FOUND", "1")
    os.environ.setdefault("HERMES_TEST_REQUIRE_TEXT_READBACK", "1")

    args = [
        "integration/test_mcp_e2e_real.py::test_mcp_ui_flow_real",
        "integration/test_mcp_text_entry_e2e_real.py::test_mcp_text_entry_flow_real",
        "integration/test_mcp_zonui3b_actions_e2e_real.py::test_mcp_zonui3b_click_flow_real",
        "integration/test_mcp_zonui3b_e2e_real.py::test_mcp_zonui3b_deep_flow_real",
        "integration/test_mcp_strict_acceptance_e2e_real.py::test_mcp_strict_acceptance_real",
        "-q",
    ]
    plugin = ReportPlugin()
    rc = pytest.main(args, plugins=[plugin])
    summary = {
        "pytest_return_code": int(rc),
        "pytest_args": args,
        "reports": plugin.reports,
    }
    REPORT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(REPORT_PATH)
    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
