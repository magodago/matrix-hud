#!/usr/bin/env python3
"""Matrix HUD Server — Serves the agent monitor widget + status API."""

import json
import os
import socket
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

HUD_FILE = os.path.join(os.path.dirname(__file__), 'matrix_hud.html')
STATUS_FILE = os.path.join(os.path.dirname(__file__), 'agent_status.json')
PORT = 3333

# Initial status
initial_status = [
    {"agent": "neo", "status": "idle", "progress": 0, "task": ""},
    {"agent": "morpheus", "status": "working", "progress": 67, "task": "analizando el Matrix..."},
    {"agent": "trinity", "status": "working", "progress": 43, "task": "ejecutando plan de extracción"},
    {"agent": "tank", "status": "working", "progress": 55, "task": "procesando assets 3D"},
    {"agent": "switch", "status": "idle", "progress": 0, "task": ""},
    {"agent": "smith", "status": "idle", "progress": 0, "task": ""},
    {"agent": "oracle", "status": "idle", "progress": 0, "task": ""},
    {"agent": "keymaker", "status": "idle", "progress": 0, "task": ""},
    {"agent": "sati", "status": "idle", "progress": 0, "task": ""},
    {"agent": "mouse", "status": "idle", "progress": 0, "task": ""},
    {"agent": "apoc", "status": "idle", "progress": 0, "task": ""},
]

with open(STATUS_FILE, 'w') as f:
    json.dump(initial_status, f)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == '/' or path == '/index.html':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            with open(HUD_FILE, 'rb') as f:
                self.wfile.write(f.read())
                
        elif path.startswith('/agent-photos/'):
            # Serve agent photos
            filename = os.path.basename(path)
            photo_dir = os.path.join(os.path.dirname(__file__), 'agent-photos')
            photo_path = os.path.join(photo_dir, filename)
            if os.path.exists(photo_path):
                ext = filename.rsplit('.', 1)[-1].lower()
                ctype = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'webp': 'image/webp'}.get(ext, 'image/png')
                self.send_response(200)
                self.send_header('Content-Type', ctype)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Cache-Control', 'max-age=3600')
                self.end_headers()
                with open(photo_path, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b'{"error": "photo not found"}')
                
        elif path == '/status':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            with open(STATUS_FILE, 'r') as f:
                self.wfile.write(f.read().encode())
                
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error": "not found"}')
    
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == '/update':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode()
            
            try:
                updates = json.loads(body)
                if not isinstance(updates, list):
                    updates = [updates]
                
                # Read current status
                with open(STATUS_FILE, 'r') as f:
                    current = json.load(f)
                
                # Apply updates
                for update in updates:
                    agent_id = update.get('agent')
                    existing = [s for s in current if s['agent'] == agent_id]
                    if existing:
                        existing[0].update(update)
                    else:
                        current.append(update)
                
                with open(STATUS_FILE, 'w') as f:
                    json.dump(current, f, indent=2)
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True, "updates": len(updates)}).encode())
                
            except Exception as e:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error": "not found"}')
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
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
    print(f"  Network: http://{ip}:{PORT}")
    print('  Update agent status:')
    print('  curl -X POST http://localhost:%d/update \\' % PORT)
    print("    -H 'Content-Type: application/json' \\")
    print("""    -d '{"agent":"trinity","status":"working","task":"codificando..."}'""")
    print(f"{'='*50}\n")
    
    # Auto-open browser
    try:
        webbrowser.open(f'http://localhost:{PORT}')
    except: pass
    
    server.serve_forever()
