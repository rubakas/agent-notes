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
