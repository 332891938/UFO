# Linux MCP Service

Standalone Linux MCP server extracted for Hermes integration.

## Features
- Execute allow-listed shell commands (`execute_command`)
- Read basic Linux system info (`get_system_info`)
- API key protection via `UFO_MCP_API_KEY`

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export UFO_MCP_API_KEY="your-secret-key"
```

## Run
```bash
python server.py --host localhost --port 8010
```

## Notes
- This service is intended for Linux hosts.
- Commands are restricted by an allow-list and dangerous pattern checks.
