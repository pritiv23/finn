"""Everything numeric in a research dossier, computed in plain Python from the
company's reported multi-year tables. No model touches these numbers — a ratio is
either right or wrong, and code is cheaper and more reliable at it.
"""
from __future__ import annotations

from typing import Iterable


def _row(table: dict | None, *names: str) -> list | None:
    if not table:
        return None
    for n in names:
        if n in table["rows"]:
            return table["rows"][n]
    return None


def _aligned(table: dict | None, periods: list[str], *names: str) -> list:
    """The named row, re-indexed onto `periods` (tables don't always share columns)."""
    row = _row(table, *names)
    if not row:
        return [None] * len(periods)
    lookup = dict(zip(table["periods"], row))
    return [lookup.get(p) for p in periods]


def _add(*xs):
    return None if any(x is None for x in xs) else sum(xs)


def cagr(series: list, years: int):
    vals = [v for v in series if v is not None]
    if len(vals) < years + 1:
        return None
    a, b = vals[-years - 1], vals[-1]
    if a is None or b is None or a <= 0 or b <= 0:
        return None
    return round(((b / a) ** (1 / years) - 1) * 100, 1)


def _ratio(a, b):
    return None if a is None or b in (None, 0) else round(a / b, 2)


def _yoy(series: list, lag: int = 4) -> list:
    out = []
    for i, v in enumerate(series):
        p = series[i - lag] if i >= lag else None
        out.append(None if v is None or p in (None, 0) else round((v - p) / abs(p) * 100, 1))
    return out


def _last(xs: Iterable):
    xs = [x for x in xs if x is not None]
    return xs[-1] if xs else None


def compute(sc: dict) -> dict:
    t = sc.get("tables", {})
    pl, bs, cf, ra, q = (t.get(k) for k in ("profit-loss", "balance-sheet", "cash-flow", "ratios", "quarters"))
    lender = bool(_row(pl, "Financing Profit") or _row(q, "Financing Profit"))

    years = [p for p in (pl or {}).get("periods", []) if p != "TTM"][-6:]
    rev = _aligned(pl, years, "Sales", "Revenue")
    op = _aligned(pl, years, "Operating Profit", "Financing Profit")
    pat = _aligned(pl, years, "Net Profit")
    pbt = _aligned(pl, years, "Profit before tax")
    other = _aligned(pl, years, "Other Income")
    dep = _aligned(pl, years, "Depreciation")
    opm = [None if r in (None, 0) or o is None else round(o / r * 100, 1) for r, o in zip(rev, op)]

    cfo = _aligned(cf, years, "Cash from Operating Activity")
    fa = _aligned(bs, years, "Fixed Assets", "Net Block")
    cwip = _aligned(bs, years, "CWIP")
    capex = [None] + [
        None if None in (fa[i], fa[i - 1], dep[i]) else round((fa[i] + (cwip[i] or 0)) - (fa[i - 1] + (cwip[i - 1] or 0)) + dep[i], 1)
        for i in range(1, len(years))
    ]
    fcf = [None if c is None or x is None else round(c - x, 1) for c, x in zip(cfo, capex)]

    borrow = _aligned(bs, years, "Borrowings", "Borrowing")
    equity = [_add(a, b) for a, b in zip(_aligned(bs, years, "Equity Capital"), _aligned(bs, years, "Reserves"))]
    de = [_ratio(b, e) for b, e in zip(borrow, equity)]

    wc = _aligned(ra, years, "Working Capital Days")
    ccc = _aligned(ra, years, "Cash Conversion Cycle")
    roce = _aligned(ra, years, "ROCE %", "ROE %")

    qp = (q or {}).get("periods", [])[-8:]
    q_rev = _aligned(q, qp, "Sales", "Revenue")
    q_op = _aligned(q, qp, "Operating Profit", "Financing Profit")
    q_pat = _aligned(q, qp, "Net Profit")
    q_full = (q or {}).get("periods", [])
    full_rev = _aligned(q, q_full, "Sales", "Revenue")
    full_pat = _aligned(q, q_full, "Net Profit")
    q_rev_yoy = _yoy(full_rev)[-len(qp):] if qp else []
    q_pat_yoy = _yoy(full_pat)[-len(qp):] if qp else []
    q_opm = [None if r in (None, 0) or o is None else round(o / r * 100, 1) for r, o in zip(q_rev, q_op)]

    pairs = [(c, p) for c, p in zip(cfo[-5:], pat[-5:]) if c is not None and p is not None]
    conversion = round(sum(c for c, _ in pairs) / sum(p for _, p in pairs) * 100) if pairs and sum(p for _, p in pairs) > 0 else None

    tr = sc.get("top_ratios", {})
    ttm_rev = _row(pl, "Sales", "Revenue")[-1] if _row(pl, "Sales", "Revenue") and (pl["periods"][-1] == "TTM") else _last(rev)
    ttm_pat = _row(pl, "Net Profit")[-1] if _row(pl, "Net Profit") and (pl["periods"][-1] == "TTM") else _last(pat)

    out = {
        "lender": lender,
        "snapshot": {
            "price": tr.get("Current Price"), "market_cap": tr.get("Market Cap"), "pe": tr.get("Stock P/E"),
            "roce": tr.get("ROCE"), "roe": tr.get("ROE"), "dividend_yield": tr.get("Dividend Yield"),
            "ttm_revenue": ttm_rev, "ttm_pat": ttm_pat,
            "ttm_pat_margin": round(ttm_pat / ttm_rev * 100, 1) if ttm_rev and ttm_pat is not None else None,
            "opm": _last(opm), "de": None if lender else _last(de),
        },
        "annual": {"years": years, "revenue": rev, "operating_profit": op, "opm": opm, "pat": pat, "pbt": pbt,
                   "other_income": other, "cfo": cfo, "capex_est": capex, "fcf_est": fcf,
                   "borrowings": borrow, "equity": equity, "de": de, "wc_days": wc, "ccc": ccc, "roce": roce},
        "quarterly": {"periods": qp, "revenue": q_rev, "opm": q_opm, "pat": q_pat,
                      "revenue_yoy": q_rev_yoy, "pat_yoy": q_pat_yoy},
        "quarters_full": {"periods": q_full, "revenue": full_rev, "op": _aligned(q, q_full, "Operating Profit", "Financing Profit"),
                          "pat": full_pat},
        "trajectory": {"revenue_cagr_3y": cagr(rev, 3), "revenue_cagr_5y": cagr(rev, 5),
                       "pat_cagr_3y": cagr(pat, 3), "pat_cagr_5y": cagr(pat, 5)},
        "cash": {"conversion_5y_pct": conversion,
                 "fcf_5y": round(sum(x for x in fcf[-5:] if x is not None), 1) if any(x is not None for x in fcf[-5:]) else None,
                 "negative_fcf_years": sum(1 for x in fcf[-5:] if x is not None and x < 0)},
    }
    out["flags"] = flags(out)
    return out


