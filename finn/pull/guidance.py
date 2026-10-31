"""Promised vs delivered.

1. Take the last four concall transcripts.
2. Keep only the paragraphs that sound like guidance (a keyword-and-number filter
   cuts each transcript by ~80% before any model sees it).
3. A cheap model lists management's forward-looking statements, with the quote
   and page, as structured targets ("revenue growth, 15–18%, FY27").
4. Code checks each numeric target against the numbers reported *after* the
   call. The verdict on a measurable promise is arithmetic, not opinion.
5. What can't be measured (a launch, a plant, "margins will improve") is left
   for the single smart-model call in research.py, which sees the quotes and
   the numbers side by side.
"""
from __future__ import annotations

import re

from .. import llm
from ..sources import pdfs

KEYWORDS = re.compile(
    r"guid|expect|target|outlook|aspir|aim\b|going forward|next (year|quarter|fiscal)|this (year|fiscal)|"
    r"\bfy ?'?\d{2}|\bh[12]\b|medium[- ]term|double[- ]digit|margin|growth|grow|capex|capacity|"
    r"run[- ]rate|peak revenue|breakeven|order book|pipeline", re.I)
NUMBERY = re.compile(r"\d")

EXTRACT_SYSTEM = """You read earnings-call transcripts of Indian listed companies.
List forward-looking statements made by MANAGEMENT (not analysts, not the moderator)
about the company's own future numbers or milestones: revenue/sales growth, EBITDA or
operating margin, profit growth, capex, capacity, volumes, launches.
Rules: quote must be verbatim from the text, at most 35 words. Map vague numbers:
'double-digit' -> target_low 10; 'mid-teens' -> 14 to 16; 'high single digit' -> 7 to 9.
If no number is given, leave targets null. Do not invent anything not in the text.
ONLY statements about the FUTURE (will, expect, target, guide, aim, plan, should, going forward).
SKIP anything that reports results already achieved ("revenue for the year was...", "we grew 26%"):
those are not promises. Use metric "ebitda_margin" only when the number is a margin (% of revenue);
growth in EBITDA is metric "other"."""

EXTRACT_USER = """Call: {label}
Return JSON {{"items": [{{"metric": "revenue_growth"|"ebitda_margin"|"pat_growth"|"capex"|"capacity"|"volume"|"other",
 "quote": str, "target_low": number|null, "target_high": number|null, "unit": "%"|"cr"|"other"|null,
 "horizon": str (as said, e.g. "FY27", "next year", "H2", "medium term"), "page": int, "speaker": str|null}}]}}
At most 5 items, most important first. Return an empty list if there is no forward-looking guidance.

Excerpts (page numbers in brackets):
{text}"""

MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def _ym(label: str):
    m = re.match(r"([A-Za-z]{3})\w*\s+(\d{4})", label or "")
    return (int(m.group(2)), MONTHS.get(m.group(1).lower())) if m else None


def fiscal_year(year: int, month: int) -> int:
    """Indian FY: Apr 2026–Mar 2027 is FY27 (returned as 2027)."""
    return year + 1 if month >= 4 else year


def excerpts(url: str, budget: int = 9000) -> str:
    texts = pdfs.pages(url, fast=True)
    keep, used = [], 0
    for pno, page in enumerate(texts, 1):
        for para in re.split(r"\n(?=[A-Z][a-zA-Z .]{2,40}:)|\n\s*\n", page):
            p = " ".join(para.split())
            if len(p) < 60 or not (KEYWORDS.search(p) and NUMBERY.search(p)):
                continue
            if re.match(r"^(moderator|operator)\b", p, re.I):
                continue
            chunk = f"[p{pno}] {p[:900]}"
            if used + len(chunk) > budget:
                return "\n".join(keep)
            keep.append(chunk)
            used += len(chunk)
    return "\n".join(keep)


def extract(call: dict) -> list[dict]:
    if not call.get("transcript"):
        return []
    text = excerpts(call["transcript"])
    if not text:
        return []
    got = llm.complete_json("fast", EXTRACT_SYSTEM, EXTRACT_USER.format(label=call["period"], text=text), max_tokens=1500)
    items = (got or {}).get("items") or []
    for it in items:
        it["call"] = call["period"]
        it["source_url"] = call["transcript"]
    return items


# ---------------------------------------------------------------------------
# Checking a promise against what was reported
# ---------------------------------------------------------------------------

