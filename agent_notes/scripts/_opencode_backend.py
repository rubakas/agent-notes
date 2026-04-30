"""Session cost report for OpenCode — reads SQLite database."""
import sqlite3
from pathlib import Path

from . import _pricing
from ._formatting import (
    BOLD, DIM, GREEN, YELLOW, NC,
    tier_color, fmt_tokens, fmt_time, fmt_cost,
)

DB = Path.home() / ".local/share/opencode/opencode.db"

SQL = """
WITH cs AS (SELECT id FROM session WHERE parent_id IS NULL ORDER BY time_created DESC LIMIT 1),
conv_start AS (
  SELECT COALESCE(
    (SELECT json_extract(m2.data,'$.time.created')
     FROM message m1 JOIN message m2 ON m1.session_id=m2.session_id
     WHERE m1.session_id=(SELECT id FROM cs)
       AND json_extract(m2.data,'$.time.created') > json_extract(m1.data,'$.time.created')
       AND json_extract(m2.data,'$.time.created') - json_extract(m1.data,'$.time.created') > 1800000
       AND NOT EXISTS (
         SELECT 1 FROM message mx WHERE mx.session_id=m1.session_id
           AND json_extract(mx.data,'$.time.created') > json_extract(m1.data,'$.time.created')
           AND json_extract(mx.data,'$.time.created') < json_extract(m2.data,'$.time.created'))
     ORDER BY json_extract(m1.data,'$.time.created') DESC LIMIT 1),
    0) AS start_ts
)
SELECT
  COALESCE(json_extract(m.data,'$.agent'), 'lead') AS agent,
  (SELECT json_extract(m2.data,'$.modelID') FROM message m2
   WHERE m2.session_id = s.id AND json_extract(m2.data,'$.role') = 'assistant'
   ORDER BY json_extract(m2.data,'$.time.completed') DESC LIMIT 1) AS model,
  SUM(json_extract(m.data,'$.tokens.input'))       AS inp,
  SUM(json_extract(m.data,'$.tokens.output'))      AS outp,
  SUM(json_extract(m.data,'$.tokens.cache.read'))  AS cache,
  ROUND(SUM(
    CASE WHEN json_extract(m.data,'$.time.completed') IS NOT NULL
              AND json_extract(m.data,'$.time.created') IS NOT NULL
    THEN (json_extract(m.data,'$.time.completed') - json_extract(m.data,'$.time.created')) / 1000.0
    ELSE 0 END
  ), 1) AS sec
FROM session s
JOIN message m ON m.session_id = s.id
CROSS JOIN cs
CROSS JOIN conv_start
WHERE (s.parent_id = cs.id OR s.id = cs.id)
  AND json_extract(m.data,'$.role') = 'assistant'
  AND json_extract(m.data,'$.time.created') >= conv_start.start_ts
  AND (s.time_created >= conv_start.start_ts OR s.id = (SELECT id FROM cs))
GROUP BY s.id
"""


def run() -> int:
    if not DB.exists():
        print(f"Database not found: {DB}")
        return 1

    rows = sqlite3.connect(DB).execute(SQL).fetchall()
    if not rows:
        print("No sessions found.")
        return 0

    records = [
        (agent, model or "unknown", inp or 0, outp or 0, cache or 0, sec or 0)
        for agent, model, inp, outp, cache, sec in rows
    ]

    costs = [
        (agent, model, inp, outp, cache, sec,
         _pricing.calculate_cost(model, inp, outp, cache),
         _pricing.baseline_cost(inp, outp, cache))
        for agent, model, inp, outp, cache, sec in records
    ]

    _total_inp  = sum(i for _, _, i, *_ in costs)
    _total_outp = sum(o for _, _, _, o, *_ in costs)
    _total_cache = sum(c for _, _, _, _, c, *_ in costs)
    _max_sec    = max(s for _, _, _, _, _, s, *_ in costs)
    _total_sec  = sum(s for _, _, _, _, _, s, *_ in costs)
    _total_time = f"{fmt_time(_max_sec)} / {fmt_time(_total_sec)} seq"

    agent_col_w = max(len(f"{a}({m})") for a, m, *_ in costs) + 2
    tok_col_w = max(
        max(len(fmt_tokens(i, o, c)) for _, _, i, o, c, *_ in costs),
        len(fmt_tokens(_total_inp, _total_outp, _total_cache))
    ) + 2
    time_col_w = max(
        max(len(fmt_time(s)) for _, _, _, _, _, s, *_ in costs),
        len(_total_time)
    ) + 2
    W = (agent_col_w, tok_col_w, time_col_w, 12, 12)

    bl_label = _pricing.baseline_label()
    header = (
        f"{'agent(model)':<{W[0]}}"
        f" {'in/out/cache':<{W[1]}}"
        f" {'time':<{W[2]}}"
        f" {'actual':<{W[3]}}"
        f" {f'vs {bl_label}':<{W[4]}}"
    )
    print(BOLD + header + NC)
    print(DIM + "-" * len(header) + NC)

    total_inp = total_outp = total_cache = 0
    total_actual = total_vs = max_sec = total_sec = 0.0

    for agent, model, inp, outp, cache, sec, actual, vs in costs:
        label = f"{agent}({model})"
        time_str = fmt_time(sec)
        col = tier_color(model)
        print(
            col + f"{label:<{W[0]}}" + NC
            + f" {fmt_tokens(inp, outp, cache):<{W[1]}}"
            + f" {time_str:<{W[2]}}"
            + f" {fmt_cost(actual):<{W[3]}}"
            + f" {fmt_cost(vs):<{W[4]}}"
        )
        total_inp += inp
        total_outp += outp
        total_cache += cache
        total_actual += actual
        total_vs += vs
        max_sec = max(max_sec, sec)
        total_sec += sec

    saved_pct = round((1 - total_actual / total_vs) * 100) if total_vs else 0
    total_label = f"TOTAL (saved {saved_pct}%)"
    total_time = _total_time
    col = GREEN if total_actual <= 5 else YELLOW
    print(
        col + BOLD
        + f"{total_label:<{W[0]}}"
        + f" {fmt_tokens(total_inp, total_outp, total_cache):<{W[1]}}"
        + f" {total_time:<{W[2]}}"
        + f" {fmt_cost(total_actual):<{W[3]}}"
        + f" {fmt_cost(total_vs):<{W[4]}}"
        + NC
    )
    return 0
