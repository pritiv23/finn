"""Write the bundled *sample* data the app falls back to when no real snapshot exists.

Everything here is illustrative: synthetic prices, invented filings, a fictional
company for the research dossier. The app labels it as sample data on every
screen. Run `python -m finn demo` to replace it with the real thing.

The filings still go through the real classifier and enrichment code, so the
sample exercises the same paths real data does.
"""
from __future__ import annotations

import datetime as dt
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from finn.config import DATA_OUT, load_portfolio  # noqa: E402
from finn.pull import guidance, metrics  # noqa: E402
from finn.push.classify import classify, tidy_detail  # noqa: E402
from finn.push.enrich import _rows_from_triplets, linkedin_search  # noqa: E402
from finn.sources.screener import parse_company  # noqa: E402
from tests.fixtures import page  # noqa: E402

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
NOW = dt.datetime(2026, 10, 30, 8, 30, tzinfo=IST)
OUT = DATA_OUT / "sample"

BASE = {"RELIANCE": 1480, "HDFCBANK": 1010, "TCS": 3150, "ITC": 412, "LT": 3920, "BAJFINANCE": 1045, "SUNPHARMA": 1690,
        "MARUTI": 16200, "TITAN": 3720, "ETERNAL": 318, "DMART": 4210, "HAL": 4730, "DIXON": 15800, "POLYCAB": 7350,
        "PERSISTENT": 5980, "KPITTECH": 1240, "CDSL": 1590, "DEEPAKNTR": 1880}

# (symbol, close move on last day %, volume multiple on last day)
LAST_DAY = {"DIXON": (6.2, 3.1), "KPITTECH": (-4.8, 1.7), "TITAN": (3.1, 2.4), "BAJFINANCE": (-1.9, 1.3)}


def prices(symbol: str) -> list[list]:
    rnd = random.Random(symbol)
    px, vol0 = BASE[symbol], rnd.randint(4, 60) * 100_000
    days, d = [], NOW.date() - dt.timedelta(days=130)
    while len(days) < 90:
        d += dt.timedelta(days=1)
        if d.weekday() < 5:
            days.append(d)
    rows = []
    for i, day in enumerate(days):
        if i == len(days) - 1 and symbol in LAST_DAY:
            move, mult = LAST_DAY[symbol]
            px = px * (1 + move / 100)
            avg = sum(r[2] for r in rows[-20:]) / 20
            vol = int(avg * mult)
        else:
            px *= 1 + rnd.gauss(0.0006, 0.013)
            vol = int(vol0 * rnd.uniform(0.6, 1.4))
        rows.append([day.isoformat(), round(px, 2), vol])
    return rows


def ago(hours: float) -> str:
    return (NOW - dt.timedelta(hours=hours)).isoformat(timespec="seconds")