def _horizon_fy(horizon: str, call_ym) -> int | None:
    h = (horizon or "").lower()
    m = re.search(r"fy\s?'?(\d{2,4})", h)
    if m:
        y = int(m.group(1))
        return y + 2000 if y < 100 else y
    if call_ym is None:
        return None
    cur = fiscal_year(*call_ym)
    if re.search(r"this (year|fiscal)|current (year|fiscal)|full year|for the year", h):
        return cur
    if re.search(r"next (year|fiscal)", h):
        return cur + 1
    return None


def _quarters_by_fy(metrics: dict):
    """{fy: [(period, revenue, op_profit, pat), ...]} from the full quarterly table."""
    q = metrics["quarters_full"]
    out: dict[int, list] = {}
    for p, r, o, n in zip(q["periods"], q["revenue"], q["op"], q["pat"]):
        ym = _ym(p)
        if ym:
            out.setdefault(fiscal_year(*ym), []).append((p, r, o, n))
    return out


def _sum(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) if xs else None


def check(item: dict, metrics: dict) -> dict:
    """Adds `actual`, `verdict` and `basis` to a guidance item where it can be measured."""
    metric = item.get("metric")
    lo, hi = item.get("target_low"), item.get("target_high")
    item["verdict"], item["actual"], item["basis"] = "unmeasurable", None, None
    if metric not in ("revenue_growth", "ebitda_margin", "pat_growth") or (lo is None and hi is None):
        return item
    if item.get("unit") not in (None, "%"):
        return item

    call_ym = _ym(item.get("call", ""))
    fy = _horizon_fy(item.get("horizon", ""), call_ym)
    by_fy = _quarters_by_fy(metrics)
    if fy is None:
        # Open-ended ("medium term", "going forward"): judge the quarters since the call.
        fy = fiscal_year(*call_ym) if call_ym else None
    if fy is None or fy not in by_fy:
        item["verdict"] = "too_early"
        return item

    cur, prev = by_fy.get(fy, []), by_fy.get(fy - 1, [])
    n = len(cur)
    complete = n == 4
    if metric == "ebitda_margin":
        rev, op = _sum(r for _, r, _, _ in cur), _sum(o for _, _, o, _ in cur)
        actual = round(op / rev * 100, 1) if rev and op is not None else None
        tol = 0.5
    else:
        idx = 1 if metric == "revenue_growth" else 3
        now = _sum(row[idx] for row in cur)
        before = _sum(row[idx] for row in prev[:n]) if len(prev) >= n else None
        actual = round((now - before) / abs(before) * 100, 1) if now is not None and before else None
        tol = 1.0
    if actual is None:
        item["basis"] = "not enough reported history to compare"
        return item

    item["actual"] = actual
    item["basis"] = f"FY{str(fy)[2:]} {'full year' if complete else f'first {n} quarter' + ('s' if n > 1 else '')}"
    floor = lo if lo is not None else hi
    if actual + tol >= floor:
        item["verdict"] = "delivered" if complete else "on_track"
        if hi is not None and actual > hi + tol:
            item["verdict"] = "beat" if complete else "ahead"
    else:
        item["verdict"] = "missed" if complete else "behind"
    return item


FUTURE = re.compile(r"\b(will|would|expect|anticipat|target|guid|aim|aspir|plan|should|going forward|outlook|"
                    r"next (year|quarter|fiscal)|by fy|in fy|over the next|medium[- ]term|looking ahead|intend|envisage|confident|on track)", re.I)


def is_forward(item: dict) -> bool:
    """Code-side guard against the model passing off reported results as promises."""
    if not FUTURE.search(item.get("quote") or ""):
        return False
    fy = _horizon_fy(item.get("horizon", ""), _ym(item.get("call", "")))
    call = _ym(item.get("call", ""))
    if fy is not None and call is not None and fy < fiscal_year(*call):
        return False                      # talks about a year that had already ended
    return True


def promised_vs_delivered(sc: dict, metrics: dict, max_calls: int = 4) -> dict:
    calls = [c for c in sc.get("concalls", []) if c.get("transcript")][:max_calls]
    if not llm.available():
        return {"items": [], "calls": calls, "note": "Add a model key (see README) to read transcripts."}
    items: list[dict] = []
    seen: set[str] = set()
    for c in calls:
        for it in extract(c):
            key = re.sub(r"\W+", "", (it.get("quote") or "").lower())[:60]
            if key and key not in seen and is_forward(it):
                seen.add(key)
                items.append(it)
    for i, it in enumerate(items):
        it["id"] = f"G{i + 1}"
        check(it, metrics)
    tally: dict[str, int] = {}
    for it in items:
        tally[it["verdict"]] = tally.get(it["verdict"], 0) + 1
    return {"items": items, "calls": calls, "tally": tally}
