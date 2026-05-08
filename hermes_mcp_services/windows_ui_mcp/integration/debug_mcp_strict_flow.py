import asyncio
import base64
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastmcp import Client

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from window_launch_utils import _desktop_snapshot, _match_mcp_window, close_test_window


ROOT = Path(__file__).resolve().parent
ARTIFACT_DIR = Path(
    os.environ.get("HERMES_TEST_ARTIFACT_DIR", str(ROOT / "_artifacts"))
)


def _window_area(item: Dict[str, Any]) -> int:
    rect = item.get("rectangle") or {}
    try:
        return int(rect.get("width", 0)) * int(rect.get("height", 0))
    except Exception:
        return 0


def _should_exclude_window(item: Dict[str, Any]) -> bool:
    name = str(item.get("name") or "")
    class_name = str(item.get("class_name") or "")

    exclude_substrings = [
        s.strip().lower()
        for s in (
            os.environ.get("HERMES_TEST_WINDOW_EXCLUDE", "notepad++|文件资源管理器")
            or ""
        ).split("|")
        if s.strip()
    ]
    exclude_class_names = {
        s.strip()
        for s in (
            os.environ.get(
                "HERMES_TEST_WINDOW_EXCLUDE_CLASS", "CabinetWClass|Notepad++"
            )
            or ""
        ).split("|")
        if s.strip()
    }

    if class_name in exclude_class_names:
        return True
    name_l = name.lower()
    return any(ex in name_l for ex in exclude_substrings)


def _pick_window(
    windows: List[Dict[str, Any]], keyword: str, preferred_class: str
) -> Optional[Dict[str, Any]]:
    keyword_l = (keyword or "").strip().lower()
    preferred_class_l = (preferred_class or "").strip().lower()

    candidates = [w for w in windows if not _should_exclude_window(w)]
    class_matches = [
        w
        for w in candidates
        if str(w.get("class_name") or "").lower() == preferred_class_l
    ]
    if class_matches:
        class_matches.sort(
            key=lambda w: (
                1 if keyword_l in str(w.get("name") or "").lower() else 0,
                _window_area(w),
            ),
            reverse=True,
        )
        return class_matches[0]

    best: Optional[Dict[str, Any]] = None
    best_score = -10**9
    for item in candidates:
        name_l = str(item.get("name") or "").lower()
        class_name_l = str(item.get("class_name") or "").lower()
        control_type = str(item.get("control_type") or "").lower()

        score = 0
        if keyword_l and keyword_l in name_l:
            score += 10
        if control_type == "window":
            score += 5
        if preferred_class_l and class_name_l == preferred_class_l:
            score += 100
        if preferred_class_l and name_l.endswith(f" - {preferred_class_l}"):
            score += 50
        if _window_area(item) > 0:
            score += 1
        if score > best_score:
            best_score = score
            best = item
    return best


