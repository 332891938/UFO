import json
import os
import time
from pathlib import Path
from typing import Any


def write_success_artifact(test_name: str, **extra: Any) -> Path:
    artifact_dir = Path(
        os.environ.get(
            "HERMES_TEST_SUCCESS_ARTIFACT_DIR",
            str(Path(__file__).resolve().parent / "_artifacts" / "success"),
        )
    )
    artifact_dir.mkdir(parents=True, exist_ok=True)
    path = artifact_dir / f"{test_name}.json"
    payload = {
        "test_name": test_name,
        "status": "passed",
        "timestamp": int(time.time()),
    }
    payload.update(extra)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
