#!/usr/bin/env python3
"""
Matrix Agent Watcher — Daemon de fondo que actualiza el HUD cada 2s.
CERO tokens — solo scripts, sin LLM.
"""
import json, subprocess, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

HUD_URL = "https://matrix-hud.onrender.com/update"
TASK_FILE = Path("/tmp/matrix_agent_tasks.json")
LOG_FILE = Path("/tmp/matrix_watcher.log")

log_fh = open(LOG_FILE, "a", buffering=1)
def log(msg):
    t = datetime.now().strftime("%H:%M:%S")
    log_fh.write(f"[{t}] {msg}\n")
    log_fh.flush()

def read_tasks():
    try:
        with open(TASK_FILE) as f:
            return json.load(f)
    except: return {}

def build_status():
    tasks = read_tasks()
    agents = []

    # === NEO (yo — el agente) ===
    agents.append({"agent": "neo", "status": "idle", "progress": 0,
                   "task": "ONLINE", "subtitle": ""})

    # === AGENTES DELEGABLES ===
    agent_list = ["morpheus", "trinity", "tank", "switch", "smith", "oracle", "keymaker", "sati", "mouse", "apoc"]
    for aid in agent_list:
        t = tasks.get(aid, {})
        if t.get("status") == "working":
            agents.append({
                "agent": aid, "status": "working",
                "progress": t.get("progress", 50),
                "task": t.get("task", "TRABAJANDO..."),
                "subtitle": t.get("subtitle", "")
            })
        else:
            agents.append({
                "agent": aid, "status": "idle", "progress": 0,
                "task": "", "subtitle": ""
            })

    return agents

def read_token_data():
    """Lee cache de tokens si existe"""
    try:
        with open("/tmp/matrix_token_cache.json") as f:
            return json.load(f)
    except:
        return None

def main():
    log("Watcher iniciado")
    while True:
        try:
            agents = build_status()
            data = json.dumps(agents).encode()
            req = urllib.request.Request(HUD_URL, data=data,
                headers={"Content-Type": "application/json"})
            resp = urllib.request.urlopen(req, timeout=5)
            result = json.loads(resp.read())
            working = sum(1 for a in agents if a["status"] == "working")
            log(f"📤 {working}/11 working → {result}")

            # Token data si existe cache
            token_data = read_token_data()
            if token_data:
                td = json.dumps(token_data).encode()
                treq = urllib.request.Request(f"{HUD_URL.replace('/update', '/token-update')}",
                    data=td, headers={"Content-Type": "application/json"})
                urllib.request.urlopen(treq, timeout=5)
        except Exception as e:
            log(f"✗ {e}")
        time.sleep(2)

if __name__ == "__main__":
    main()
