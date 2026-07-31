#!/usr/bin/env python3
"""sync_agents.py v2 — Estado REAL de NEO + subagentes Hermes → Matrix HUD.

v2: los perfiles Matrix son los ROLES de delegación de NEO. El HUD se alimenta
de ~/.hermes/state.db: cuando NEO delega tareas a subagentes, cada delegación
se clasifica por keywords y se asigna al perfil Matrix correspondiente.

Fuentes 100% reales:
  - sessions source='telegram'  → NEO (agente principal, sesión activa)
  - sessions source='subagent'  → delegaciones activas/recientes
  - sessions source='cron'      → trabajos programados (Keymaker/Apoc)
  - procesos del sistema        → watchdog (Apoc)
"""
import json, os, re, sqlite3, subprocess, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

HUD_URL = "https://matrix-hud.onrender.com/update"
STATUS_FILE = Path("/home/dorti/matrix-hud/agent_status.json")
STATE_DB = Path("/home/dorti/.hermes/state.db")
LOG_FILE = Path("/tmp/matrix_sync.log")

# Keywords → perfil Matrix (roles de delegación reales de NEO)
ROLE_KEYWORDS = {
    "morpheus": ["plan", "arquitect", "estrateg", "roadmap", "spec", "planificar", "architecture", "design the solution", "diseñar la solución"],
    "trinity":  ["cod", "implement", "script", "python", "javascript", "html", "función", "function", "feature", "refactor", "api", "backend", "frontend", "módulo", "modulo", "build", "crear", "crea"],
    "smith":    ["review", "test", "qa", "bug", "validar", "verificar", "audit", "debug", "revisar", "testing"],
    "oracle":   ["investig", "research", "analiz", "dato", "mercado", "estudio", "búsqueda", "busqueda", "informe", "benchmark", "report"],
    "sati":     ["diseño", "diseño", "ui", "ux", "css", "landing", "visual", "branding", "web", "página", "pagina", "design"],
    "tank":     ["render", "3d", "blender", "vídeo", "video", "procesamiento", "imagen", "pesado", "comfyui"],
    "switch":   ["consulta", "pregunta", "resumen", "quick", "lookup", "resumir"],
    "keymaker": ["automat", "pipeline", "cron", "scraper", "integración", "integracion", "deploy", "infra", "script shell", "workflow"],
    "mouse":    ["prototipo", "spike", "experimento", "prueba de concepto", "proof of concept", "prueba rápida"],
}

ALL_ROLES = ["morpheus", "trinity", "smith", "oracle", "sati", "tank", "switch", "keymaker", "mouse"]

def log(msg):
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass

def now_ts():
    return time.time()

def classify_role(title):
    """Clasifica una tarea de subagente → perfil Matrix."""
    t = (title or "").lower()
    for role, kws in ROLE_KEYWORDS.items():
        for kw in kws:
            if kw in t:
                return role
    # Fallback: subagentes de review/código genéricos
    if re.search(r"\b(código|code|app|web|site|página)\b", t):
        return "trinity"
    return "mouse"  # experimento/comodín por defecto

