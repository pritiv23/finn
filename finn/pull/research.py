"""Assemble a research dossier for any NSE symbol.

Cost shape per company (first run; re-runs hit the cache and cost nothing):
  - 0 model calls for every number, ratio, chart and flag
  - ≤4 fast-model calls to list guidance in the last four transcripts
  - 1 smart-model call to weigh narrative against numbers and write bull/bear

Grounding: the smart model receives only (a) our computed numbers, (b) verbatim
transcript excerpts and (c) annual-report MD&A excerpts, each with a source id,
and must cite one for every point. It is told not to use outside knowledge.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re

from .. import llm
from ..config import DATA_OUT
from ..sources import pdfs, screener
from . import guidance, metrics

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

SYNTH_SYSTEM = """You are a sceptical buy-side analyst. You are given ONLY: computed financials
for one Indian listed company, guidance statements management made on recent earnings calls
(with code-checked verdicts where measurable), and short excerpts from the annual report and
the latest call. Use nothing else: no outside knowledge of the company, no news, no broker views.
Every point must cite a source id from the inputs (FIN, AR, T1..T4, G1..Gn).
Write tight: each point at most 30 words. Prefer numbers to adjectives. If the inputs don't
support a section, return an empty list for it rather than padding."""

SYNTH_USER = """Company: {name} ({symbol})

FIN — computed from reported financials (₹ crore unless stated):
{fin}

Guidance found on calls (G ids), with verdicts computed by code where measurable:
{guid}

AR — annual report, management discussion excerpts:
{ar}

T1 — latest call, opening remarks excerpt:
{opening}

