import json
from pathlib import Path

from window_launch_utils import (
    _desktop_snapshot,
    close_test_window,
    get_windows,
    launch_test_window,
)


ARTIFACT_PATH = Path(__file__).resolve().parent / "_artifacts" / "debug_launch_window.json"


def main() -> None:
    server_url = "http://127.0.0.1:8037/mcp"
    before_desktop = _desktop_snapshot()
    before_windows = get_windows(server_url)
    windows, target, launched_handle = launch_test_window(
        server_url,
        "notepad.exe",
        lambda items: next(
            (
                item
                for item in items
                if "Notepad" in str(item.get("name", ""))
                or str(item.get("class_name", "")) == "Notepad"
            ),
            None,
        ),
    )
    after_desktop = _desktop_snapshot()
    after_windows = get_windows(server_url)

    report = {
        "before_desktop_count": len(before_desktop),
        "before_windows_count": len(before_windows),
        "after_desktop_count": len(after_desktop),
        "after_windows_count": len(after_windows),
        "launched_handle": launched_handle,
        "target": target,
        "before_windows_top": before_windows[:20],
        "after_windows_top": after_windows[:20],
        "new_desktop_handles": [
            handle for handle in after_desktop.keys() if handle not in before_desktop
        ],
        "new_mcp_windows": [
            item
            for item in after_windows
            if str(item.get("id") or "")
            not in {str(win.get("id") or "") for win in before_windows}
        ],
    }
    ARTIFACT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    close_test_window(launched_handle)
    print(ARTIFACT_PATH)


if __name__ == "__main__":
    main()
