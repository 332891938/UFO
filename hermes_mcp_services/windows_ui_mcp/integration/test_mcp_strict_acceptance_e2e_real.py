import base64
import io
import json
import os
import time
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image, ImageChops

from conftest import call_tool, run_async
from window_launch_utils import close_test_window, launch_test_window


def _window_area(item: dict) -> int:
    rect = item.get("rectangle") or {}
    try:
        return int(rect.get("width", 0)) * int(rect.get("height", 0))
    except Exception:
        return 0


def _should_exclude_window(item: dict) -> bool:
    name = str(item.get("name") or "")
    class_name = str(item.get("class_name") or "")

    exclude_substrings = [
        s.strip().lower()
        for s in (
            os.environ.get("HERMES_TEST_WINDOW_EXCLUDE", "notepad++|文件资源管理器") or ""
        ).split("|")
        if s.strip()
    ]
    exclude_class_names = {
        s.strip()
        for s in (
            os.environ.get("HERMES_TEST_WINDOW_EXCLUDE_CLASS", "CabinetWClass|Notepad++")
            or ""
        ).split("|")
        if s.strip()
    }

    if class_name in exclude_class_names:
        return True
    name_l = name.lower()
    if any(ex in name_l for ex in exclude_substrings):
        return True
    return False


def _pick_window(windows: List[dict], keyword: str, preferred_class: str) -> Optional[dict]:
    keyword_l = (keyword or "").strip().lower()
    preferred_class = (preferred_class or "").strip()
    preferred_class_l = preferred_class.lower()

    candidates = [w for w in windows if not _should_exclude_window(w)]
    if preferred_class:
        class_matches = [
            w for w in candidates if str(w.get("class_name") or "").lower() == preferred_class_l
        ]
        if class_matches:

            def _score(w: dict) -> tuple[int, int]:
                name_l = str(w.get("name") or "").lower()
                kw = 1 if (keyword_l and keyword_l in name_l) else 0
                return (kw, _window_area(w))

            class_matches.sort(key=_score, reverse=True)
            return class_matches[0]

    best: Optional[dict] = None
    best_score = -10**9
    for item in candidates:
        name_l = str(item.get("name") or "").lower()
        class_name_l = str(item.get("class_name") or "").lower()
        control_type = str(item.get("control_type") or "")
        area = _window_area(item)

        score = 0
        if keyword_l and keyword_l in name_l:
            score += 10
        if control_type.lower() == "window":
            score += 5
        if preferred_class and class_name_l == preferred_class_l:
            score += 100
        if preferred_class and name_l.endswith(f" - {preferred_class_l}"):
            score += 50
        score += min(3, 1 if area > 0 else 0)

        if score > best_score:
            best_score = score
            best = item

    return best