def _span(xs: list, n: int = 3):
    """(value n periods ago, latest) using only populated points."""
    pts = [x for x in xs if x is not None]
    if len(pts) < 2:
        return None, None
    return pts[max(0, len(pts) - 1 - n)], pts[-1]


def flags(m: dict) -> list[dict]:
    """Plain-language observations a careful analyst would note. Thresholds are deliberately simple."""
    a, out = m["annual"], []

    def add(tone, section, text):
        out.append({"tone": tone, "section": section, "text": text})

    conv = m["cash"]["conversion_5y_pct"]
    if conv is not None:
        if conv < 70:
            add("bad", "cash", f"Only {conv}% of the last five years' profit showed up as operating cash.")
        elif conv >= 100:
            add("good", "cash", f"Operating cash ran at {conv}% of reported profit over five years.")
    if m["cash"]["negative_fcf_years"] >= 3:
        add("watch", "cash", f"Free cash flow (estimated) was negative in {m['cash']['negative_fcf_years']} of the last 5 years.")

    o0, o1 = _span(a["opm"])
    if o0 is not None and o1 is not None:
        if o1 - o0 <= -3:
            add("bad", "trajectory", f"Operating margin compressed from {o0:.0f}% to {o1:.0f}% over three years.")
        elif o1 - o0 >= 3:
            add("good", "trajectory", f"Operating margin expanded from {o0:.0f}% to {o1:.0f}% over three years.")

    g = m["trajectory"]["revenue_cagr_3y"]
    p = m["trajectory"]["pat_cagr_3y"]
    if g is not None and p is not None and g - p >= 8:
        add("watch", "trajectory", f"Profit grew slower than sales ({p:.0f}% vs {g:.0f}% a year, 3-year CAGR).")

    if not m["lender"]:
        d0, d1 = _span(a["de"])
        if d1 is not None and d1 > 1:
            add("watch", "balance", f"Debt is {d1:.1f}× equity.")
        elif d0 is not None and d1 is not None and d1 - d0 >= 0.3:
            add("bad", "balance", f"Leverage rose from {d0:.1f}× to {d1:.1f}× debt-to-equity in three years.")
        elif d1 is not None and d1 < 0.1:
            add("good", "balance", "Practically debt-free.")
        w0, w1 = _span(a["wc_days"])
        if w0 is not None and w1 is not None and w1 - w0 >= 20:
            add("bad", "balance", f"Working-capital cycle stretched from {w0:.0f} to {w1:.0f} days.")
        elif w0 is not None and w1 is not None and w0 - w1 >= 20:
            add("good", "balance", f"Working-capital cycle tightened from {w0:.0f} to {w1:.0f} days.")

    oi, pbt = _last(a["other_income"]), _last(a["pbt"])
    if oi and pbt and pbt > 0 and oi / pbt > 0.25:
        add("watch", "trajectory", f"Other income is {oi / pbt * 100:.0f}% of pre-tax profit — not all earnings are operating.")
    return out
