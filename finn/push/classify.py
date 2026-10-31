"""Sort exchange filings into the reference taxonomy, and decide how loud each one is.

Two separate questions, deliberately:
  category — what kind of filing it is (the reference document's list).
  tier     — how much of the investor's attention it earns:
               3  headline: show it first, enriched
               2  glance:   one line, collapsed under the headlines
               1  routine:  hidden behind a count

Rules, not a model. NSE tags every filing with a subject line and a short text,
and those are consistent enough that ~40 ordered regexes classify almost
everything correctly, instantly, for free, and the same way every time. The model
budget goes to reading the handful of filings that are worth reading.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

TOP_ROLE = r"\b(ceo|chief executive|cfo|chief financial|managing director|md|whole[- ]?time director|executive director|chairman|chairperson|president|coo|chief operating)\b"


@dataclass(frozen=True)
class Rule:
    category: str
    tier: int
    label: str
    pattern: str
    unless: str | None = None


# Order matters: first match wins. Noise is caught first so that, say, a
# newspaper ad *about* results doesn't get treated like the results themselves.
RULES: list[Rule] = [
    # ---- routine paperwork -------------------------------------------------------
    Rule("unclassified", 1, "Trading window", r"trading window"),
    Rule("results", 1, "Results ad", r"(newspaper (publication|advertisement)|copy of newspaper).{0,300}result"),
    Rule("unclassified", 1, "Newspaper ad", r"newspaper (publication|advertisement)|copy of newspaper"),
    Rule("unclassified", 1, "Compliance certificate",
         r"certificate under|regulation 74|reg\.? ?74|compliance certificate|loss of share cert|duplicate share|"
         r"issue of duplicate|transmission of shares|share certificate"),
    Rule("unclassified", 1, "ESOP allotment", r"\besop|\besos|\besps|employee stock|stock option"),
    Rule("unclassified", 1, "ESG report", r"\bbrsr\b|business responsibility|sustainability report|\besg\b"),
    Rule("unclassified", 1, "Fund-use report", r"monitoring agency|statement of deviation"),
    Rule("unclassified", 1, "Auditor change", r"\b(statutory|secretarial|internal|cost) auditor"),
    Rule("press_release", 2, "Price/volume clarification", r"spurt in volume|clarification.{0,40}(price|volume|news|rumou?r)|movement in price"),

    # ---- results -------------------------------------------------------------------
    Rule("results", 1, "Results date", r"board meeting intimation.{0,200}(result|financial)|intimation.{0,80}board meeting.{0,120}result"),
    Rule("results", 3, "Results", r"integrated filing.{0,10}financ|financial results?\b|results? for the (quarter|half|year)|(un)?audited (standalone|consolidated)?.{0,30}results",
         unless=r"intimation|newspaper"),
    Rule("results", 2, "Results deck", r"investor presentation|earnings presentation|shareholders?'? letter|press release.{0,60}results"),

    # ---- earnings call / investor meetings ---------------------------------------------
    Rule("earnings_call", 2, "Concall transcript", r"transcript"),
    Rule("earnings_call", 1, "Concall recording", r"(audio|video).{0,20}recording|recording of.{0,40}call"),
    Rule("earnings_call", 1, "Concall notice", r"(earnings|conference|con\.?) ?call.{0,80}(schedul|intimat|invit)|"
                                               r"(schedul|intimat|invit).{0,80}(earnings|conference) call"),
    Rule("investor_meetings", 1, "Investor meetings", r"analysts?/institutional investor meet|investor meet|analyst meet|"
                                                    r"investor conference|one[- ]on[- ]one|group meeting"),

    # ---- ownership ---------------------------------------------------------------------
    Rule("pledging", 3, "Promoter pledge", r"pledge|encumbranc|encumbered"),
    Rule("insider_trading", 2, "Insider deal", r"\bsast\b|takeover regulations|regulation 29|regulation 31|"
                                              r"insider trading|\bpit\b|regulation 7 ?\(2\)"),

    # ---- people ------------------------------------------------------------------------
    Rule("management_change", 3, "Top management", r"(change in director|key managerial|appoint|resign|cessation|retire|re-?designat|step(s|ping)? down)"
                                                 r".{0,300}" + TOP_ROLE),
    Rule("management_change", 3, "Top management", TOP_ROLE + r".{0,120}(appoint|resign|cessation|retire|step(s|ping)? down)"),
    Rule("management_change", 1, "Company secretary", r"company secretary|compliance officer|share transfer agent"),
    Rule("management_change", 2, "Board change", r"change in director|key managerial|appointment of|resignation|cessation|retire"),

    # ---- corporate actions ------------------------------------------------------------------
    Rule("bonus_split", 3, "Bonus/split", r"\bbonus\b|stock split|sub-?division|split of (equity )?shares"),
    Rule("dividend", 2, "Dividend", r"dividend"),
    Rule("fund_raise", 3, "Buyback", r"buy-?back"),
    Rule("fund_raise", 3, "Equity raise", r"rights issue|\bqip\b|qualified institution|preferential (issue|allotment)|fund ?rais|raising of funds"),
    Rule("fund_raise", 1, "Debt issue", r"commercial paper|\bncds?\b|non-?convertible|debenture"),
    Rule("unclassified", 1, "Allotment", r"allotment of (securities|equity shares)"),

    Rule("credit_rating", 3, "Rating cut", r"rating.{0,200}(downgrad|negative|watch|withdrawn)"),
    Rule("credit_rating", 2, "Rating upgrade", r"rating.{0,200}upgrad"),
    Rule("credit_rating", 1, "Rating affirmed", r"credit rating|rating"),

    # ---- deals, spend, disputes -----------------------------------------------------------------
    Rule("M&A", 2, "New subsidiary", r"incorporation of.{0,40}subsidiar"),
    Rule("M&A", 3, "Deal", r"acqui|amalgamat|merger|demerger|scheme of arrangement|joint venture|\bjv\b|"
                          r"divest|disinvest|stake sale|sale of (the |its |entire |our )*(stake|shares|business|undertaking)|slump sale|"
                          r"business transfer agreement|share purchase agreement"),
    Rule("capex", 2, "Capex", r"capacity expansion|new (plant|facility)|\bcapex\b|capital expenditure|greenfield|brownfield|"
                             r"commissioning|commenced commercial production|manufacturing facility"),
    Rule("litigation", 2, "Inspection cleared", r"establishment inspection report|\beir\b|voluntary action indicated|\bnai\b|\bvai\b"),
    Rule("litigation", 3, "Regulatory action", r"warning letter|import alert|insolvency|\bnclt\b|\bcirp\b|search and seizure|"
                                              r"penalty|show cause|forensic|fraud|default"),
    Rule("litigation", 2, "Dispute/order", r"litigation|order passed|demand (notice|order)|tax demand|\bgst\b|dispute|"
                                          r"action\(?s\)? initiated|\busfda\b|form 483|observations|inspection"),

    # ---- meetings -------------------------------------------------------------------------------
    Rule("postal_ballot", 1, "Postal ballot", r"postal ballot"),
    Rule("agm_egm", 1, "AGM/EGM", r"annual general meeting|\bagm\b|\begm\b|extra-?ordinary general|shareholders'? meeting|"
                                 r"voting results|scrutini[sz]er|book closure|record date"),

    # ---- everything else that is still news -------------------------------------------------------
    Rule("press_release", 2, "Business update", r"\border(s)?\b.{0,40}(win|receiv|bag|secur|worth|valued)|contract|bagged|launch|"
                                               r"partnership|tie-?up|collaborat|agreement|\bmou\b|business update|operational update"),
    Rule("press_release", 2, "Press release", r"press release|media release"),
    Rule("press_release", 1, "General update", r"general update|\bupdates?\b"),
]

_COMPILED = [(r, re.compile(r.pattern, re.I | re.S), re.compile(r.unless, re.I | re.S) if r.unless else None) for r in RULES]


# NSE's catch-all subject lines name every possibility ("...Auditor/ Compliance
# Officer/ Share Transfer Agent"), which would trip the role patterns. Shorten them
# so the detail text decides.
SUBJECT_ALIASES = [
    (re.compile(r"^change in directors.*", re.I), "Change in directors"),
    (re.compile(r"^analysts/institutional investor meet.*", re.I), "Investor meet/call update"),
]


def classify(subject: str, detail: str = "") -> dict:
    for rx, alias in SUBJECT_ALIASES:
        subject = rx.sub(alias, subject or "")
    text = f"{subject} | {detail}"
    for rule, rx, unless in _COMPILED:
        if rx.search(text) and not (unless and unless.search(text)):
            return {"category": rule.category, "tier": rule.tier, "label": rule.label}
    return {"category": "unclassified", "tier": 1, "label": "Other"}


_BOILERPLATE = re.compile(
    r"^.{0,120}?\b(has|have)\s+(informed|submitted|intimated)\s+(to\s+)?the\s+exchange\s+"
    r"(about|regarding|that|of|with respect to|copy of|a copy of)?\s*", re.I)


def tidy_detail(detail: str, limit: int = 180) -> str:
    """NSE's free-text field minus its 'X Limited has informed the Exchange regarding' preamble."""
    d = _BOILERPLATE.sub("", detail or "").strip()
    d = re.sub(r"^(that\s+)?(it|the company)\s+has\s+", "", d, flags=re.I)
    d = d[:1].upper() + d[1:] if d else d
    if len(d) > limit:
        cut = d[:limit].rsplit(" ", 1)[0]
        d = cut.rstrip(",;:") + "…"
    return d