def is_process_running(name_filter):
    try:
        r = subprocess.run(["pgrep", "-f", name_filter], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False

def query_db(sql, params=()):
    if not STATE_DB.exists():
        return []
    try:
        con = sqlite3.connect(str(STATE_DB))
        con.row_factory = sqlite3.Row
        rows = con.execute(sql, params).fetchall()
        con.close()
        return rows
    except Exception as e:
        log(f"DB error: {e}")
        return []

def get_neo_state():
    """NEO = sesión activa con David (telegram) o cron corriendo."""
    cutoff = now_ts() - 6 * 3600
    # Sesión telegram activa más reciente
    rows = query_db("""
        SELECT title, started_at, model, message_count FROM sessions
        WHERE source='telegram' AND ended_at IS NULL AND started_at > ?
        ORDER BY started_at DESC LIMIT 1
    """, (cutoff,))
    if rows:
        r = rows[0]
        model = r["model"] or "deepseek-v4-flash"
        task = r["title"] or "Sesión activa"
        return {"status": "working", "progress": 100, "task": task[:80],
                "subtitle": model.upper().replace("-", " ")[:24]}
    # Cron corriendo ahora mismo
    rows = query_db("""
        SELECT title FROM sessions
        WHERE source='cron' AND ended_at IS NULL AND started_at > ?
        ORDER BY started_at DESC LIMIT 1
    """, (now_ts() - 3600,))
    if rows:
        return {"status": "working", "progress": 75,
                "task": ("⏳ " + (rows[0]["title"] or "cron activo"))[:80],
                "subtitle": "DEEPSEEK V4 FLASH"}
    return {"status": "idle", "progress": 0, "task": "ONLINE", "subtitle": "DEEPSEEK V4 FLASH"}

def get_delegation_goal(session_id):
    """Lee el goal REAL de una delegación activa desde el live transcript
    (más fiable que el título de state.db, que se rellena al terminar)."""
    live_dir = Path("/home/dorti/.hermes/cache/delegation/live")
    try:
        if live_dir.exists():
            for tdir in live_dir.iterdir():
                if not tdir.is_dir():
                    continue
                for logf in tdir.glob("task-*.log"):
                    head = logf.read_text(errors="ignore")[:400]
                    for line in head.splitlines():
                        if line.startswith("goal:"):
                            return line[5:].strip()[:120]
    except Exception:
        pass
    return None

def get_live_delegations():
    """Delegaciones detectadas por live transcripts en cache/delegation/live/.
    Lee manifest.json de cada una: tasks running = trabajando AHORA,
    tasks completed hace <45 min = done reciente. Devuelve (working, done)."""
    live_dir = Path("/home/dorti/.hermes/cache/delegation/live")
    working, done = [], []
    if not live_dir.exists():
        return working, done
    now = time.time()
    try:
        for tdir in live_dir.iterdir():
            if not tdir.is_dir():
                continue
            mf = tdir / "manifest.json"
            if not mf.exists():
                continue
            try:
                m = json.loads(mf.read_text(errors="ignore"))
            except Exception:
                continue
            tasks = m.get("tasks", [])
            for t in tasks:
                goal = (t.get("goal") or "")[:120]
                if not goal:
                    continue
                st = t.get("status", "")
                if st == "running" or (not m.get("completed") and st != "completed"):
                    working.append(goal)
                elif st == "completed":
                    done.append(goal)
            # Tolerancia: delegación que acaba de terminar (sin 'completed' aún)
            if not m.get("completed"):
                # puede seguir corriendo: el manifest se escribe al final
                try:
                    if now - tdir.stat().st_mtime > 120:
                        continue
                except Exception:
                    pass
    except Exception as e:
        log(f"live delegations error: {e}")
    return working, done

def get_subagents_state():
    """Delegaciones de subagentes activas o terminadas hace <45 min.
    Prioridad: live transcripts (activas AHORA) > state.db (recientes)."""
    # 1) Trabajando AHORA (manifest.json de delegaciones vivas)
    live_working, live_done = get_live_delegations()
    live_roles = {}
    for goal in live_working:
        role = classify_role(goal)
        live_roles[role] = {
            "status": "working",
            "progress": 100,
            "task": goal[:70],
            "subtitle": "en marcha · tiempo real",
        }

    # 2) Recientes desde state.db (para mostrar 'done')
    cutoff = now_ts() - 3 * 3600
    rows = query_db("""
        SELECT id, title, started_at, ended_at, message_count, parent_session_id
        FROM sessions WHERE source='subagent' AND started_at > ?
        ORDER BY started_at DESC
    """, (cutoff,))
    assigned = {}  # role -> [tareas]
    for r in rows:
        active = r["ended_at"] is None
        age = now_ts() - (r["started_at"] or 0)
        title = r["title"]
        if not title:
            title = get_delegation_goal(r["id"])
        role = classify_role(title)
        entry = {
            "title": (title or "tarea delegada")[:70],
            "active": active,
            "age_min": int(age / 60),
            "msgs": r["message_count"] or 0,
        }
        assigned.setdefault(role, []).append(entry)
    result = {}
    for role in ALL_ROLES:
        entries = assigned.get(role, [])
        if not entries:
            continue
        active_entries = [e for e in entries if e["active"]]
        recent = [e for e in entries if e["age_min"] <= 45]
        pool = active_entries or recent
        if not pool:
            continue
        e = pool[0]
        status = "working" if e["active"] else "done"
        result[role] = {
            "status": status,
            "progress": 100 if e["active"] else 100,
            "task": e["title"],
            "subtitle": f"{e['age_min']}min · {e['msgs']} msg",
        }
    # 3) Los roles en marcha AHORA ganan sobre el histórico
    for role, state in live_roles.items():
        result[role] = state
    return result

def get_apoc_state():
    """Apoc = vigilancia: watcher, sync, gateway, crons activos."""
    watchers = any(is_process_running(p) for p in
                   ["matrix_watcher.py", "sync_agents", "hermes-gateway", "gateway.py"])
    crons = query_db("""
        SELECT title FROM sessions
        WHERE source='cron' AND ended_at IS NULL AND started_at > ?
        ORDER BY started_at DESC LIMIT 1
    """, (now_ts() - 3600,))
    if watchers or crons:
        task = "WATCHDOG · heartbeat " + datetime.now().strftime("%H:%M")
        if crons:
            task += " · " + (crons[0]["title"] or "cron")[:30]
        return {"status": "working", "progress": 100, "task": task[:80],
                "subtitle": "sistemas nominales"}
    return {"status": "idle", "progress": 0, "task": "SIN HEARTBEAT", "subtitle": ""}

def get_keymaker_state(sub_state):
    """Keymaker = automatización: crons activos o pipelines."""
    if "keymaker" in sub_state:
        return sub_state["keymaker"]
    crons = query_db("""
        SELECT title FROM sessions
        WHERE source='cron' AND ended_at IS NULL AND started_at > ?
        ORDER BY started_at DESC LIMIT 1
    """, (now_ts() - 3600,))
    if crons:
        return {"status": "working", "progress": 100,
                "task": ("⚙️ " + (crons[0]["title"] or "cron activo"))[:80],
                "subtitle": "automatización"}
    return {"status": "idle", "progress": 0, "task": "EN ESPERA", "subtitle": ""}

def main():
    neo = get_neo_state()
    subs = get_subagents_state()
    apoc = get_apoc_state()
    keymaker = get_keymaker_state(subs)

    agents = [
        {"agent": "neo", **neo},
        {"agent": "apoc", **apoc},
        {"agent": "keymaker", **keymaker},
    ]
    # Subagentes delegados → sus perfiles Matrix (sati se trata aparte: si hay
    # delegación de diseño real, gana sobre el estado del HUD en Render)
    for role in ALL_ROLES:
        if role != "sati" and role in subs:
            agents.append({"agent": role, **subs[role]})

    # Sati: HUD online en Render, salvo que tenga una tarea de diseño delegada
    if "sati" in subs:
        agents.append({"agent": "sati", **subs["sati"]})
    else:
        try:
            r = urllib.request.urlopen("https://matrix-hud.onrender.com/", timeout=5)
            sati_online = r.status == 200
        except Exception:
            sati_online = False
        if sati_online:
            agents.append({"agent": "sati", "status": "working", "progress": 100,
                           "task": "HUD EN VIVO RENDER",
                           "subtitle": datetime.now().strftime("%H:%M:%S") + " · online"})
        else:
            agents.append({"agent": "sati", "status": "idle", "progress": 0, "task": "OFFLINE", "subtitle": ""})

    active = [a["agent"] for a in agents if a["status"] == "working"]
    log(f"Sync: {len(agents)} agentes | NEO={neo['status']} | subagentes={[k for k in subs]} | activos={active}")

    with open(STATUS_FILE, "w") as f:
        json.dump(agents, f)

    try:
        data = json.dumps(agents).encode()
        req = urllib.request.Request(HUD_URL, data=data,
            headers={"Content-Type": "application/json", "User-Agent": "matrix-sync-v2"})
        resp = urllib.request.urlopen(req, timeout=10)
        log(f"Render: {json.loads(resp.read())}")
    except Exception as e:
        log(f"Render error: {e}")

if __name__ == "__main__":
    main()
