#!/usr/bin/env python3
"""
Matrix Agent Watcher — Daemon de fondo que actualiza el HUD cada 10s.
CERO tokens — solo scripts, sin LLM.
"""
import json, os, subprocess, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

HUD_URL = "https://matrix-hud.onrender.com/update"
BOT_STATUS = Path("/tmp/neo-trading-bot/bot_status.json")
TASK_FILE = Path("/tmp/matrix_agent_tasks.json")
LOG_FILE = Path("/tmp/matrix_watcher.log")
TOKEN_TRACKER = Path("/home/dorti/matrix-hud/token_tracker.py")
TOKEN_CACHE = Path("/tmp/matrix_token_cache.json")

log_fh = open(LOG_FILE, "a", buffering=1)
def log(msg):
    t = datetime.now().strftime("%H:%M:%S")
    log_fh.write(f"[{t}] {msg}\n")
    log_fh.flush()

def is_running(name_filter):
    try:
        r = subprocess.run(["pgrep", "-f", name_filter], capture_output=True, timeout=3)
        return r.returncode == 0
    except: return False

def read_tasks():
    """Lee tareas activas de agentes (las que YO escribo al delegar)"""
    try:
        with open(TASK_FILE) as f:
            return json.load(f)
    except: return {}

def write_agent(agent_id, status, task="", progress=0, subtitle=""):
    """Escribe estado de un agente en el archivo de tareas"""
    tasks = read_tasks()
    tasks[agent_id] = {
        "status": status,
        "task": task,
        "progress": progress,
        "subtitle": subtitle,
        "updated": datetime.now(timezone.utc).isoformat()
    }
    with open(TASK_FILE, "w") as f:
        json.dump(tasks, f, indent=2)

def build_status():
    """Construye estado de TODOS los agentes"""
    tasks = read_tasks()
    now = datetime.now(timezone.utc)
    agents = []

    # === NEO (scalper) — siempre corre, datos reales ===
    try:
        with open(BOT_STATUS) as f:
            d = json.load(f)
        cap = d.get("capital", 100)
        pnl = d.get("total_pnl", 0)
        total = cap + pnl
        pnl_pct = (pnl / cap) * 100 if cap > 0 else 0
        btc = d.get("last_price", 0)
        sig = d.get("signal", "WAIT")
        rsi = d.get("rsi", "--")
        velas = len(d.get("close_prices", []))
        trades = d.get("total_trades", 0)
        progress = max(0, min(100, int((total - 100) / 10 * 100)))
        task = f"${btc:.0f} {sig} | RSI {rsi} · {velas}v"
        agents.append({
            "agent": "neo", "status": "working", "progress": progress,
            "task": task, "subtitle": f"€{total:.2f} ({pnl_pct:+.2f}%)"
        })
    except:
        agents.append({"agent": "neo", "status": "idle", "progress": 0, "task": "OFFLINE", "subtitle": ""})

    # === AGENTES DELEGABLES (todos los demás) ===
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
            # Si no hay tarea activa, idle
            agents.append({
                "agent": aid, "status": "idle", "progress": 0,
                "task": "", "subtitle": ""
            })

    return agents

def read_token_data():
    """Ejecuta token_tracker.py y devuelve los datos cacheados"""
    try:
        # Ejecutar tracker (rápido, solo query SQLite)
        subprocess.run(["/usr/bin/python3", str(TOKEN_TRACKER)], capture_output=True, timeout=10)
        with open(TOKEN_CACHE) as f:
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

            # También POSTear datos de tokens
            token_data = read_token_data()
            if token_data:
                td = json.dumps(token_data).encode()
                treq = urllib.request.Request(f"{HUD_URL.replace('/update', '/token-update')}",
                    data=td, headers={"Content-Type": "application/json"})
                tresp = urllib.request.urlopen(treq, timeout=5)
                tlog = json.loads(tresp.read())
                today = token_data.get("today", {})
                if "error" not in today:
                    log(f"💰 Tokens: ${today.get('cost_total', 0):.4f} ({today.get('session_count', 0)} sesiones)")
        except Exception as e:
            log(f"✗ {e}")
        time.sleep(2)

if __name__ == "__main__":
    main()
