import pytest

from finn.push.classify import classify, tidy_detail

CASES = [
    # (subject, detail, category, tier)
    ("Outcome of Board Meeting", "approved the Unaudited Financial Results for the quarter ended September 30, 2026", "results", 3),
    ("Integrated Filing (Financial)", "Integrated filing for the quarter ended 30-Sep-2026", "results", 3),
    ("Board Meeting Intimation", "to consider and approve the financial results for the quarter ended Sep 2026", "results", 1),
    ("Copy of Newspaper Publication", "newspaper advertisement of the financial results", "results", 1),
    ("Copy of Newspaper Publication", "notice of loss of share certificates", "unclassified", 1),
    ("Change in Directors/ Key Managerial Personnel/ Auditor/ Compliance Officer/ Share Transfer Agent",
     "Cessation of Mr. Rakesh Kumar as Chief Financial Officer w.e.f. October 31, 2026", "management_change", 3),
    ("Change in Directors/ Key Managerial Personnel/ Auditor/ Compliance Officer/ Share Transfer Agent",
     "Appointment of Ms. Anita Rao as Independent Director", "management_change", 2),
    ("Change in Directors/ Key Managerial Personnel/ Auditor/ Compliance Officer/ Share Transfer Agent",
     "Appointment of M/s ABC & Co. as Secretarial Auditor", "unclassified", 1),
    ("Analysts/Institutional Investor Meet/Con. Call Updates", "Transcript of the earnings call held on Oct 21, 2026", "earnings_call", 2),
    ("Analysts/Institutional Investor Meet/Con. Call Updates", "Schedule of meet with Morgan Stanley Investment Management", "investor_meetings", 1),
    ("Credit Rating", "CRISIL has reaffirmed the rating at CRISIL AAA/Stable", "credit_rating", 1),
    ("Credit Rating", "ICRA has downgraded the long-term rating to [ICRA]AA-", "credit_rating", 3),
    ("Acquisition", "acquisition of 51% stake in XYZ Electronics Pvt Ltd for Rs 320 crore", "M&A", 3),
    ("Updates", "Incorporation of a wholly owned subsidiary in Singapore", "M&A", 2),
    ("Trading Window", "closure of trading window from Oct 1, 2026", "unclassified", 1),
    ("Allotment of Securities", "allotment of 12,400 equity shares under ESOP Scheme 2019", "unclassified", 1),
    ("Disclosure under SEBI Takeover Regulations", "creation of pledge on shares by promoter", "pledging", 3),
    ("Press Release", "has bagged an order worth Rs 1,200 crore from NHAI", "press_release", 2),
    ("Record Date", "record date for the purpose of interim dividend of Rs 11 per share", "dividend", 2),
    ("Shareholders meeting", "Voting results of the 40th AGM", "agm_egm", 1),
    ("Action(s) initiated or orders passed", "Receipt of GST demand order of Rs 4.2 crore", "litigation", 2),
    ("Updates", "USFDA has issued a warning letter for the Halol facility", "litigation", 3),
    ("Bonus", "Board recommended bonus issue in the ratio 1:1", "bonus_split", 3),
]


@pytest.mark.parametrize("subject,detail,category,tier", CASES)
def test_classify(subject, detail, category, tier):
    got = classify(subject, detail)
    assert (got["category"], got["tier"]) == (category, tier), got


def test_tidy_detail_strips_preamble():
    d = "Dixon Technologies (India) Limited has informed the Exchange regarding acquisition of 51% stake in X."
    assert tidy_detail(d) == "Acquisition of 51% stake in X."
