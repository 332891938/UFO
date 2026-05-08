import asyncio
import json
import traceback
from pathlib import Path
from fastmcp import Client

artifact_dir = Path('integration/_artifacts')
artifact_dir.mkdir(parents=True, exist_ok=True)
out = {}

async def main():
    async with Client('http://127.0.0.1:8031/mcp') as client:
        windows = (await client.call_tool('get_desktop_app_info', {'remove_empty': True, 'refresh_app_windows': True})).data
        out['windows_count'] = len(windows)
        target = None
        for w in windows:
            if str(w.get('class_name', '')) == 'Notepad' and 'Notepad' in str(w.get('name', '')):
                target = w
                break
        out['target'] = target
        if target is None:
            return
        selected = (await client.call_tool('select_application_window', {'id': target['id'], 'name': target['name']})).data
        out['selected'] = selected
        try:
            result = (await client.call_tool('find_control_on_screen', {'description': 'File', 'element_type': 'Button'})).data
            out['find_result'] = result
        except Exception:
            out['find_error'] = traceback.format_exc()

asyncio.run(main())
(artifact_dir / 'direct_find_result.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
