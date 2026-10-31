"""End-of-day price and volume.

Uses yfinance when installed; otherwise calls the same Yahoo chart endpoint
yfinance uses under the hood, so the dependency is optional.
"""
from __future__ import annotations

import datetime as dt

import requests

from .. import cache
from ..config import BROWSER_UA


def _via_yfinance(symbol: str, days: int):
    import yfinance as yf  # optional

    df = yf.Ticker(f"{symbol}.NS").history(period=f"{days}d", interval="1d", auto_adjust=False)
    if df is None or df.empty:
        return None
    return [[idx.strftime("%Y-%m-%d"), round(float(r["Close"]), 2), int(r["Volume"])]
            for idx, r in df.iterrows() if r["Close"] == r["Close"]]


def _via_chart_api(symbol: str, days: int):
    rng = "3mo" if days <= 90 else "6mo"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.NS?range={rng}&interval=1d"
    r = requests.get(url, headers={"User-Agent": BROWSER_UA}, timeout=20)
    r.raise_for_status()
    res = r.json()["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    rows = []
    for ts, c, v in zip(res["timestamp"], q["close"], q["volume"]):
        if c is None or v is None:
            continue  # Yahoo leaves holes on non-trading days
        d = dt.datetime.fromtimestamp(ts, dt.timezone(dt.timedelta(hours=5, minutes=30))).strftime("%Y-%m-%d")
        rows.append([d, round(c, 2), int(v)])
    return rows


def eod_series(symbol: str, days: int = 90):
    """[[date, close, volume], ...] oldest first. Cached for 6 hours."""
    def fetch():
        try:
            return _via_yfinance(symbol, days)
        except ImportError:
            pass
        except Exception:
            pass  # yfinance breaks every few months; fall through to the raw endpoint
        try:
            return _via_chart_api(symbol, days)
        except Exception:
            return None

    return cache.cached_json("prices", f"{symbol}:{days}:{dt.date.today()}", fetch, max_age=6 * cache.HOUR)
