"""screener.in company pages: the standardised multi-year tables and the document links.

screener.in is a consolidator of company filings, so its tables are a convenient
primary-data view (they are the company's reported numbers, not opinions). We use
it for numbers and for finding the annual-report and concall-transcript PDFs.
The parser is generic — every table becomes {periods, rows} keyed by row label —
so it survives screener tweaking a row name or adding a column.
"""
from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup

from .. import cache
from ..config import BROWSER_UA

BASE = "https://www.screener.in"
SECTIONS = ["quarters", "profit-loss", "balance-sheet", "cash-flow", "ratios"]


def _num(text: str):
    t = text.replace(",", "").replace("%", "").replace("₹", "").strip()
    if t in ("", "-", "—"):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def _label(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ").replace("+", "")).strip()


def parse_table(section) -> dict | None:
    table = section.find("table") if section else None
    if not table:
        return None
    head = table.find("thead")
    periods = [_label(th.get_text()) for th in head.find_all("th")][1:] if head else []
    rows: dict[str, list] = {}
    for tr in table.select("tbody tr"):
        cells = tr.find_all("td")
        if len(cells) < 2:
            continue
        label = _label(cells[0].get_text())
        if not label or label.lower().startswith("raw pdf"):
            continue
        rows[label] = [_num(td.get_text()) for td in cells[1:]]
    return {"periods": periods, "rows": rows} if rows else None


def parse_company(html: str, url: str = "") -> dict:
    soup = BeautifulSoup(html, "lxml")
    h1 = soup.find("h1")
    out = {
        "name": h1.get_text(strip=True) if h1 else "",
        "url": url,
        "about": "",
        "top_ratios": {},
        "tables": {},
        "annual_reports": [],
        "concalls": [],
    }
    about = soup.select_one(".company-profile .about") or soup.select_one(".about")
    if about:
        out["about"] = " ".join(about.get_text(" ", strip=True).split())

    for li in soup.select("#top-ratios li"):
        name = li.select_one(".name")
        val = li.select_one(".number")
        if name and val:
            out["top_ratios"][_label(name.get_text())] = _num(val.get_text())

    for sid in SECTIONS:
        t = parse_table(soup.find("section", id=sid))
        if t:
            out["tables"][sid] = t

    for a in soup.select(".documents.annual-reports a"):
        href = a.get("href", "")
        m = re.search(r"(20\d\d)", a.get_text(" "))
        if href.startswith("http"):
            out["annual_reports"].append({"year": int(m.group(1)) if m else None, "url": href,
                                          "label": " ".join(a.get_text(" ").split())})

    for li in soup.select(".documents.concalls li"):
        date_el = li.find("div")
        when = date_el.get_text(strip=True) if date_el else ""
        links = {a.get_text(strip=True).lower(): a.get("href") for a in li.find_all("a") if a.get("href", "").startswith("http")}
        if links:
            out["concalls"].append({"period": when, "transcript": links.get("transcript"),
                                    "ppt": links.get("ppt"), "recording": links.get("rec")})
    return out


def _has_numbers(parsed: dict) -> bool:
    q = parsed["tables"].get("quarters")
    return bool(q and len(q["periods"]) >= 4 and any(v is not None for row in q["rows"].values() for v in row))


def company(symbol: str) -> dict | None:
    """Consolidated figures where the company reports them, else standalone."""
    symbol = symbol.upper().strip()

    def fetch():
        reached = False
        s = requests.Session()
        s.headers["User-Agent"] = BROWSER_UA
        for path, basis in ((f"/company/{symbol}/consolidated/", "consolidated"), (f"/company/{symbol}/", "standalone")):
            try:
                r = s.get(BASE + path, timeout=25)
            except requests.RequestException:
                continue
            reached = True
            if r.status_code != 200:
                continue
            parsed = parse_company(r.text, BASE + path)
            if _has_numbers(parsed):
                parsed["basis"] = basis
                parsed["symbol"] = symbol
                return parsed
        if not reached:
            raise ConnectionError("Couldn't reach screener.in. Check your internet connection.")
        return None

    return cache.cached_json("screener", symbol, fetch, max_age=cache.DAY)
