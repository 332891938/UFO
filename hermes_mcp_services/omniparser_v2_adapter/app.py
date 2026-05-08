#!/usr/bin/env python3

import argparse
import ast
import base64
import io
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import gradio as gr
from gradio_client import Client, handle_file
from PIL import Image


DEFAULT_OFFICIAL_API_NAME = "/process"


class OfficialOmniParserProxy:
    def __init__(self, endpoint: str, api_name: str = DEFAULT_OFFICIAL_API_NAME):
        self.endpoint = endpoint
        self.api_name = api_name
        self.client = Client(endpoint)

    def predict(
        self,
        image_path: str,
        box_threshold: float,
        iou_threshold: float,
        use_paddleocr: bool,
        imgsz: int,
    ) -> Any:
        return self.client.predict(
            image_input=handle_file(filepath_or_url=image_path),
            box_threshold=box_threshold,
            iou_threshold=iou_threshold,
            use_paddleocr=use_paddleocr,
            imgsz=imgsz,
            api_name=self.api_name,
        )


def _image_size(image_path: str) -> Tuple[int, int]:
    with Image.open(image_path) as image:
        return image.size


def _normalize_number(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_bbox(raw_bbox: Any, image_size: Tuple[int, int]) -> List[float]:
    width, height = image_size

    if isinstance(raw_bbox, str):
        try:
            raw_bbox = json.loads(raw_bbox)
        except json.JSONDecodeError:
            raw_bbox = ast.literal_eval(raw_bbox)

    if isinstance(raw_bbox, dict):
        if {"x0", "y0", "x1", "y1"}.issubset(raw_bbox.keys()):
            values = [
                raw_bbox["x0"],
                raw_bbox["y0"],
                raw_bbox["x1"],
                raw_bbox["y1"],
            ]
        elif {"x", "y", "w", "h"}.issubset(raw_bbox.keys()):
            values = [
                raw_bbox["x"],
                raw_bbox["y"],
                raw_bbox["x"] + raw_bbox["w"],
                raw_bbox["y"] + raw_bbox["h"],
            ]
        else:
            values = [0, 0, 0, 0]
    elif isinstance(raw_bbox, (list, tuple)) and len(raw_bbox) >= 4:
        values = list(raw_bbox[:4])
    else:
        values = [0, 0, 0, 0]

    coords = [(_normalize_number(value) or 0.0) for value in values]
    if max(coords) > 1.5:
        return [
            max(0.0, min(1.0, coords[0] / max(width, 1))),
            max(0.0, min(1.0, coords[1] / max(height, 1))),
            max(0.0, min(1.0, coords[2] / max(width, 1))),
            max(0.0, min(1.0, coords[3] / max(height, 1))),
        ]

    return [max(0.0, min(1.0, value)) for value in coords]


def _normalize_detection(item: Dict[str, Any], image_size: Tuple[int, int]) -> Dict[str, Any]:
    return {
        "bbox": _normalize_bbox(
            item.get("bbox")
            or item.get("box")
            or item.get("rect")
            or item.get("bounding_box")
            or [0, 0, 0, 0],
            image_size,
        ),
        "content": (
            item.get("content")
            or item.get("text")
            or item.get("label")
            or item.get("name")
            or item.get("caption")
            or ""
        ),
        "type": (
            item.get("type")
            or item.get("control_type")
            or item.get("category")
            or item.get("cls")
            or item.get("class")
            or "Button"
        ),
        "interactivity": bool(
            item.get("interactivity", item.get("interactive", item.get("clickable", True)))
        ),
    }


def _try_parse_dict_line(line: str) -> Optional[Dict[str, Any]]:
    line = line.strip()
    if not line:
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        pass
    try:
        start = line.index("{")
        end = line.rindex("}") + 1
        return ast.literal_eval(line[start:end])
    except Exception:
        return None


def _iter_candidate_items(payload: Any) -> Iterable[Any]:
    if isinstance(payload, dict):
        for key in (
            "parsed_content_list",
            "parsed_content",
            "detections",
            "elements",
            "results",
            "data",
        ):
            if key in payload:
                yield payload[key]
        yield payload
        return

    if isinstance(payload, (list, tuple)):
        for item in payload:
            yield item
        return

    yield payload


def _extract_detection_items(payload: Any) -> List[Dict[str, Any]]:
    detections: List[Dict[str, Any]] = []

    for candidate in _iter_candidate_items(payload):
        if isinstance(candidate, str):
            for line in candidate.splitlines():
                parsed = _try_parse_dict_line(line)
                if isinstance(parsed, dict):
                    detections.append(parsed)
        elif isinstance(candidate, dict):
            if any(key in candidate for key in ("bbox", "box", "rect", "bounding_box")):
                detections.append(candidate)
        elif isinstance(candidate, list):
            for item in candidate:
                if isinstance(item, dict):
                    detections.append(item)
                elif isinstance(item, str):
                    parsed = _try_parse_dict_line(item)
                    if isinstance(parsed, dict):
                        detections.append(parsed)

    return detections


def _decode_base64_image(value: str) -> Optional[Image.Image]:
    if not isinstance(value, str) or not value:
        return None

    try:
        raw = value.split(",", 1)[1] if "," in value else value
        return Image.open(io.BytesIO(base64.b64decode(raw)))
    except Exception:
        return None


def _extract_preview_image(payload: Any) -> Optional[Image.Image]:
    if isinstance(payload, Image.Image):
        return payload

    if isinstance(payload, str):
        if payload.startswith("data:image/"):
            return _decode_base64_image(payload)
        if Path(payload).exists():
            return Image.open(payload)
        return None

    if isinstance(payload, dict):
        for key in ("som_image_base64", "image_base64", "annotated_image", "image"):
            if key in payload:
                preview = _extract_preview_image(payload[key])
                if preview is not None:
                    return preview
        return None

    if isinstance(payload, (list, tuple)):
        for item in payload:
            preview = _extract_preview_image(item)
            if preview is not None:
                return preview

    return None


def _serialize_detections(detections: List[Dict[str, Any]]) -> str:
    return "\n".join(json.dumps(item, ensure_ascii=True) for item in detections)


def create_adapter(
    official_endpoint: str,
    official_api_name: str = DEFAULT_OFFICIAL_API_NAME,
) -> gr.Blocks:
    proxy = OfficialOmniParserProxy(official_endpoint, official_api_name)

    def process(
        image_input: str,
        box_threshold: float = 0.05,
        iou_threshold: float = 0.1,
        use_paddleocr: bool = True,
        imgsz: int = 640,
    ):
        if not image_input:
            return None, ""

        image_size = _image_size(image_input)
        official_output = proxy.predict(
            image_input,
            box_threshold=box_threshold,
            iou_threshold=iou_threshold,
            use_paddleocr=use_paddleocr,
            imgsz=imgsz,
        )
        preview_image = _extract_preview_image(official_output)
        detections = [
            _normalize_detection(item, image_size)
            for item in _extract_detection_items(official_output)
        ]
        return preview_image, _serialize_detections(detections)

    with gr.Blocks(title="OmniParser v2 Adapter") as demo:
        gr.Markdown(
            "OmniParser v2 adapter for windows_ui_mcp. "
            "It proxies the official OmniParser Gradio endpoint and reformats "
            "the output into newline-delimited JSON."
        )
        with gr.Row():
            image_input = gr.File(label="Input Screenshot", type="filepath")
            preview_output = gr.Image(label="Annotated Preview")
        box_threshold = gr.Slider(
            label="Box Threshold", minimum=0.01, maximum=1.0, step=0.01, value=0.05
        )
        iou_threshold = gr.Slider(
            label="IOU Threshold", minimum=0.01, maximum=1.0, step=0.01, value=0.1
        )
        use_paddleocr = gr.Checkbox(label="Use PaddleOCR", value=True)
        imgsz = gr.Slider(label="Image Size", minimum=320, maximum=1600, step=32, value=640)
        parsed_output = gr.Textbox(
            label="Normalized Parsed Output",
            lines=16,
            show_copy_button=True,
        )
        run_button = gr.Button("Process")
        run_button.click(
            process,
            inputs=[image_input, box_threshold, iou_threshold, use_paddleocr, imgsz],
            outputs=[preview_output, parsed_output],
            api_name="process",
        )

    return demo


def main() -> None:
    parser = argparse.ArgumentParser(description="OmniParser v2 adapter for windows_ui_mcp")
    parser.add_argument("--host", default=os.environ.get("ADAPTER_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("ADAPTER_PORT", "7861")))
    parser.add_argument(
        "--official-endpoint",
        default=os.environ.get("OFFICIAL_OMNIPARSER_ENDPOINT", ""),
        help="Official OmniParser Gradio endpoint, e.g. http://127.0.0.1:7860",
    )
    parser.add_argument(
        "--official-api-name",
        default=os.environ.get("OFFICIAL_OMNIPARSER_API_NAME", DEFAULT_OFFICIAL_API_NAME),
        help="API name exposed by the official OmniParser service.",
    )
    args = parser.parse_args()

    if not args.official_endpoint:
        raise SystemExit(
            "Missing official OmniParser endpoint. Pass --official-endpoint or set "
            "OFFICIAL_OMNIPARSER_ENDPOINT."
        )

    app = create_adapter(
        official_endpoint=args.official_endpoint,
        official_api_name=args.official_api_name,
    )
    app.launch(server_name=args.host, server_port=args.port, show_api=True)


if __name__ == "__main__":
    main()
