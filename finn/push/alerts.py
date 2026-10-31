"""Threshold alerts on end-of-day data.

The same rules run in the browser (web/js/rules.js) so that when the investor
drags a threshold the alert list updates instantly. This module is the server
copy, used for the snapshot's default view and for tests.
"""
from __future__ import annotations

from statistics import mean


def day_stats(series: list[list], lookback: int = 20) -> dict | None:
    """series: [[date, close, volume], ...] oldest first."""
    if not series or len(series) < 2:
        return None
    date, close, vol = series[-1]
    prev_close = series[-2][1]
    window = [r[2] for r in series[-lookback - 1:-1] if r[2]]
    avg = mean(window) if window else None
    return {
        "date": date,
        "close": close,
        "change_pct": round((close - prev_close) / prev_close * 100, 2) if prev_close else None,
        "volume": vol,
        "avg_volume": round(avg) if avg else None,
        "volume_multiple": round(vol / avg, 2) if avg else None,
    }


def evaluate(symbol: str, series: list[list], volume_multiple: float, lookback: int, move_pct: float) -> list[dict]:
    s = day_stats(series, lookback)
    if not s:
        return []
    out = []
    if s["volume_multiple"] is not None and s["volume_multiple"] >= volume_multiple:
        out.append({"symbol": symbol, "kind": "volume", "date": s["date"], "value": s["volume_multiple"],
                    "text": f"Volume {s['volume_multiple']:.1f}× its {lookback}-day average"})
    if s["change_pct"] is not None and abs(s["change_pct"]) >= move_pct:
        out.append({"symbol": symbol, "kind": "move", "date": s["date"], "value": s["change_pct"],
                    "text": f"Closed {s['change_pct']:+.1f}% on the day"})
    return out
