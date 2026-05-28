#!/usr/bin/env python3
"""
Token Cost Tracker — Lee state.db de Hermes Agent y calcula coste real.
DeepSeek V4 Flash pricing:
  - Input:  $0.14 por millón de tokens
  - Output: $0.28 por millón de tokens
  - Cache:  $0.035 por millón de tokens (aprox 25% del input)
"""
import json, os, sqlite3
from datetime import datetime, timezone
from pathlib import Path

# ── Rutas ──
STATE_DB = Path.home() / ".hermes" / "state.db"
TOKEN_CACHE = Path("/tmp/matrix_token_cache.json")

# ── Precios DeepSeek V4 Flash (por millón de tokens) ──
# Oficial: cache-hit input = $0.028/M (80% descuento sobre $0.14/M)
# NOTA: state.db ya separa input_tokens (no cache) de cache_read_tokens (cache-hit)
# input_tokens = prompt_total - cache_read - cache_write (porción NO cacheada)
PRICING = {
    "input_per_million": 0.14,         # $0.14/M — tokens NO cacheados
    "output_per_million": 0.28,        # $0.28/M — completion tokens
    "cache_read_per_million": 0.028,   # $0.028/M — cache-hit (80% off)
    "cache_write_per_million": 0.07,   # ~$0.07/M — cache creation
}

def get_today_start() -> float:
    """Timestamp UNIX de hoy a las 00:00:00 UTC"""
    return datetime.combine(datetime.now(timezone.utc).date(), datetime.min.time()).replace(tzinfo=timezone.utc).timestamp()

def get_yesterday_start() -> float:
    """Timestamp UNIX de ayer a las 00:00:00 UTC"""
    from datetime import timedelta
    return (datetime.combine(datetime.now(timezone.utc).date(), datetime.min.time()).replace(tzinfo=timezone.utc) - timedelta(days=1)).timestamp()

def query_token_totals(since_ts: float) -> dict:
    """Consulta state.db y devuelve totales de tokens desde since_ts"""
    if not STATE_DB.exists():
        return {"error": "state.db not found"}
    
    try:
        conn = sqlite3.connect(str(STATE_DB))
        cur = conn.execute("""
            SELECT 
                COALESCE(SUM(input_tokens), 0),
                COALESCE(SUM(output_tokens), 0),
                COALESCE(SUM(cache_read_tokens), 0),
                COALESCE(SUM(cache_write_tokens), 0),
                COALESCE(SUM(reasoning_tokens), 0),
                COUNT(*)
            FROM sessions WHERE started_at >= ?
        """, (since_ts,))
        row = cur.fetchone()
        conn.close()
        
        return {
            "input_tokens": row[0],
            "output_tokens": row[1],
            "cache_read_tokens": row[2],
            "cache_write_tokens": row[3],
            "reasoning_tokens": row[4],
            "session_count": row[5],
        }
    except Exception as e:
        return {"error": str(e)}

def calculate_cost(totals: dict) -> dict:
    """Aplica precios DeepSeek V4 Flash a los totales de tokens"""
    if "error" in totals:
        return {"error": totals["error"]}
    
    p = PRICING
    input_cost = totals["input_tokens"] * p["input_per_million"] / 1_000_000
    output_cost = totals["output_tokens"] * p["output_per_million"] / 1_000_000
    cache_read_cost = totals["cache_read_tokens"] * p["cache_read_per_million"] / 1_000_000
    cache_write_cost = totals["cache_write_tokens"] * p["cache_write_per_million"] / 1_000_000
    total_cost = input_cost + output_cost + cache_read_cost + cache_write_cost
    
    return {
        "cost_input": round(input_cost, 6),
        "cost_output": round(output_cost, 6),
        "cost_cache_read": round(cache_read_cost, 6),
        "cost_cache_write": round(cache_write_cost, 6),
        "cost_total": round(total_cost, 6),
        "tokens_input": totals["input_tokens"],
        "tokens_output": totals["output_tokens"],
        "tokens_cache_read": totals["cache_read_tokens"],
        "tokens_cache_write": totals["cache_write_tokens"],
        "tokens_reasoning": totals["reasoning_tokens"],
        "tokens_total": totals["input_tokens"] + totals["output_tokens"] + totals["cache_read_tokens"] + totals["cache_write_tokens"],
        "session_count": totals["session_count"],
        "pricing": f"Input ${p['input_per_million']}/M · Output ${p['output_per_million']}/M · Cache ${p['cache_read_per_million']}/M",
        "updated": datetime.now(timezone.utc).isoformat(),
    }

def get_today_cost() -> dict:
    """Devuelve coste de HOY"""
    totals = query_token_totals(get_today_start())
    return calculate_cost(totals)

def get_yesterday_cost() -> dict:
    """Devuelve coste de AYER"""
    totals = query_token_totals(get_yesterday_start())
    result = calculate_cost(totals)
    # Filtra solo ayer (excluye hoy)
    today_totals = query_token_totals(get_today_start())
    if "error" not in today_totals and "error" not in totals:
        for k in ["input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens", "reasoning_tokens", "session_count"]:
            result[k] = max(0, totals[k] - today_totals[k])
        # Recalcular coste
        sub_totals = {k: result[k] for k in ["input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens", "reasoning_tokens", "session_count"]}
        cost_result = calculate_cost(sub_totals)
        result.update(cost_result)
    return result

def save_cache(data: dict):
    """Guarda en cache para que el watcher lo lea"""
    with open(TOKEN_CACHE, "w") as f:
        json.dump(data, f, indent=2)

def load_cache() -> dict:
    """Lee cache"""
    try:
        with open(TOKEN_CACHE) as f:
            return json.load(f)
    except:
        return {}

def format_cost_usd(cents: float) -> str:
    """Formatea coste: $0.42"""
    if cents < 0.01:
        return f"${cents:.4f}"
    return f"${cents:.2f}"

def format_tokens(n: int) -> str:
    """Formatea tokens: 1.2M, 384K, etc."""
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n/1_000:.0f}K"
    return str(n)

if __name__ == "__main__":
    today = get_today_cost()
    yesterday = get_yesterday_cost()
    
    result = {
        "today": today,
        "yesterday": yesterday,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    save_cache(result)
    
    # Print summary
    if "error" not in today:
        print(f"📊 TOKENS HOY — {format_tokens(today['tokens_input'])} in · {format_tokens(today['tokens_output'])} out · {today['session_count']} sesiones")
        print(f"💰 COSTE: ${today['cost_total']:.4f} (in: ${today['cost_input']:.4f} + out: ${today['cost_output']:.4f} + cache: ${today['cost_cache_read']:.4f})")
    else:
        print(f"✗ Error: {today.get('error', 'unknown')}")
