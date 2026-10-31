"""Corporate announcements from NSE.

NSE's JSON API sits behind a cookie check: a session must visit the site once
before /api/* answers. We do that warm-up, then ask per symbol.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import time

import requests

from .. import cache
from ..config import BROWSER_UA

BASE = "https://www.nseindia.com"


class NSEClient:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": BROWSER_UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-IN,en;q=0.9",
            "Referer": f"{BASE}/companies-listing/corporate-filings-announcements",
        })
        self._warm = False

    def _warmup(self):
        if self._warm:
            return
        for path in ("/", "/companies-listing/corporate-filings-announcements"):
            try:
                self.s.get(BASE + path, timeout=15)
            except requests.RequestException:
                pass
        self._warm = True

    def announcements(self, symbol: str, start: dt.date, end: dt.date) -> list[dict]:
        key = f"{symbol}:{start}:{end}"

        def fetch():
            self._warmup()
            params = {"index": "equities", "symbol": symbol,
                      "from_date": start.strftime("%d-%m-%Y"), "to_date": end.strftime("%d-%m-%Y")}
            for attempt in range(3):
                try:
                    r = self.s.get(f"{BASE}/api/corporate-announcements", params=params, timeout=20)
                    if r.status_code in (401, 403):     # cookie expired: re-warm once
                        self._warm = False
                        self._warmup()
                        continue
                    r.raise_for_status()
                    data = r.json()
                    rows = data if isinstance(data, list) else data.get("data", [])
                    return [normalise(row) for row in rows]
                except (requests.RequestException, ValueError):
                    time.sleep(1.5 * (attempt + 1))
            return None

        # Today's window must stay fresh; older windows can be reused for an hour.
        return cache.cached_json("nse", key, fetch, max_age=cache.HOUR) or []


def _parse_time(s: str | None) -> str | None:
    if not s:
        return None
    for fmt in ("%d-%b-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M:%S"):
        try:
            return dt.datetime.strptime(s.strip(), fmt).isoformat()
        except ValueError:
            continue
    return None


def normalise(row: dict) -> dict:
    """Map NSE's field names to ours. Unknown fields are ignored on purpose."""
    ts = _parse_time(row.get("an_dt")) or _parse_time(row.get("sort_date")) or _parse_time(row.get("exchdisstime"))
    url = row.get("attchmntFile") or ""
    ident = str(row.get("seq_id") or hashlib.sha1(f"{row.get('symbol')}{ts}{url}".encode()).hexdigest()[:12])
    return {
        "id": f"nse-{ident}",
        "symbol": row.get("symbol", ""),
        "company": row.get("sm_name", ""),
        "subject": (row.get("desc") or "").strip(),
        "detail": " ".join((row.get("attchmntText") or "").split()),
        "time": ts,
        "url": url if url.startswith("http") else "",
        "source": "NSE",
    }