# Invented filings, written the way NSE phrases them.
RAW = [
    ("TITAN", 14, "Outcome of Board Meeting", "Titan Company Limited has informed the Exchange regarding Board meeting held on October 29, 2026 approving the Unaudited Financial Results for the quarter ended September 30, 2026."),
    ("BAJFINANCE", 9, "Change in Directors/ Key Managerial Personnel/ Auditor/ Compliance Officer/ Share Transfer Agent", "Bajaj Finance Limited has informed the Exchange regarding Cessation of Mr. Arvind Mehta as Chief Financial Officer w.e.f. October 31, 2026 and appointment of Ms. Kavita Iyer as Chief Financial Officer w.e.f. November 1, 2026."),
    ("DIXON", 20, "Acquisition", "Dixon Technologies (India) Limited has informed the Exchange regarding execution of definitive agreements to acquire 51% stake in Ravel Display Systems Private Limited for a consideration of Rs 320 crore."),
    ("PERSISTENT", 30, "Outcome of Board Meeting", "Persistent Systems Limited has informed the Exchange regarding approval of the audited financial results for the quarter ended September 30, 2026 and declaration of interim dividend."),
    ("HAL", 6, "Press Release", "Hindustan Aeronautics Limited has informed the Exchange that it has received an order worth Rs 2,410 crore from the Ministry of Defence for overhaul of aero-engines."),
    ("LT", 11, "Press Release", "Larsen & Toubro Limited has informed the Exchange that its Buildings & Factories business has secured a significant order (Rs 1,000-2,500 crore) for a data-centre campus in Navi Mumbai."),
    ("KPITTECH", 16, "Analysts/Institutional Investor Meet/Con. Call Updates", "KPIT Technologies Limited has informed the Exchange regarding Transcript of the earnings conference call held on October 24, 2026."),
    ("LT", 40, "Credit Rating", "Larsen & Toubro Limited has informed the Exchange regarding CRISIL has reaffirmed its rating at CRISIL AAA/Stable on the long-term bank facilities."),
    ("ITC", 22, "Record Date", "ITC Limited has informed the Exchange that the record date for the purpose of interim dividend of Rs 6.50 per share is November 6, 2026."),
    ("ETERNAL", 52, "Updates", "Eternal Limited has informed the Exchange regarding incorporation of a wholly owned subsidiary, Blinkit Logistics Private Limited."),
    ("SUNPHARMA", 64, "Updates", "Sun Pharmaceutical Industries Limited has informed the Exchange that the USFDA has completed an inspection of the Dadra facility with an Establishment Inspection Report (EIR) indicating closure."),
    ("POLYCAB", 70, "Board Meeting Intimation", "Polycab India Limited has informed the Exchange that a meeting of the Board will be held on November 4, 2026 to consider the financial results for the quarter ended September 30, 2026."),
    ("MARUTI", 26, "Updates", "Maruti Suzuki India Limited has informed the Exchange regarding production volume for the month of October 2026."),
    ("DEEPAKNTR", 90, "Change in Directors/ Key Managerial Personnel/ Auditor/ Compliance Officer/ Share Transfer Agent", "Deepak Nitrite Limited has informed the Exchange regarding appointment of Mr. Sanjay Kulkarni as an Additional Independent Director."),
    ("HDFCBANK", 8, "Allotment of Securities", "HDFC Bank Limited has informed the Exchange regarding allotment of 4,21,330 equity shares under ESOS."),
    ("HDFCBANK", 31, "Allotment of Securities", "HDFC Bank Limited has informed the Exchange regarding allotment of 1,88,045 equity shares under ESOS."),
    ("TITAN", 13, "Copy of Newspaper Publication", "Titan Company Limited has informed the Exchange regarding newspaper advertisement of the financial results for the quarter ended September 30, 2026."),
    ("PERSISTENT", 28, "Copy of Newspaper Publication", "Persistent Systems Limited has informed the Exchange regarding newspaper publication of financial results."),
    ("TCS", 18, "Analysts/Institutional Investor Meet/Con. Call Updates", "Tata Consultancy Services Limited has informed the Exchange regarding schedule of analyst / institutional investor meetings."),
    ("TCS", 66, "Analysts/Institutional Investor Meet/Con. Call Updates", "Tata Consultancy Services Limited has informed the Exchange regarding schedule of one-on-one meetings with investors."),
    ("RELIANCE", 15, "Certificate under SEBI (Depositories and Participants) Regulations, 2018", "Reliance Industries Limited has informed the Exchange regarding a certificate under Regulation 74(5)."),
    ("RELIANCE", 44, "Updates", "Reliance Industries Limited has informed the Exchange regarding loss of share certificates."),
    ("CDSL", 21, "Trading Window", "Central Depository Services (India) Limited has informed the Exchange regarding closure of trading window."),
    ("DMART", 12, "Shareholders meeting", "Avenue Supermarts Limited has informed the Exchange regarding scrutinizer's report on postal ballot."),
    ("DMART", 58, "Business Responsibility and Sustainability Reporting (BRSR)", "Avenue Supermarts Limited has informed the Exchange regarding Business Responsibility and Sustainability Report."),
    ("KPITTECH", 5, "Analysts/Institutional Investor Meet/Con. Call Updates", "KPIT Technologies Limited has informed the Exchange regarding audio recording of the earnings call."),
    ("SUNPHARMA", 33, "Trading Window", "Sun Pharmaceutical Industries Limited has informed the Exchange regarding closure of trading window."),
    ("MARUTI", 80, "Copy of Newspaper Publication", "Maruti Suzuki India Limited has informed the Exchange regarding notice to shareholders for transfer of shares to IEPF."),
    ("BAJFINANCE", 36, "Updates", "Bajaj Finance Limited has informed the Exchange regarding allotment of non-convertible debentures on private placement basis."),
    ("BAJFINANCE", 120, "Updates", "Bajaj Finance Limited has informed the Exchange regarding allotment of commercial paper."),
    ("HAL", 100, "Analysts/Institutional Investor Meet/Con. Call Updates", "Hindustan Aeronautics Limited has informed the Exchange regarding intimation of earnings conference call scheduled on November 10, 2026."),
    ("ITC", 140, "Allotment of Securities", "ITC Limited has informed the Exchange regarding allotment of 3,12,000 ordinary shares under ITC Employee Stock Option Scheme."),
    ("POLYCAB", 3, "Trading Window", "Polycab India Limited has informed the Exchange regarding closure of trading window."),
    ("ETERNAL", 10, "Updates", "Eternal Limited has informed the Exchange regarding allotment of equity shares under ESOP 2021."),
    ("CDSL", 75, "Copy of Newspaper Publication", "Central Depository Services (India) Limited has informed the Exchange regarding newspaper publication of notice of board meeting."),
    ("DEEPAKNTR", 17, "Certificate under SEBI (Depositories and Participants) Regulations, 2018", "Deepak Nitrite Limited has informed the Exchange regarding certificate under Regulation 74(5)."),
    ("TCS", 150, "Updates", "Tata Consultancy Services Limited has informed the Exchange regarding a partnership with a European insurer to modernise its policy administration platform."),
]

