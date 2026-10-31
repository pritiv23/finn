"""A synthetic screener.in-shaped page for a fictional company, so parsing and
metrics can be tested offline. Structure mirrors the real page; numbers are made up."""

QUARTERS = ["Jun 2024", "Sep 2024", "Dec 2024", "Mar 2025", "Jun 2025", "Sep 2025", "Dec 2025", "Mar 2026", "Jun 2026", "Sep 2026"]
Q_SALES = [980, 1000, 1050, 1120, 1100, 1180, 1240, 1320, 1290, 1390]
Q_OP = [118, 120, 128, 140, 132, 145, 155, 168, 160, 176]
Q_PBT = [88, 90, 96, 108, 99, 111, 120, 131, 124, 138]
Q_PAT = [65, 67, 72, 81, 74, 83, 90, 98, 93, 103]

YEARS = ["Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024", "Mar 2025", "Mar 2026", "TTM"]
SALES = [2500, 2900, 3400, 3900, 4270, 5030, 5240]
OP = [350, 390, 430, 470, 520, 600, 659]
OI = [20, 22, 25, 30, 30, 35, 36]
INT = [30, 32, 35, 40, 42, 45, 46]
DEP = [60, 70, 80, 90, 100, 110, 112]
PBT = [280, 310, 340, 370, 408, 480, 537]
PAT = [210, 232, 255, 277, 306, 360, 403]

BS_YEARS = ["Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024", "Mar 2025", "Mar 2026", "Sep 2026"]
EQ = [50] * 7
RES = [900, 1100, 1320, 1560, 1830, 2140, 2250]
BOR = [300, 320, 400, 520, 640, 760, 800]
FA = [800, 880, 980, 1100, 1240, 1400, 1450]
CWIP = [40, 60, 50, 80, 70, 90, 100]
CFO = [240, 150, 180, 190, 170, 240]
CFI = [-150, -170, -190, -230, -250, -290]
WCD = [60, 66, 72, 80, 88, 92]


def _table(sid, periods, rows):
    head = "".join(f"<th>{p}</th>" for p in periods)
    body = ""
    for label, vals in rows.items():
        cells = "".join(f"<td>{v:,}</td>" if isinstance(v, (int, float)) else f"<td>{v}</td>" for v in vals)
        body += f'<tr><td class="text"><button class="button-plain">{label}&nbsp;<span>+</span></button></td>{cells}</tr>'
    return f'<section id="{sid}"><table class="data-table"><thead><tr><th></th>{head}</tr></thead><tbody>{body}</tbody></table></section>'


def page() -> str:
    opm = [f"{round(o / s * 100)}%" for o, s in zip(OP, SALES)]
    q = _table("quarters", QUARTERS, {"Sales": Q_SALES, "Operating Profit": Q_OP, "Profit before tax": Q_PBT, "Net Profit": Q_PAT,
                                      "Raw PDF": [""] * len(QUARTERS)})
    pl = _table("profit-loss", YEARS, {"Sales": SALES, "Operating Profit": OP, "OPM %": opm, "Other Income": OI,
                                        "Interest": INT, "Depreciation": DEP, "Profit before tax": PBT, "Net Profit": PAT})
    bs = _table("balance-sheet", BS_YEARS, {"Equity Capital": EQ, "Reserves": RES, "Borrowings": BOR, "Fixed Assets": FA, "CWIP": CWIP})
    cf = _table("cash-flow", YEARS[:-1], {"Cash from Operating Activity": CFO, "Cash from Investing Activity": CFI})
    ra = _table("ratios", YEARS[:-1], {"Working Capital Days": WCD, "ROCE %": ["18%", "19%", "18%", "17%", "17%", "18%"]})
    return f"""<html><body><h1 class="h2">Meridian Appliances Ltd</h1>
<div class="company-profile"><div class="about"><p>Makes kitchen appliances.</p></div></div>
<ul id="top-ratios"><li><span class="name">Market Cap</span><span class="value">₹ <span class="number">12,400</span> Cr.</span></li>
<li><span class="name">Stock P/E</span><span class="value"><span class="number">30.8</span></span></li></ul>
{q}{pl}{bs}{cf}{ra}
<section id="documents"><div class="documents annual-reports"><ul><li><a href="https://example.com/ar2026.pdf">Financial Year 2026 <div>from bse</div></a></li></ul></div>
<div class="documents concalls"><ul>
<li><div>Oct 2026</div><a class="concall-link" href="https://example.com/t1.pdf">Transcript</a><a class="concall-link" href="https://example.com/p1.pdf">PPT</a></li>
<li><div>Jul 2026</div><a class="concall-link" href="https://example.com/t2.pdf">Transcript</a></li>
</ul></div></section></body></html>"""
