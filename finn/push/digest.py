"""Build the push snapshot: prices + every filing in the window, classified and enriched.

The snapshot is one JSON file. The app reads it from the API when one is running,
or straight off static hosting when not, so the demo always opens.

The window fetched is wide (7 days by default). The app narrows it — 24h, 3 days,
a week — on the device, without another round-trip.
"""
from __future__ import annotations

import datetime as dt
import json
from concurrent.futures import ThreadPoolExecutor

from .. import llm
from ..config import DATA_OUT, Portfolio, load_portfolio
from ..sources import prices, screener
from ..sources.nse import NSEClient
from .classify import classify, tidy_detail
from .enrich import one_liner, people_card, results_card

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def _enrich(filing: dict) -> dict:
    cat, tier = filing["category"], filing["tier"]
    try:
        if cat == "results" and tier == 3:
            filing["results"] = results_card(filing, screener.company(filing["symbol"]))
        elif cat == "management_change" and tier >= 2:
            filing["people"] = people_card(filing)
        elif tier == 3:
            line = one_liner(filing)
            filing["summary"] = line["summary"]
            if line.get("routine"):          # the model read it and found nothing: demote
                filing["tier"] = 2
        elif tier == 2:
            filing["summary"] = tidy_detail(filing.get("detail", ""))   # free: NSE's own text
    except Exception as e:  # one bad PDF must never sink the digest
        filing["enrich_error"] = str(e)[:120]
    return filing


def build(portfolio: Portfolio | None = None, days: int = 7, log=print) -> dict:
    pf = portfolio or load_portfolio()
    today = dt.datetime.now(IST).date()
    start = today - dt.timedelta(days=days)
    nse = NSEClient()

    log(f"prices for {len(pf.holdings)} holdings…")
    with ThreadPoolExecutor(6) as ex:
        series = dict(zip(pf.symbols, ex.map(lambda s: prices.eod_series(s, 90), pf.symbols)))

    log("announcements…")
    filings: list[dict] = []
    for h in pf.holdings:            # sequential: NSE throttles parallel sessions
        for f in nse.announcements(h.symbol, start, today):
            f.update(classify(f["subject"], f["detail"]))
            f["name"] = h.name
            filings.append(f)
    log(f"{len(filings)} filings; enriching headline items with {llm.describe()}")

    with ThreadPoolExecutor(4) as ex:
        filings = list(ex.map(_enrich, filings))
    filings.sort(key=lambda f: f.get("time") or "", reverse=True)

    snap = {
        "generated_at": dt.datetime.now(IST).isoformat(timespec="seconds"),
        "window_days": days,
        "sample": False,
        "model": llm.describe(),
        "defaults": pf.alerts.__dict__,
        "holdings": [{"symbol": h.symbol, "name": h.name, "sector": h.sector, "eod": series.get(h.symbol) or []}
                     for h in pf.holdings],
        "filings": filings,
    }
    return snap


def write(snap: dict) -> str:
    DATA_OUT.mkdir(parents=True, exist_ok=True)
    path = DATA_OUT / "snapshot.json"
    path.write_text(json.dumps(snap, ensure_ascii=False, separators=(",", ":")))
    return str(path)