def _env_flag(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _write_artifact_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _write_artifact_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_trace(trace_path: Path, trace: List[dict]) -> None:
    _write_artifact_text(
        trace_path,
        json.dumps(trace, ensure_ascii=False, indent=2),
    )


def _decode_data_url_png(data_url: str) -> Image.Image:
    if not isinstance(data_url, str) or not data_url.startswith("data:image/"):
        raise ValueError("Expected screenshot as data:image/*;base64,...")
    raw = data_url.split(",", 1)[1] if "," in data_url else data_url
    image = Image.open(io.BytesIO(base64.b64decode(raw)))
    return image.convert("RGB")


def _pixel_diff_ratio(a: Image.Image, b: Image.Image) -> float:
    if a.size != b.size:
        b = b.resize(a.size)
    diff = ImageChops.difference(a, b)
    gray = diff.convert("L")
    hist = gray.histogram()
    total = a.size[0] * a.size[1]
    changed = total - (hist[0] if hist else 0)
    return changed / max(1, total)


def _pick_text_control(controls: List[dict]) -> Optional[dict]:
    candidates: List[Tuple[int, int, dict]] = []
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


def _center(rect: List[int]) -> tuple[float, float]:
    left, top, right, bottom = rect[:4]
    return (left + right) / 2.0, (top + bottom) / 2.0


def test_mcp_strict_acceptance_real(server_url):
    app_command = os.environ.get("HERMES_TEST_UI_APP", "notepad.exe").strip() or "notepad.exe"
    window_keyword = os.environ.get("HERMES_TEST_UI_WINDOW_KEYWORD", "Notepad").strip() or "Notepad"
    window_class = os.environ.get("HERMES_TEST_WINDOW_CLASS_NAME", "Notepad").strip() or "Notepad"

    desc = os.environ.get("HERMES_TEST_ZONUI3B_DESC", "").strip()
    if not desc:
        desc = "File"

    text = os.environ.get("HERMES_TEST_TEXT", "").strip()
    if not text:
        text = f"strict-acceptance-{int(time.time())}"

    min_change = float(os.environ.get("HERMES_TEST_MIN_SCREENSHOT_CHANGE", "0.002").strip() or "0.002")
    min_text_change = float(
        os.environ.get("HERMES_TEST_MIN_TEXT_SCREENSHOT_CHANGE", "0.001").strip() or "0.001"
    )
    save_artifacts = _env_flag("HERMES_TEST_SAVE_ARTIFACTS", "0")
    artifact_dir = Path(
        os.environ.get("HERMES_TEST_ARTIFACT_DIR", str(Path(__file__).parent / "_artifacts"))
    )
    pause_seconds = float(os.environ.get("HERMES_TEST_PAUSE_SECONDS", "0").strip() or "0")

    windows, target_window, launched_handle = launch_test_window(
        server_url,
        app_command,
        lambda items: _pick_window(items, window_keyword, window_class),
    )
    try:
        assert target_window is not None, f"Window containing '{window_keyword}' was not found."
        if str(target_window.get("class_name") or "") != window_class:
            top = [
                {
                    "id": w.get("id"),
                    "name": w.get("name"),
                    "class_name": w.get("class_name"),
                    "area": _window_area(w),
                }
                for w in windows[:30]
            ]
            raise AssertionError(
                "Selected window class_name mismatch. "
                f"expected='{window_class}', got='{target_window.get('class_name')}'. "
                "This usually means the real Notepad window is minimized/hidden or "
                "keyword matched a different app (e.g. Trae/Chrome). "
                "Set HERMES_TEST_WINDOW_CLASS_NAME=Notepad and close/minimize other windows, "
                "or set HERMES_TEST_UI_WINDOW_KEYWORD to a more specific title. "
                f"Top windows snapshot={top}"
            )

        run_id = f"{int(time.time())}"
        trace: List[dict] = []
        trace_path = artifact_dir / f"strict_{run_id}_trace.json"
        if save_artifacts:
            _write_artifact_text(
                artifact_dir / f"strict_{run_id}_windows.json",
                json.dumps(windows, ensure_ascii=False, indent=2),
            )
            _write_artifact_text(
                artifact_dir / f"strict_{run_id}_selected_window.json",
                json.dumps(target_window, ensure_ascii=False, indent=2),
            )
            trace.append(
                {
                    "stage": "selected_window",
                    "window_id": target_window.get("id"),
                    "window_name": target_window.get("name"),
                    "window_class": target_window.get("class_name"),
                }
            )
            _write_trace(trace_path, trace)

        selected = run_async(
            call_tool(
                server_url,
                "select_application_window",
                {"id": target_window["id"], "name": target_window["name"]},
            )
        )
        assert isinstance(selected, dict) and selected.get("success") is True

        before_url = run_async(call_tool(server_url, "capture_window_screenshot", {}))
        before_img = _decode_data_url_png(before_url)
        if save_artifacts:
            _write_artifact_bytes(
                artifact_dir / f"strict_{run_id}_before.png",
                base64.b64decode(before_url.split(",", 1)[1]),
            )
            trace.append({"stage": "before_screenshot_saved"})
            _write_trace(trace_path, trace)

        controls = run_async(
            call_tool(
                server_url,
                "get_app_window_controls_target_info",
                {"field_list": [], "max_controls": 500},
            )
        )
        assert isinstance(controls, list) and controls, "UIA controls list is empty; cannot do strict text entry."
        text_control = _pick_text_control(controls)
        assert text_control is not None, "No candidate text control found for strict text entry."

        control_id = str(text_control.get("id") or "")
        control_name = str(text_control.get("name") or "")
        if save_artifacts:
            _write_artifact_text(
                artifact_dir / f"strict_{run_id}_text_control.json",
                json.dumps(text_control, ensure_ascii=False, indent=2),
            )
            trace.append(
                {
                    "stage": "text_control_selected",
                    "control_id": text_control.get("id"),
                    "control_name": text_control.get("name"),
                    "control_type": text_control.get("type"),
                }
            )
            _write_trace(trace_path, trace)
        assert control_id, f"Invalid text control id: {text_control!r}"

        found = run_async(
            call_tool(
                server_url,
                "find_control_on_screen",
                {"description": desc, "element_type": "Button"},
            )
        )
        assert found is not None, f"ZonUI-3B did not find target: {desc!r}"
        assert isinstance(found, dict), f"Unexpected find_control_on_screen output: {found!r}"
        if save_artifacts:
            _write_artifact_text(
                artifact_dir / f"strict_{run_id}_zonui_found.json",
                json.dumps(found, ensure_ascii=False, indent=2),
            )
            trace.append(
                {
                    "stage": "zonui_found",
                    "found_id": found.get("id"),
                    "found_name": found.get("name"),
                    "found_rect": found.get("rect"),
                }
            )
            _write_trace(trace_path, trace)

        if found.get("id"):
            run_async(
                call_tool(
                    server_url,
                    "click_control",
                    {"control_id": found["id"], "control_name": found.get("name", "")},
                )
            )
        else:
            rect = found.get("rect") or [0, 0, 0, 0]
            x, y = _center(rect)
            run_async(call_tool(server_url, "click_on_coordinates", {"x": x, "y": y}))

        time.sleep(0.4)
        after_click_url = run_async(call_tool(server_url, "capture_window_screenshot", {}))
        after_click_img = _decode_data_url_png(after_click_url)
        if save_artifacts:
            _write_artifact_bytes(
                artifact_dir / f"strict_{run_id}_after_click.png",
                base64.b64decode(after_click_url.split(",", 1)[1]),
            )
            trace.append({"stage": "after_click_screenshot_saved"})
            _write_trace(trace_path, trace)

        ratio = _pixel_diff_ratio(before_img, after_click_img)
        assert ratio >= min_change, (
            f"Screenshot did not change enough after click (ratio={ratio:.6f}, min={min_change})."
        )
        if save_artifacts:
            trace.append({"stage": "after_click_validated", "ratio": ratio})
            _write_trace(trace_path, trace)

        run_async(call_tool(server_url, "click_input", {"id": control_id, "name": control_name}))
        run_async(
            call_tool(
                server_url,
                "set_edit_text",
                {"id": control_id, "name": control_name, "text": text, "clear_current_text": True},
            )
        )
        time.sleep(0.3)

        after_type_url = run_async(call_tool(server_url, "capture_window_screenshot", {}))
        after_type_img = _decode_data_url_png(after_type_url)
        if save_artifacts:
            _write_artifact_bytes(
                artifact_dir / f"strict_{run_id}_after_type.png",
                base64.b64decode(after_type_url.split(",", 1)[1]),
            )
            trace.append({"stage": "after_type_screenshot_saved"})
            _write_trace(trace_path, trace)
        type_ratio = _pixel_diff_ratio(after_click_img, after_type_img)
        assert type_ratio >= min_text_change, (
            f"Screenshot did not change enough after typing (ratio={type_ratio:.6f}, min={min_text_change})."
        )
        if save_artifacts:
            trace.append({"stage": "after_type_validated", "ratio": type_ratio})
            _write_trace(trace_path, trace)

        readback = run_async(call_tool(server_url, "texts", {"id": control_id, "name": control_name}))
        assert isinstance(readback, str)
        assert text in readback, "texts() did not contain the written text."
        if save_artifacts:
            _write_artifact_text(artifact_dir / f"strict_{run_id}_readback.txt", readback)
            trace.append({"stage": "readback_saved", "contains_text": text in readback})
            _write_trace(trace_path, trace)

            required = [
                artifact_dir / f"strict_{run_id}_before.png",
                artifact_dir / f"strict_{run_id}_selected_window.json",
                artifact_dir / f"strict_{run_id}_zonui_found.json",
                artifact_dir / f"strict_{run_id}_after_click.png",
                artifact_dir / f"strict_{run_id}_text_control.json",
                artifact_dir / f"strict_{run_id}_after_type.png",
                artifact_dir / f"strict_{run_id}_readback.txt",
                trace_path,
            ]
            missing = [str(path) for path in required if not path.exists()]
            assert not missing, f"Missing strict acceptance artifacts: {missing}"

        if pause_seconds > 0:
            time.sleep(pause_seconds)
    finally:
        close_test_window(launched_handle)
