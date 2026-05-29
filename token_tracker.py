#!/usr/bin/env python3
"""Token Cost Tracker — Lee state.db y calcula coste real. 0 tokens."""
import json, os, sqlite3
from datetime import datetime, timezone
from pathlib import Path

STATE_DB = Path.home() / ".hermes" / "state.db"
TOKEN_CACHE = Path("/tmp/matrix_token_cache.json")

PRICING = {
    "input_per_million": 0.14,
    "output_per_million": 0.28,
    "cache_read_per_million": 0.028,
    "cache_write_per_million": 0.07,
}

def get_today_start():
    return datetime.combine(datetime.now(timezone.utc).date(), datetime.min.time()).replace(tzinfo=timezone.utc).timestamp()

def query_token_totals(since_ts):
    if not STATE_DB.exists(): return {"error": "state.db not found"}
    try:
        conn = sqlite3.connect(str(STATE_DB))
        cur = conn.execute("""
            SELECT COALESCE(SUM(input_tokens), 0), COALESCE(SUM(output_tokens), 0),
                   COALESCE(SUM(cache_read_tokens), 0), COALESCE(SUM(cache_write_tokens), 0),
                   COALESCE(SUM(estimated_cost_usd), 0), COUNT(*)
            FROM sessions WHERE started_at >= ?
        """, (since_ts,))
        row = cur.fetchone()
        conn.close()
        return {"input_tokens": row[0], "output_tokens": row[1], "cache_read_tokens": row[2],
                "cache_write_tokens": row[3], "cost_total": row[4], "session_count": row[5]}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    today = query_token_totals(get_today_start())
    result = {"today": today, "timestamp": datetime.now(timezone.utc).isoformat()}
    with open(TOKEN_CACHE, "w") as f:
        json.dump(result, f)
    if "error" not in today:
        print(f"💰 ${today['cost_total']:.4f} · {today['session_count']} sesiones")
    else:
        print(f"✗ {today['error']}")