Return JSON:
{{"business": {{"summary": str (<=50 words: what they sell, to whom, how they make money),
               "segments": [{{"name": str, "share_pct": number|null, "note": str, "source": str}}]}},
 "verdicts": [{{"id": "G..", "verdict": "delivered"|"missed"|"on_track"|"behind"|"too_early"|"unmeasurable", "why": str}}]
             (only for guidance the code marked unmeasurable but the inputs let you judge),
 "narrative_vs_numbers": [{{"claim": str, "reality": str, "stance": "agrees"|"diverges"|"unclear", "source": str}}] (3-5),
 "guidance_now": [{{"metric": str, "what": str, "source": str}}] (what management currently guides, latest call first),
 "bull": [{{"point": str, "source": str}}] (3),
 "bear": [{{"point": str, "source": str}}] (3),
 "one_line": str (<=25 words: the single thing an investor should take away)}}"""


def _fin_digest(m: dict) -> str:
    a, q = m["annual"], m["quarterly"]

    def row(name, xs, suffix=""):
        return f"{name}: " + ", ".join(f"{y}={'' if v is None else round(v, 1)}{suffix}" for y, v in zip(a["years"], xs))

    lines = [row("Revenue", a["revenue"]), row("Operating margin", a["opm"], "%"), row("PAT", a["pat"]),
             row("Cash from operations", a["cfo"]), row("FCF (est.)", a["fcf_est"]), row("Debt/Equity", a["de"]),
             row("Working-capital days", a["wc_days"]),
             "Quarterly revenue YoY %: " + ", ".join(f"{p}={v}" for p, v in zip(q["periods"], q["revenue_yoy"])),
             "Quarterly operating margin %: " + ", ".join(f"{p}={v}" for p, v in zip(q["periods"], q["opm"])),
             f"Trajectory: {json.dumps(m['trajectory'])}", f"Cash: {json.dumps(m['cash'])}",
             "Flags: " + "; ".join(f["text"] for f in m["flags"])]
    return "\n".join(lines)


def _guid_digest(items: list[dict]) -> str:
    return "\n".join(
        f"{g['id']} [{g['call']}, p{g.get('page')}] {g['metric']} target {g.get('target_low')}–{g.get('target_high')} "
        f"{g.get('horizon')}: \"{g['quote']}\" → code verdict: {g['verdict']}"
        + (f" (actual {g['actual']}% {g['basis']})" if g.get("actual") is not None else "")
        for g in items) or "none found"


def _ar_excerpt(sc: dict, budget: int = 6000) -> tuple[str, dict | None]:
    if os.getenv("FINN_SKIP_AR") or not sc.get("annual_reports"):
        return "", None
    ar = sorted(sc["annual_reports"], key=lambda r: r.get("year") or 0, reverse=True)[0]
    texts = pdfs.pages(ar["url"], fast=True)
    if not texts:
        return "", None
    hits = pdfs.find_pages(texts, [r"management discussion", r"segment(al)? (performance|review|information)",
                                   r"business overview", r"revenue mix"], window=1)[:8]
    body = "\n".join(" ".join(texts[i].split())[:1500] for i in hits)
    return body[:budget], {"id": "AR", "label": ar.get("label") or f"Annual report {ar.get('year')}", "url": ar["url"]}


def _opening(call: dict | None, budget: int = 3500) -> str:
    if not call or not call.get("transcript"):
        return ""
    texts = pdfs.pages(call["transcript"], first=6, fast=True)
    joined = " ".join(" ".join(t.split()) for t in texts[1:])     # page 1 is the cover/participants
    m = re.search(r"(good (morning|afternoon|evening)|thank you).{0,40}(everyone|all)", joined, re.I)
    return joined[m.start():m.start() + budget] if m else joined[:budget]


def build(symbol: str, progress=lambda stage: None) -> dict:
    symbol = symbol.upper().strip()
    progress("Reading reported financials")
    sc = screener.company(symbol)
    if not sc:
        raise LookupError(f"No financials found for {symbol}. Check the NSE symbol.")
    m = metrics.compute(sc)

    progress(f"Reading {min(4, len([c for c in sc.get('concalls', []) if c.get('transcript')]))} concall transcripts")
    pvd = guidance.promised_vs_delivered(sc, m)

    sources = [{"id": "FIN", "label": f"Reported financials ({sc.get('basis', '')})", "url": sc.get("url")}]
    for i, c in enumerate(pvd["calls"], 1):
        sources.append({"id": f"T{i}", "label": f"Concall transcript, {c['period']}", "url": c["transcript"]})

    synthesis = None
    if llm.available():
        progress("Reading the annual report")
        ar_text, ar_src = _ar_excerpt(sc)
        if ar_src:
            sources.append(ar_src)
        progress("Weighing what management said against the numbers")
        synthesis = llm.complete_json("smart", SYNTH_SYSTEM, SYNTH_USER.format(
            name=sc.get("name") or symbol, symbol=symbol, fin=_fin_digest(m), guid=_guid_digest(pvd["items"]),
            ar=ar_text or "not available", opening=_opening(pvd["calls"][0] if pvd["calls"] else None) or "not available"),
            max_tokens=2500)
        # Fold the model's qualitative verdicts back into unmeasurable items only:
        # a code verdict is never overwritten.
        by_id = {g["id"]: g for g in pvd["items"]}
        for v in (synthesis or {}).get("verdicts", []):
            g = by_id.get(v.get("id"))
            if g and g["verdict"] == "unmeasurable" and v.get("verdict"):
                g.update(verdict=v["verdict"], why=v.get("why"), judged_by="model")

    m.pop("quarters_full", None)
    return {
        "symbol": symbol,
        "name": sc.get("name") or symbol,
        "about": sc.get("about", ""),
        "generated_at": dt.datetime.now(IST).isoformat(timespec="seconds"),
        "basis": sc.get("basis"),
        "model": llm.describe(),
        "metrics": m,
        "guidance": pvd,
        "synthesis": synthesis,
        "sources": sources,
    }


def write(dossier: dict) -> str:
    out = DATA_OUT / "research"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{dossier['symbol']}.json"
    path.write_text(json.dumps(dossier, ensure_ascii=False, separators=(",", ":")))
    index = sorted(p.stem for p in out.glob("*.json") if p.stem != "index")
    (out / "index.json").write_text(json.dumps(index))
    return str(path)
