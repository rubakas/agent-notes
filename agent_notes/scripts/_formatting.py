"""ANSI color constants and shared formatting helpers."""
import os
import sys

_USE_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")

BOLD   = "\033[1m"   if _USE_COLOR else ""
DIM    = "\033[2m"   if _USE_COLOR else ""
YELLOW = "\033[0;33m" if _USE_COLOR else ""
GREEN  = "\033[0;32m" if _USE_COLOR else ""
CYAN   = "\033[0;36m" if _USE_COLOR else ""
NC     = "\033[0m"   if _USE_COLOR else ""


def tier_color(model_id: str) -> str:
    if not _USE_COLOR:
        return ""
    if "opus" in model_id:
        return YELLOW
    if "sonnet" in model_id:
        return CYAN
    return DIM


def fmt_num(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}m"
    if n >= 1_000:
        return f"{n / 1_000:.2f}k"
    return str(n)


def fmt_tokens(inp, outp, cache) -> str:
    return f"{fmt_num(inp)}/{fmt_num(outp)}/{fmt_num(cache)}"


def fmt_time(sec: float) -> str:
    s = int(round(sec))
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}m {s}s" if s else f"{m}m"
    h, m = divmod(m, 60)
    return f"{h}h {m}m" if m else f"{h}h"


def fmt_cost(c: float) -> str:
    return f"${c:.4f}"


def render_cost_table(
    rows: list[tuple],
    total_time_str: str,
    baseline_label: str,
) -> None:
    """Print a cost table to stdout.

    Each row must be a tuple of:
        (label: str, model: str, inp: int, outp: int, cache: int,
         time_str: str, actual: float, vs: float)

    total_time_str  — pre-formatted total time (backends compute it differently)
    baseline_label  — label for the rightmost "vs" column header
    """
    agent_col_w = max(len(label) for label, *_ in rows) + 2
    tok_col_w = max(
        max(len(fmt_tokens(i, o, c)) for _, _, i, o, c, *_ in rows),
        len(fmt_tokens(
            sum(i for _, _, i, *_ in rows),
            sum(o for _, _, _, o, *_ in rows),
            sum(c for _, _, _, _, c, *_ in rows),
        ))
    ) + 2
    time_col_w = max(
        max(len(t) for _, _, _, _, _, t, *_ in rows),
        len(total_time_str)
    ) + 2
    W = (agent_col_w, tok_col_w, time_col_w, 12, 12)

    header = (
        f"{'agent(model)':<{W[0]}}"
        f" {'in/out/cache':<{W[1]}}"
        f" {'time':<{W[2]}}"
        f" {'actual':<{W[3]}}"
        f" {f'vs {baseline_label}':<{W[4]}}"
    )
    print(BOLD + header + NC)
    print(DIM + "-" * len(header) + NC)

    total_inp = total_outp = total_cache = 0
    total_actual = total_vs = 0.0

    for label, model, inp, outp, cache, time_str, actual, vs in rows:
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

    saved_pct = round((1 - total_actual / total_vs) * 100) if total_vs else 0
    total_label = f"TOTAL (saved {saved_pct}%)"
    col = GREEN if total_actual <= 5 else YELLOW
    print(
        col + BOLD
        + f"{total_label:<{W[0]}}"
        + f" {fmt_tokens(total_inp, total_outp, total_cache):<{W[1]}}"
        + f" {total_time_str:<{W[2]}}"
        + f" {fmt_cost(total_actual):<{W[3]}}"
        + f" {fmt_cost(total_vs):<{W[4]}}"
        + NC
    )
