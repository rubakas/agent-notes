"""Session cost report for OpenCode — reads SQLite database."""
import sqlite3
from pathlib import Path

from . import _pricing
from ._formatting import fmt_time, render_cost_table

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
        (agent, _pricing.normalize_model(model or "unknown"), inp or 0, outp or 0, cache or 0, sec or 0)
        for agent, model, inp, outp, cache, sec in rows
    ]

    costs = [
        (agent, model, inp, outp, cache, sec,
         _pricing.calculate_cost(model, inp, outp, cache),
         _pricing.baseline_cost(inp, outp, cache))
        for agent, model, inp, outp, cache, sec in records
    ]

    max_sec = max(s for _, _, _, _, _, s, *_ in costs)
    total_sec = sum(s for _, _, _, _, _, s, *_ in costs)
    total_time_str = f"{fmt_time(max_sec)} / {fmt_time(total_sec)} seq"

    rows = [
        (f"{agent}({model})", model, inp, outp, cache, fmt_time(sec), actual, vs)
        for agent, model, inp, outp, cache, sec, actual, vs in costs
    ]
    render_cost_table(rows, total_time_str, _pricing.baseline_label())
    return 0
