#!/usr/bin/env python3
"""Matrix HUD Server — Serves agent monitor + status API.
Deployable on Render.com or localhost."""
import json, os, socket
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

BASE = os.path.dirname(os.path.abspath(__file__))
HUD_FILE = os.path.join(BASE, 'matrix_hud.html')
STATUS_FILE = os.path.join(BASE, 'agent_status.json')
PORT = int(os.environ.get('PORT', 3333))

# Initial status
initial_status = [
    {"agent": "neo", "status": "idle", "progress": 0, "task": ""},
    {"agent": "morpheus", "status": "idle", "progress": 0, "task": ""},
    {"agent": "trinity", "status": "idle", "progress": 0, "task": ""},
    {"agent": "tank", "status": "idle", "progress": 0, "task": ""},
    {"agent": "switch", "status": "idle", "progress": 0, "task": ""},
    {"agent": "smith", "status": "idle", "progress": 0, "task": ""},
    {"agent": "oracle", "status": "idle", "progress": 0, "task": ""},
    {"agent": "keymaker", "status": "idle", "progress": 0, "task": ""},
    {"agent": "sati", "status": "idle", "progress": 0, "task": ""},
    {"agent": "apoc", "status": "idle", "progress": 0, "task": ""},
]

if not os.path.exists(STATUS_FILE):
    with open(STATUS_FILE, 'w') as f:
        json.dump(initial_status, f)

CORS_HEADERS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == '/' or path == '/index.html':
            if os.path.exists(HUD_FILE):
                self._serve_file(HUD_FILE, 'text/html; charset=utf-8')
            else:
                self._json(404, {"error": "HUD file not found"})
        elif path.startswith('/agent-photos/'):
            filename = os.path.basename(path)
            photo_dir = os.path.join(BASE, 'agent-photos')
            photo_path = os.path.join(photo_dir, filename)
            if os.path.exists(photo_path):
                ext = filename.rsplit('.', 1)[-1].lower()
                ctype = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'webp': 'image/webp'}.get(ext, 'image/png')
                self._serve_file(photo_path, ctype)
            else:
                self._json(404, {"error": "photo not found"})
        elif path == '/status':
            self._serve_file(STATUS_FILE, 'application/json')
        else:
            self._json(404, {"error": "not found"})
    
    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == '/update':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode() if content_length else '{}'
            try:
                updates = json.loads(body)
                if not isinstance(updates, list):
                    updates = [updates]
                with open(STATUS_FILE, 'r') as f:
                    current = json.load(f)
                for update in updates:
                    agent_id = update.get('agent')
                    existing = [s for s in current if s['agent'] == agent_id]
                    if existing:
                        existing[0].update(update)
                    else:
                        current.append(update)
                with open(STATUS_FILE, 'w') as f:
                    json.dump(current, f, indent=2)
                self._json(200, {"ok": True, "updates": len(updates)})
            except Exception as e:
                self._json(400, {"error": str(e)})
        else:
            self._json(404, {"error": "not found"})
    
    def do_OPTIONS(self):
        self.send_response(200)
        for k, v in CORS_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
    
    def _serve_file(self, path, content_type):
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        for k, v in CORS_HEADERS.items():
            self.send_header(k, v)
        if 'image' not in content_type:
            self.send_header('Cache-Control', 'no-cache')
        else:
            self.send_header('Cache-Control', 'max-age=3600')
        self.end_headers()
        with open(path, 'rb') as f:
            self.wfile.write(f.read())
    
    def _json(self, code, data):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        for k, v in CORS_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def log_message(self, format, *args):
        print(f"[HUD] {args[0]} {args[1]} {args[2]}")

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.254.254.254', 1))
        ip = s.getsockname()[0]
    except: ip = '127.0.0.1'
    finally: s.close()
    return ip

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', PORT), Handler)
    ip = get_local_ip()
    print(f"\n{'='*50}")
    print(f"  MATRIX HUD SERVER")
    print(f"{'='*50}")
    print(f"  Local:   http://localhost:{PORT}")
    if ip != '127.0.0.1':
        print(f"  Network: http://{ip}:{PORT}")
    print(f"  To update agent status:")
    print(f"  curl -X POST http://localhost:{PORT}/update \\")
    print(f"    -H 'Content-Type: application/json' \\")
    print(f"    -d '{{\"agent\":\"trinity\",\"status\":\"working\",\"task\":\"codificando...\",\"progress\":42}}'")
    print(f"{'='*50}\n")
    server.serve_forever()
