"""Turn a headline filing into something the investor can read in five seconds.

  results            -> Revenue / EBITDA / PBT / PAT, this quarter vs last quarter
                        and vs a year ago, read from the filing itself
  management_change  -> who is coming or going, and where they came from
  everything else    -> one sentence: what happened, and the number that matters

Arithmetic is always done here in Python. The model is only asked to *find*
numbers on a page, never to compute with them.
"""
from __future__ import annotations

import datetime as dt
import re
import urllib.parse

from .. import llm
from ..sources import pdfs
from .classify import tidy_detail

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

RESULTS_SYSTEM = """You read Indian listed-company quarterly results filings (SEBI format).
Find the statement of profit and loss table. If both consolidated and standalone are
present, use CONSOLIDATED. Use the three 'quarter ended' columns: the current quarter,
the preceding quarter, and the corresponding quarter of the previous year.
Copy numbers exactly as printed (no arithmetic, no rounding). Negative numbers as negative.
If a line is not present, use null. Never guess."""

RESULTS_USER = """Return JSON:
{{"basis": "consolidated"|"standalone",
  "unit": the unit as printed, e.g. "crore", "lakh", "million",
  "quarters": [current_label, previous_label, year_ago_label],   e.g. ["30.09.2026","30.06.2026","30.09.2025"]
  "revenue_from_operations": [cur, prev, year_ago],
  "other_income": [...], "finance_costs": [...], "depreciation": [...],
  "profit_before_exceptional_and_tax": [...], "profit_before_tax": [...], "net_profit": [...]}}

Filing text:
{text}"""

_UNIT = {"crore": 1.0, "crores": 1.0, "cr": 1.0, "lakh": 0.01, "lakhs": 0.01, "million": 0.1, "millions": 0.1,
         "thousand": 0.0001, "billion": 100.0}


def _pct(a, b):
    if a is None or b in (None, 0):
        return None
    return round((a - b) / abs(b) * 100, 1)


def _scale(unit: str | None) -> float:
    u = (unit or "crore").lower()
    for k, v in _UNIT.items():
        if k in u:
            return v
    return 1.0


def _triplet(raw: dict, key: str, scale: float):
    vals = raw.get(key) or [None, None, None]
    out = []
    for v in (vals + [None, None, None])[:3]:
        try:
            out.append(None if v is None else round(float(str(v).replace(",", "")) * scale, 2))
        except ValueError:
            out.append(None)
    return out


def _rows_from_triplets(rev, ebitda, pbt, pat):
    rows = []
    for name, (cur, prev, yoy) in (("Revenue", rev), ("EBITDA", ebitda), ("PBT", pbt), ("PAT", pat)):
        rows.append({"name": name, "value": cur, "qoq": _pct(cur, prev), "yoy": _pct(cur, yoy),
                     "prev": prev, "year_ago": yoy})
    return rows


def _from_filing(url: str) -> dict | None:
    if not (url and llm.available()):
        return None
    texts = pdfs.pages(url, first=12)
    if not texts:
        return None
    idx = pdfs.find_pages(texts, [r"revenue from operations", r"profit before tax"])[:3] or list(range(min(2, len(texts))))
    text = "\n\n".join(texts[i] for i in idx)[:14000]
    raw = llm.complete_json("fast", RESULTS_SYSTEM, RESULTS_USER.format(text=text))
    if not raw:
        return None
    s = _scale(raw.get("unit"))
    rev = _triplet(raw, "revenue_from_operations", s)
    oi = _triplet(raw, "other_income", s)
    fin = _triplet(raw, "finance_costs", s)
    dep = _triplet(raw, "depreciation", s)
    pbt_pre = _triplet(raw, "profit_before_exceptional_and_tax", s)
    pbt = _triplet(raw, "profit_before_tax", s)
    pat = _triplet(raw, "net_profit", s)
    if rev[0] is None or pat[0] is None:
        return None
    base = [a if a is not None else b for a, b in zip(pbt_pre, pbt)]
    ebitda = []
    for b, f, d, o in zip(base, fin, dep, oi):
        ebitda.append(None if None in (b, f, d) else round(b + f + d - (o or 0), 2))
    return {"rows": _rows_from_triplets(rev, ebitda, pbt, pat), "basis": raw.get("basis"),
            "quarters": raw.get("quarters"), "unit": "₹ cr", "source": "Results filing (PDF)",
            "ebitda_note": "PBT before exceptional items + finance costs + depreciation − other income"}


def _from_screener(sc: dict | None) -> dict | None:
    """Fallback: screener's quarterly table, which is compiled from the same filings."""
    q = (sc or {}).get("tables", {}).get("quarters")
    if not q or len(q["periods"]) < 5:
        return None
    rows = q["rows"]

    def last3(*names):
        for n in names:
            if n in rows:
                r = rows[n]
                return [r[-1], r[-2], r[-5]]
        return [None, None, None]

    rev = last3("Sales", "Revenue")
    is_lender = "Financing Profit" in rows
    ebitda = [None, None, None] if is_lender else last3("Operating Profit")
    out = {"rows": _rows_from_triplets(rev, ebitda, last3("Profit before tax"), last3("Net Profit")),
           "basis": sc.get("basis"), "quarters": [q["periods"][-1], q["periods"][-2], q["periods"][-5]],
           "unit": "₹ cr", "source": "screener.in quarterly table"}
    if is_lender:
        out["ebitda_note"] = "EBITDA isn't meaningful for a lender — read PBT and PAT instead."
    return out