RESULTS = {
    # symbol: (revenue, ebitda, pbt, pat) as (cur, prev, year_ago), ₹ cr — invented
    "TITAN": ((16_420, 15_210, 13_930), (1_905, 1_710, 1_580), (1_520, 1_340, 1_255), (1_120, 990, 935)),
    "PERSISTENT": ((3_640, 3_510, 3_062), (632, 601, 521), (565, 540, 461), (418, 401, 340)),
}

PEOPLE = {
    "BAJFINANCE": [
        {"name": "Mr. Arvind Mehta", "role": "Chief Financial Officer", "change": "ceased", "effective": "31 Oct 2026",
         "reason": "To pursue opportunities outside the group", "background": None, "previously": []},
        {"name": "Ms. Kavita Iyer", "role": "Chief Financial Officer", "change": "appointed", "effective": "1 Nov 2026",
         "reason": None, "background": "Chartered accountant with 22 years in financial services; most recently Head of Treasury and Investor Relations at the company.",
         "previously": ["Head of Treasury & IR, Bajaj Finance", "Deputy CFO, a private-sector bank", "Audit, Big Four firm"]},
    ],
}

LINES = {
    "DIXON": "Buying 51% of Ravel Display Systems for ₹320 cr — adds display-module capacity in-house.",
    "PERSISTENT": None,
}


def filings() -> list[dict]:
    out = []
    for i, (sym, hrs, subject, detail) in enumerate(RAW):
        f = {"id": f"sample-{i}", "symbol": sym, "subject": subject, "detail": detail, "time": ago(hrs), "url": "", "source": "NSE"}
        f.update(classify(subject, detail))
        if f["category"] == "results" and f["tier"] == 3 and sym in RESULTS:
            rows = _rows_from_triplets(*RESULTS[sym])
            f["results"] = {"rows": rows, "basis": "consolidated", "quarters": ["Q2 FY27", "Q1 FY27", "Q2 FY26"], "unit": "₹ cr",
                            "source": "Results filing (PDF)", "cross_checked": True,
                            "ebitda_margin": round(rows[1]["value"] / rows[0]["value"] * 100, 1)}
        elif f["category"] == "management_change" and sym in PEOPLE:
            people = PEOPLE[sym]
            for p in people:
                p["linkedin"] = linkedin_search(p["name"], sym)
            f["people"] = {"people": people, "source": "Exchange filing (brief profile annexure)"}
        elif f["category"] == "management_change":
            f["people"] = {"people": [], "source": "Exchange filing"}
            f["summary"] = tidy_detail(detail)
        elif f["tier"] == 3:
            f["summary"] = LINES.get(sym) or tidy_detail(detail)
        elif f["tier"] == 2:
            f["summary"] = tidy_detail(detail)
        out.append(f)
    out.sort(key=lambda f: f["time"], reverse=True)
    return out


def snapshot() -> dict:
    pf = load_portfolio()
    names = {h.symbol: h.name for h in pf.holdings}
    fl = filings()
    for f in fl:
        f["name"] = names.get(f["symbol"], f["symbol"])
    return {
        "generated_at": NOW.isoformat(timespec="seconds"), "window_days": 7, "sample": True,
        "model": "sample data", "defaults": pf.alerts.__dict__,
        "holdings": [{"symbol": h.symbol, "name": h.name, "sector": h.sector, "eod": prices(h.symbol)} for h in pf.holdings],
        "filings": fl,
    }


