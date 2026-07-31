#!/usr/bin/env python3
"""
Matrix Agent Watcher v2 — REALTIME.
Vigila las fuentes REALES de actividad de Hermes:
  - cache/delegation/live/*/manifest.json  (delegaciones de subagentes)
  - ~/.hermes/state.db                     (sesiones telegram/cron/subagent)
Cuando algo cambia → ejecuta sync_agents.py al instante (POST a Render).

CERO tokens. El cron de 1 min (Matrix Agent Monitor) y hud-watchdog.sh
quedan como respaldo si este proceso muere.
"""
import json, sqlite3, subprocess, time
from datetime import datetime
from pathlib import Path

LIVE_DIR = Path("/home/dorti/.hermes/cache/delegation/live")
STATE_DB = Path("/home/dorti/.hermes/state.db")
SYNC = "/home/dorti/matrix-hud/sync_agents.py"
POLL_S = 2.0          # frecuencia de vigilancia
HEARTBEAT_S = 30      # sync mínimo aunque no haya cambios
LOG_FILE = Path("/tmp/matrix_watcher.log")

def log(msg):
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass

def manifest_snapshot():
    """Huella de las delegaciones: dir → mtime máximo de sus archivos
    (task-*.log se actualiza mientras corre; manifest.json al terminar)."""
    snap = {}
    if not LIVE_DIR.exists():
        return snap
    try:
        for d in LIVE_DIR.iterdir():
            if not d.is_dir():
                continue
            max_mt = 0.0
            try:
                for f in d.iterdir():
                    try:
                        max_mt = max(max_mt, f.stat().st_mtime)
                    except Exception:
                        pass
            except Exception:
                pass
            if max_mt > 0:
                snap[d.name] = round(max_mt, 1)
    except Exception:
        pass
    return snap

def sessions_snapshot():
    """Huella de las sesiones recientes. message_count cambia con cada
    tool call → el watcher dispara sync en cada acción de NEO."""
    try:
        con = sqlite3.connect(f"file:{STATE_DB}?mode=ro", uri=True)
        rows = con.execute("""
            SELECT source, title, ended_at, message_count FROM sessions
            WHERE started_at > ? ORDER BY started_at DESC LIMIT 6
        """, (time.time() - 7200,)).fetchall()
        con.close()
        return rows
    except Exception:
        return []

def run_sync(reason=""):
    t0 = time.time()
    try:
        subprocess.run(["python3", SYNC], timeout=20,
                       capture_output=True, check=False)
        log(f"sync ({reason}) {time.time()-t0:.1f}s")
    except Exception as e:
        log(f"sync FAIL ({reason}): {e}")

def main():
    prev_m = manifest_snapshot()
    prev_s = sessions_snapshot()
    last_sync = time.time()
    log(f"watcher v2 iniciado · {len(prev_m)} delegaciones · {len(prev_s)} sesiones")
    run_sync("arranque")  # estado inicial al arrancar
    while True:
        time.sleep(POLL_S)
        m = manifest_snapshot()
        s = sessions_snapshot()
        changed = (m != prev_m) or (s != prev_s)
        if changed:
            log(f"cambio detectado: deleg={len(m)} (antes {len(prev_m)}) ses={len(s)}")
        prev_m, prev_s = m, s
        if changed or (time.time() - last_sync > HEARTBEAT_S):
            last_sync = time.time()
            run_sync("cambio" if changed else "heartbeat")

if __name__ == "__main__":
    main()
