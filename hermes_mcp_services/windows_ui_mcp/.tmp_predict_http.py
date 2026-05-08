import json, traceback, urllib.request
from pathlib import Path

out = {'status': 'running'}
out_path = Path(r'd:\open-source\UFO\hermes_mcp_services\windows_ui_mcp\integration\_artifacts\zonui_predict_direct.json')
out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')

try:
    data = json.dumps({
        'image_path': r'd:\open-source\UFO\hermes_mcp_services\windows_ui_mcp\integration\_artifacts\debug_1778230618_before.png',
        'query': 'File',
    }).encode()
    req = urllib.request.Request('http://localhost:8100/predict', data=data, headers={'Content-Type': 'application/json'})
    resp = urllib.request.urlopen(req, timeout=30)
    out['status'] = 'passed'
    out['response'] = json.loads(resp.read().decode())
except Exception:
    out['status'] = 'failed'
    out['traceback'] = traceback.format_exc()
finally:
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