def _pick_text_control(controls: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    candidates: List[Tuple[int, int, Dict[str, Any]]] = []
    for idx, item in enumerate(controls):
        ctype = str(item.get("type") or "").lower()
        rect = item.get("rect") or [0, 0, 0, 0]
        area = 0
        if isinstance(rect, list) and len(rect) >= 4:
            left, top, right, bottom = rect[:4]
            area = max(0, right - left) * max(0, bottom - top)
        score = 0
        if ctype in {"edit", "document"}:
            score += 100
        if ctype in {"pane", "text"}:
            score += 10
        score += min(50, area // 5000)
        candidates.append((score, idx, item))
    if not candidates:
        return None
    candidates.sort(key=lambda t: (t[0], -t[1]), reverse=True)
    return candidates[0][2]


def _center(rect: List[int]) -> Tuple[float, float]:
    left, top, right, bottom = rect[:4]
    return (left + right) / 2.0, (top + bottom) / 2.0


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")


def _write_image(path: Path, data_url: str) -> None:
    raw = data_url.split(",", 1)[1] if "," in data_url else data_url
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(base64.b64decode(raw))


async def _call_tool(
    client: Client, report: Dict[str, Any], name: str, args: Dict[str, Any], timeout: float = 120.0
) -> Any:
    report["events"].append({"stage": name, "arguments": args})
    try:
        result = await asyncio.wait_for(client.call_tool(name, args), timeout=timeout)
        report["events"].append({"stage": f"{name}:ok"})
        return result.data
    except Exception:
        report["events"].append(
            {
                "stage": f"{name}:error",
                "traceback": traceback.format_exc(),
            }
        )
        raise


async def main() -> None:
    server_url = os.environ.get("HERMES_TEST_SERVER_URL", "http://127.0.0.1:8031/mcp")
    app_command = os.environ.get("HERMES_TEST_UI_APP", "notepad.exe").strip() or "notepad.exe"
    window_keyword = os.environ.get("HERMES_TEST_UI_WINDOW_KEYWORD", "Notepad").strip() or "Notepad"
    window_class = os.environ.get("HERMES_TEST_WINDOW_CLASS_NAME", "Notepad").strip() or "Notepad"
    zonui_desc = os.environ.get("HERMES_TEST_ZONUI3B_DESC", "File").strip() or "File"
    text = os.environ.get("HERMES_TEST_TEXT", "").strip() or f"debug-flow-{int(time.time())}"

    run_id = f"debug_{int(time.time())}"
    report_path = ARTIFACT_DIR / f"{run_id}.json"
    report: Dict[str, Any] = {
        "run_id": run_id,
        "server_url": server_url,
        "status": "running",
        "events": [],
    }
    _write_json(report_path, report)
    launched_handle = None

    try:
        async with Client(server_url) as client:
            windows = await _call_tool(
                client,
                report,
                "get_desktop_app_info",
                {"remove_empty": True, "refresh_app_windows": True},
            )
            target = _pick_window(windows, window_keyword, window_class)
            if target is None:
                before = _desktop_snapshot()
                await _call_tool(client, report, "run_shell", {"bash_command": app_command})
                await asyncio.sleep(2)
                windows = await _call_tool(
                    client,
                    report,
                    "get_desktop_app_info",
                    {"remove_empty": True, "refresh_app_windows": True},
                )
                after = _desktop_snapshot()
                new_handles = [handle for handle in after.keys() if handle not in before]
                for handle in reversed(new_handles):
                    candidate = _match_mcp_window(
                        windows,
                        after[handle],
                        lambda items: _pick_window(items, window_keyword, window_class),
                    )
                    if candidate is not None:
                        launched_handle = handle
                        break
                report["launched_handle"] = launched_handle
            else:
                raise RuntimeError(
                    "Debug flow now expects no pre-existing Notepad window. "
                    "Please close existing Notepad windows first."
                )
            report["windows_count"] = len(windows)
            _write_json(ARTIFACT_DIR / f"{run_id}_windows.json", windows)

            target = _pick_window(windows, window_keyword, window_class)
            report["selected_window"] = target
            _write_json(ARTIFACT_DIR / f"{run_id}_selected_window.json", target)
            if target is None:
                raise RuntimeError("No suitable target window found.")

            selected = await _call_tool(
                client,
                report,
                "select_application_window",
                {"id": target["id"], "name": target["name"]},
            )
            report["selected_result"] = selected
            _write_json(ARTIFACT_DIR / f"{run_id}_selected_result.json", selected)

            before = await _call_tool(client, report, "capture_window_screenshot", {})
            _write_image(ARTIFACT_DIR / f"{run_id}_before.png", before)

            found = await _call_tool(
                client,
                report,
                "find_control_on_screen",
                {"description": zonui_desc, "element_type": "Button"},
            )
            report["found"] = found
            _write_json(ARTIFACT_DIR / f"{run_id}_zonui_found.json", found)

            if found and found.get("id"):
                click_result = await _call_tool(
                    client,
                    report,
                    "click_control",
                    {"control_id": found["id"], "control_name": found.get("name", "")},
                )
            elif found and found.get("rect"):
                x, y = _center(found["rect"])
                click_result = await _call_tool(
                    client,
                    report,
                    "click_on_coordinates",
                    {"x": x, "y": y},
                )
            else:
                raise RuntimeError(f"ZonUI-3B did not return a usable target: {found!r}")

            report["click_result"] = click_result
            _write_json(ARTIFACT_DIR / f"{run_id}_click_result.json", click_result)
            await asyncio.sleep(0.4)

            after_click = await _call_tool(client, report, "capture_window_screenshot", {})
            _write_image(ARTIFACT_DIR / f"{run_id}_after_click.png", after_click)

            controls = await _call_tool(
                client,
                report,
                "get_app_window_controls_target_info",
                {"field_list": [], "max_controls": 500},
            )
            report["controls_count"] = len(controls)
            _write_json(ARTIFACT_DIR / f"{run_id}_controls.json", controls)

            text_control = _pick_text_control(controls)
            report["text_control"] = text_control
            _write_json(ARTIFACT_DIR / f"{run_id}_text_control.json", text_control)
            if not text_control or not text_control.get("id"):
                raise RuntimeError("No usable text control found.")

            await _call_tool(
                client,
                report,
                "click_input",
                {"id": text_control["id"], "name": text_control.get("name", "")},
            )
            await _call_tool(
                client,
                report,
                "set_edit_text",
                {
                    "id": text_control["id"],
                    "name": text_control.get("name", ""),
                    "text": text,
                    "clear_current_text": True,
                },
            )
            await asyncio.sleep(0.4)

            after_type = await _call_tool(client, report, "capture_window_screenshot", {})
            _write_image(ARTIFACT_DIR / f"{run_id}_after_type.png", after_type)

            readback = await _call_tool(
                client,
                report,
                "texts",
                {"id": text_control["id"], "name": text_control.get("name", "")},
            )
            report["readback"] = readback
            _write_text(ARTIFACT_DIR / f"{run_id}_readback.txt", str(readback))

            report["status"] = "passed"
    except Exception:
        report["status"] = "failed"
        report["fatal_traceback"] = traceback.format_exc()
    finally:
        close_test_window(launched_handle)
        _write_json(report_path, report)
        print(report_path)


if __name__ == "__main__":
    asyncio.run(main())