def dossier() -> dict:
    sc = parse_company(page(), "https://www.screener.in/")
    sc["basis"] = "consolidated"
    m = metrics.compute(sc)
    items = [
        {"metric": "revenue_growth", "quote": "We remain confident of 15 to 18% revenue growth for FY27, led by the built-in category.",
         "target_low": 15, "target_high": 18, "unit": "%", "horizon": "FY27", "page": 4, "speaker": "CFO", "call": "Jul 2026"},
        {"metric": "ebitda_margin", "quote": "We should exit FY26 at a 14% EBITDA margin as the new plant stabilises.",
         "target_low": 14, "target_high": None, "unit": "%", "horizon": "FY26", "page": 6, "speaker": "MD", "call": "Jul 2025"},
        {"metric": "revenue_growth", "quote": "For the full year FY26, we are guiding to mid-teens growth.",
         "target_low": 14, "target_high": 16, "unit": "%", "horizon": "FY26", "page": 3, "speaker": "MD", "call": "Oct 2025"},
        {"metric": "capacity", "quote": "The Sanand plant will be commissioned by Q3 FY27, taking capacity to 2.4 million units.",
         "target_low": None, "target_high": None, "unit": None, "horizon": "Q3 FY27", "page": 7, "speaker": "MD", "call": "Oct 2026"},
        {"metric": "other", "quote": "Working capital should come back to around 70 days by year-end.",
         "target_low": 70, "target_high": None, "unit": "other", "horizon": "FY26", "page": 9, "speaker": "CFO", "call": "Jan 2026"},
    ]
    for i, it in enumerate(items, 1):
        it["id"] = f"G{i}"
        it["source_url"] = ""
        guidance.check(it, m)
    items[3].update(verdict="too_early", why="Plant is due Q3 FY27; Q2 FY27 is the latest reported quarter.", judged_by="model")
    items[4].update(verdict="missed", why="Working-capital days were 92 at FY26 year-end against ~70 promised.", judged_by="model")
    tally: dict = {}
    for it in items:
        tally[it["verdict"]] = tally.get(it["verdict"], 0) + 1
    m.pop("quarters_full", None)
    return {
        "symbol": "MERIDIAN", "name": "Meridian Appliances Ltd", "sample": True,
        "about": "A fictional kitchen-appliance maker, used to show the research view without live data.",
        "generated_at": NOW.isoformat(timespec="seconds"), "basis": "consolidated", "model": "sample data",
        "metrics": m,
        "guidance": {"items": items, "calls": [{"period": p, "transcript": ""} for p in ("Oct 2026", "Jul 2026", "Jan 2026", "Oct 2025")], "tally": tally},
        "synthesis": {
            "one_line": "Growth is real and ahead of guidance, but it is being bought with working capital: profit is not turning into cash.",
            "business": {"summary": "Designs and manufactures kitchen appliances — hobs, chimneys and built-in ovens — sold through dealers and modern retail in India.",
                         "segments": [{"name": "Built-in appliances", "share_pct": 46, "note": "fastest-growing", "source": "AR"},
                                      {"name": "Cooktops & chimneys", "share_pct": 38, "note": "mature", "source": "AR"},
                                      {"name": "Exports", "share_pct": 16, "note": "Middle East OEM", "source": "AR"}]},
            "narrative_vs_numbers": [
                {"claim": "Management calls FY26 'a year of cash discipline'.", "reality": "Cash from operations was 67% of profit in FY26; working-capital days rose to 92.", "stance": "diverges", "source": "FIN"},
                {"claim": "Built-in category is driving growth.", "reality": "Revenue grew 18% in FY26 and 16% in H1 FY27, consistent with mix commentary.", "stance": "agrees", "source": "T1"},
                {"claim": "Margins to expand as the new plant stabilises.", "reality": "Operating margin has held at 12–13% for eight quarters; no expansion yet.", "stance": "diverges", "source": "G2"},
            ],
            "guidance_now": [{"metric": "Revenue growth", "what": "15–18% for FY27", "source": "T2"},
                             {"metric": "Capacity", "what": "Sanand plant by Q3 FY27, 2.4 mn units", "source": "T1"}],
            "bull": [{"point": "Revenue compounding at 14% a year for five years with steady 12–13% margins.", "source": "FIN"},
                     {"point": "H1 FY27 growth of 16% is inside the 15–18% guided range.", "source": "G1"},
                     {"point": "New capacity adds headroom just as built-in demand is growing.", "source": "T1"}],
            "bear": [{"point": "65% cash conversion over five years: growth is being funded by receivables and inventory.", "source": "FIN"},
                     {"point": "Free cash flow (est.) negative in four of the last five years; borrowings up 2.5× since FY21.", "source": "FIN"},
                     {"point": "Two margin and working-capital promises missed in the last year.", "source": "G2"}],
        },
        "sources": [{"id": "FIN", "label": "Reported financials (sample)", "url": ""},
                    {"id": "T1", "label": "Concall transcript, Oct 2026 (sample)", "url": ""},
                    {"id": "T2", "label": "Concall transcript, Jul 2026 (sample)", "url": ""},
                    {"id": "AR", "label": "Annual report FY26 (sample)", "url": ""}],
    }


def main():
    (OUT / "research").mkdir(parents=True, exist_ok=True)
    (OUT / "snapshot.json").write_text(json.dumps(snapshot(), ensure_ascii=False, indent=0))
    (OUT / "research" / "MERIDIAN.json").write_text(json.dumps(dossier(), ensure_ascii=False, indent=0))
    (OUT / "research" / "index.json").write_text(json.dumps(["MERIDIAN"]))
    print("sample data written to", OUT)


if __name__ == "__main__":
    main()
