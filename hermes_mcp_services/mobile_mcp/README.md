# Mobile MCP Service

Standalone Android MCP service extracted for Hermes integration.

## Features
Data server (default `8020`):
- `capture_screenshot`
- `get_ui_tree`
- `get_device_info`
- `get_mobile_app_target_info`
- `get_app_window_controls_target_info`

Action server (default `8021`):
- `tap`
- `swipe`
- `type_text`
- `launch_app`
- `press_key`
- `click_control`
- `wait`
- `invalidate_cache`

## Requirements
- Android device or emulator
- ADB installed and available in `PATH`

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
adb devices
```

## Run
```bash
python server.py --server both --host localhost --data-port 8020 --action-port 8021
```

## Notes
- `both` mode runs data/action servers in one process to share cache state.