def results_card(filing: dict, sc: dict | None) -> dict | None:
    card = _from_filing(filing.get("url", ""))
    check = _from_screener(sc)
    filed = (filing.get("time") or "")[:7]
    # Is screener already showing this quarter? (It lags the filing by a few hours.)
    current = bool(check) and (not filed or _same_or_next_quarter((check.get("quarters") or [""])[0], filed))
    if card and check and current:
        # Cross-check the model's reading against an independent source.
        a, b = card["rows"][0]["value"], check["rows"][0]["value"]
        card["cross_checked"] = bool(a and b and abs(a - b) / abs(b) < 0.03)
        if not card["cross_checked"]:
            # Never show a number we couldn't verify when a verified one exists.
            check["note"] = "Our reading of the filing didn't match the reported tables, so these are the tables' figures."
            card = check
    if not card and check:
        if not current:
            return {"pending": True, "source": "Numbers will appear once the quarter is in the tables."}
        card = check
    if card and card.get("rows"):
        margin = [r for r in card["rows"] if r["name"] == "EBITDA"][0]["value"]
        rev = card["rows"][0]["value"]
        if margin is not None and rev:
            card["ebitda_margin"] = round(margin / rev * 100, 1)
    return card


_MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def _same_or_next_quarter(period_label: str, filed_yyyy_mm: str) -> bool:
    """'Sep 2026' is the right quarter for a filing made in Oct/Nov 2026."""
    try:
        mon, year = period_label.split()
        p = dt.date(int(year), _MONTHS[mon[:3]], 1)
        f = dt.date(int(filed_yyyy_mm[:4]), int(filed_yyyy_mm[5:7]), 1)
        return 0 <= (f.year - p.year) * 12 + (f.month - p.month) <= 3
    except (ValueError, KeyError):
        return True


# ---------------------------------------------------------------------------
# People
# ---------------------------------------------------------------------------

PEOPLE_SYSTEM = """You read Indian stock-exchange disclosures about changes in directors and key
managerial personnel (SEBI Reg. 30). These filings usually include a 'brief profile' annexure
for anyone appointed. Extract only what the text states. Never add outside knowledge."""

PEOPLE_USER = """Return JSON: {{"people": [{{"name": str, "role": str, "change": "appointed"|"resigned"|"retired"|"ceased"|"redesignated",
"effective": str|null, "reason": str|null,
"background": str|null  (the brief profile in at most 40 words: last roles, education),
"previously": [str] (up to 3 earlier employers/roles, as stated)}}]}}

Text:
{text}"""

_NAME_RX = re.compile(
    r"(appointment|re-?appointment|cessation|resignation|retirement|re-?designation)\s+of\s+"
    r"((?:Mr|Ms|Mrs|Dr|Shri|Smt)\.?\s+[A-Z][A-Za-z.\s]{2,60}?)\s+as\s+(?:the\s+)?([A-Za-z&\s-]{3,80}?)"
    r"(?=\s+(?:of|w\.?e\.?f|with effect|effective)\b|[,;]|\.\s|$)", re.I)

_CHANGE = {"appoint": "appointed", "re-appoint": "appointed", "reappoint": "appointed", "cessation": "ceased",
           "resign": "resigned", "retire": "retired", "re-designat": "redesignated", "redesignat": "redesignated"}


def _people_from_text(detail: str) -> list[dict]:
    out = []
    for m in _NAME_RX.finditer(detail or ""):
        verb = m.group(1).lower()
        change = next((v for k, v in _CHANGE.items() if verb.startswith(k)), "changed")
        out.append({"name": " ".join(m.group(2).split()), "role": m.group(3).strip(), "change": change,
                    "effective": None, "reason": None, "background": None, "previously": []})
    return out


def linkedin_search(name: str, company: str) -> str:
    q = re.sub(r"^(mr|ms|mrs|dr|shri|smt)\.?\s+", "", name, flags=re.I)
    return "https://www.linkedin.com/search/results/people/?" + urllib.parse.urlencode({"keywords": f"{q} {company}"})


def people_card(filing: dict) -> dict:
    people = []
    if filing.get("url") and llm.available():
        texts = pdfs.pages(filing["url"], first=8)
        if texts:
            got = llm.complete_json("fast", PEOPLE_SYSTEM, PEOPLE_USER.format(text="\n".join(texts)[:12000]))
            people = (got or {}).get("people") or []
    if not people:
        people = _people_from_text(filing.get("detail", ""))
    for p in people:
        if p.get("name"):
            p["linkedin"] = linkedin_search(p["name"], filing.get("company") or filing.get("symbol", ""))
    return {"people": people[:4], "source": "Exchange filing" + (" (brief profile annexure)" if any(p.get("background") for p in people) else "")}


# ---------------------------------------------------------------------------
# One line for everything else
# ---------------------------------------------------------------------------

LINE_SYSTEM = """You summarise Indian stock-exchange filings for a busy portfolio manager.
Write ONE sentence, at most 24 words: what happened and the single number that matters
(amount, %, date) if the text gives one. Plain words, no adjectives, no 'the company has informed'.
Use only the text provided. If the filing is routine paperwork with no investment relevance,
set routine to true."""


def one_liner(filing: dict) -> dict:
    fallback = {"summary": tidy_detail(filing.get("detail", "")), "by": "exchange text"}
    if not (filing.get("url") and llm.available()):
        return fallback
    texts = pdfs.pages(filing["url"], first=3)
    if not texts:
        return fallback
    got = llm.complete_json("fast", LINE_SYSTEM,
                            'Return JSON {"summary": str, "routine": bool}\n\nSubject: '
                            f'{filing.get("subject")}\n\n' + "\n".join(texts)[:6000], max_tokens=200)
    if not got or not got.get("summary"):
        return fallback
    return {"summary": got["summary"].strip(), "routine": bool(got.get("routine")), "by": "model"}
