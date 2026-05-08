# OmniParser v2 Adapter

This is a minimal adapter service that proxies the official
[`microsoft/OmniParser`](https://github.com/microsoft/OmniParser) Gradio endpoint
and reformats its output into the structure expected by
`hermes_mcp_services/windows_ui_mcp`.

## Why This Exists

`windows_ui_mcp` currently calls OmniParser like this:

- Gradio endpoint
- API name: `/process`
- inputs:
  - `image_input`
  - `box_threshold`
  - `iou_threshold`
  - `use_paddleocr`
  - `imgsz`

And it expects the result shape to behave like:

```python
results = client.predict(...)
parsed_lines = results[1].splitlines()
```

Where each line is a JSON object like:

```json
{"bbox":[0.1,0.2,0.3,0.4],"content":"Save","type":"Button","interactivity":true}
```

This adapter normalizes the official OmniParser output into that format.

## Files

- `app.py`: Gradio adapter service
- `requirements.txt`: minimal dependencies

## Setup

```powershell
cd d:\open-source\UFO\hermes_mcp_services\omniparser_v2_adapter
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Run

Point the adapter to the official OmniParser service:

```powershell
$env:OFFICIAL_OMNIPARSER_ENDPOINT="http://127.0.0.1:7860"
python app.py --host 0.0.0.0 --port 7861
```

Optional:

```powershell
$env:OFFICIAL_OMNIPARSER_API_NAME="/process"
```

## Connect From `windows_ui_mcp`

Set:

```powershell
$env:HERMES_OMNIPARSER_ENDPOINT="http://127.0.0.1:7861"
```

Then start:

```powershell
cd d:\open-source\UFO\hermes_mcp_services\windows_ui_mcp
python server.py --host localhost --port 8030
```

## Validation

You can validate OmniParser integration with:

```powershell
$env:HERMES_RUN_REAL_TESTS="1"
$env:HERMES_TEST_SERVER_URL="http://localhost:8030/mcp"
$env:HERMES_TEST_UI_APP="notepad.exe"
$env:HERMES_TEST_UI_WINDOW_KEYWORD="Notepad"
$env:HERMES_OMNIPARSER_ENDPOINT="http://127.0.0.1:7861"
python -m pytest integration/test_mcp_e2e_real.py -k omniparser -s
```

## Notes

- The adapter keeps the input side close to the official OmniParser Gradio demo.
- The output side is normalized for the current `windows_ui_mcp` parser.
- If the official OmniParser output changes in the future, only this adapter should need updates.
