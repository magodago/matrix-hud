#!/usr/bin/env python3
"""Sincroniza estado REAL de agentes Matrix → HUD en Render
   Solo agentes que EXISTEN con procesos/scripts activos.
   Métricas 100% reales extraídas del sistema."""
import json, os, subprocess, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

HUD_URL = "https://matrix-hud.onrender.com/update"
STATUS_FILE = Path("/home/dorti/matrix-hud/agent_status.json")
BOT_STATUS = Path("/tmp/neo-trading-bot/bot_status.json")
LOG_FILE = Path("/tmp/matrix_sync.log")

def log(msg):
    with open(LOG_FILE, "a") as f:
        f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")

def get_scalper_data():
    """Datos reales del scalper NEO"""
    try:
        with open(BOT_STATUS) as f:
            d = json.load(f)
        cfg = d.get("cfg", {})
        perf = d.get("perf", {})
        closes = d.get("close_prices", [])
        bb_lower = d.get("bb_lower", 0)
        bb_upper = d.get("bb_upper", 0)
        bb_mid = d.get("bb_mid", 0)
        last_price = d.get("last_price", 0)
        entry_pct = ""
        if bb_mid and last_price:
            if last_price <= bb_lower:
                entry_pct = "⬇ FIBRA INF"
            elif last_price >= bb_upper:
                entry_pct = "⬆ FIBRA SUP"
            else:
                pct_from_mid = ((last_price - bb_mid) / bb_mid) * 100
                entry_pct = f"{'↗' if pct_from_mid > 0 else '↘'} {abs(pct_from_mid):.1f}%"
        return {
            "capital": d.get("capital", 0),
            "pnl": d.get("total_pnl", 0),
            "trades": perf.get("wins", 0) + perf.get("losses", 0),
            "wins": perf.get("wins", 0),
            "losses": perf.get("losses", 0),
            "win_rate": perf.get("win_rate", 0),
            "signal": d.get("signal", "WAIT"),
            "rsi": d.get("rsi", "--"),
            "btc": d.get("last_price", 0),
            "velas": len(closes),
            "entry_zone": entry_pct,
            "bb": f"{bb_lower:.0f}/{bb_mid:.0f}/{bb_upper:.0f}",
            "last_update": d.get("last_updated", ""),
        }
    except Exception as e:
        log(f"  ✗ Error leyendo scalper: {e}")
        return None

def is_process_running(name_filter):
    """Verifica si un proceso con ese nombre está vivo"""
    try:
        result = subprocess.run(["pgrep", "-f", name_filter], capture_output=True, timeout=5)
        return result.returncode == 0
    except:
        return False

def get_uptime(pid):
    """Obtiene uptime de un proceso en segundos"""
    try:
        with open(f"/proc/{pid}/stat") as f:
            data = f.read()
            parts = data.split()
            start_ticks = int(parts[21])
            uptime_sec = os.times()[4] * 100  # approx
            clock_ticks = os.sysconf(os.sysconf_names['SC_CLK_TCK'])
            return int((time.time() - (start_ticks / clock_ticks)))
    except:
        return 0

def build_agents():
    """Construye estado REAL de agentes"""
    now = datetime.now(timezone.utc)
    agents = []
    
    # === NEO — SCALPER REAL ===
    scalper = get_scalper_data()
    neo_running = is_process_running("scalper.py")
    if neo_running and scalper:
        pnl_pct = (scalper["pnl"] / scalper["capital"]) * 100 if scalper["capital"] > 0 else 0
        task_parts = []
        if scalper["trades"] > 0:
            task_parts.append(f"{scalper['trades']} trades")
            task_parts.append(f"{scalper['win_rate']*100:.0f}% WR")
        task_parts.append(f"RSI {scalper['rsi']}")
        task_parts.append(f"{scalper['velas']} velas")
        task_parts.append(scalper["entry_zone"])
        task = " · ".join(task_parts) if task_parts else "ARRANCANDO..."
        
        # Progreso hacia +10%
        progress = min(100, int((scalper["capital"] + scalper["pnl"] - 100) / 10 * 100))
        if progress < 0: progress = 0
        
        agents.append({
            "agent": "neo",
            "status": "working",
            "progress": progress,
            "task": f"${scalper['btc']:.0f} {scalper['signal']} | {task}",
            "subtitle": f"€{scalper['capital']+scalper['pnl']:.2f} ({pnl_pct:+.2f}%)"
        })
    else:
        agents.append({"agent": "neo", "status": "idle", "progress": 0, "task": "OFFLINE", "subtitle": ""})
    
    # === APOC — WATCHDOG + MONITOR ===
    apoc_running = is_process_running("matrix_monitor.sh") or is_process_running("sync_agents")
    if apoc_running:
        agents.append({
            "agent": "apoc",
            "status": "working",
            "progress": 100,
            "task": f"WATCHDOG · heartbeat {now.strftime('%H:%M')}",
            "subtitle": "sistemas nominales"
        })
    else:
        agents.append({"agent": "apoc", "status": "idle", "progress": 0, "task": "SIN HEARTBEAT", "subtitle": ""})
    
    # === KEYMAKER — STRATEGY OPTIMIZER ===
    opt_running = is_process_running("strategy-optimizer")
    if opt_running:
        agents.append({
            "agent": "keymaker",
            "status": "working",
            "progress": 100,
            "task": "OPTIMIZADOR c/30min",
            "subtitle": "ajuste automático TP/SL"
        })
    else:
        agents.append({"agent": "keymaker", "status": "idle", "progress": 0, "task": "INACTIVO", "subtitle": ""})
    
    # === SATI — HUD EN RENDER ===
    # Verificar que Render responde
    try:
        r = urllib.request.urlopen("https://matrix-hud.onrender.com/", timeout=5)
        sati_online = r.status == 200
    except:
        sati_online = False
    
    if sati_online:
        agents.append({
            "agent": "sati",
            "status": "working",
            "progress": 100,
            "task": "HUD EN VIVO RENDER",
            "subtitle": f"{now.strftime('%H:%M:%S')} · online"
        })
    else:
        agents.append({"agent": "sati", "status": "idle", "progress": 0, "task": "OFFLINE", "subtitle": ""})
    
    return agents

def main():
    agents = build_agents()
    log(f"Sync: {len(agents)} agentes reales | NEO={'🟢' if agents[0]['status']=='working' else '🔴'}")
    
    # Guardar local
    with open(STATUS_FILE, "w") as f:
        json.dump(agents, f)
    
    # Pushear a Render
    try:
        data = json.dumps(agents).encode()
        req = urllib.request.Request(HUD_URL, data=data,
            headers={"Content-Type": "application/json", "User-Agent": "matrix-sync"})
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read())
        log(f"Render: {result}")
    except Exception as e:
        log(f"Render error: {e}")

if __name__ == "__main__":
    main()
