from finn.pull import guidance, metrics
from finn.push import alerts, enrich
from finn.sources.screener import parse_company

from .fixtures import page


def _sc():
    sc = parse_company(page(), "https://www.screener.in/company/MERIDIAN/")
    sc["basis"] = "consolidated"
    return sc


def test_parser_reads_tables_and_documents():
    sc = _sc()
    assert sc["name"] == "Meridian Appliances Ltd"
    assert sc["top_ratios"]["Market Cap"] == 12400
    assert sc["tables"]["quarters"]["rows"]["Sales"][-1] == 1390
    assert "Raw PDF" not in sc["tables"]["quarters"]["rows"]
    assert sc["tables"]["profit-loss"]["periods"][-1] == "TTM"
    assert sc["concalls"][0] == {"period": "Oct 2026", "transcript": "https://example.com/t1.pdf",
                                 "ppt": "https://example.com/p1.pdf", "recording": None}
    assert sc["annual_reports"][0]["year"] == 2026


def test_metrics_are_computed_not_guessed():
    m = metrics.compute(_sc())
    assert m["annual"]["years"][-1] == "Mar 2026"           # TTM excluded from annual series
    assert m["snapshot"]["ttm_revenue"] == 5240
    assert m["trajectory"]["revenue_cagr_3y"] == round(((5030 / 3400) ** (1 / 3) - 1) * 100, 1)
    # capex estimate = change in (fixed assets + CWIP) + depreciation
    assert m["annual"]["capex_est"][-1] == (1400 + 90) - (1240 + 70) + 110
    # 5y conversion: sum CFO / sum PAT over the last five years
    assert m["cash"]["conversion_5y_pct"] == round(sum([150, 180, 190, 170, 240]) / sum([232, 255, 277, 306, 360]) * 100)
    texts = " ".join(f["text"] for f in m["flags"])
    assert "operating cash" in texts                         # conversion < 70% gets flagged
    assert "Working-capital cycle stretched" in texts        # 66 -> 92 days


def test_promise_checked_against_later_quarters():
    m = metrics.compute(_sc())
    # Said in Jul 2026 (Q1 FY27 call): "revenue growth of 15-18% in FY27".
    item = {"metric": "revenue_growth", "target_low": 15, "target_high": 18, "unit": "%", "horizon": "FY27", "call": "Jul 2026"}
    got = guidance.check(item, m)
    # FY27 so far = Jun 2026 + Sep 2026 vs Jun 2025 + Sep 2025
    expected = round(((1290 + 1390) - (1100 + 1180)) / (1100 + 1180) * 100, 1)
    assert got["actual"] == expected
    assert got["basis"] == "FY27 first 2 quarters"
    assert got["verdict"] == "on_track"


def test_margin_promise_missed_for_completed_year():
    m = metrics.compute(_sc())
    item = {"metric": "ebitda_margin", "target_low": 14, "target_high": None, "unit": "%", "horizon": "FY26", "call": "Jul 2025"}
    got = guidance.check(item, m)
    assert got["basis"] == "FY26 full year"
    assert got["verdict"] == "missed"          # (145+155+168+132)/(1100+1180+1240+1320)? -> ~12.4%


def test_unmeasurable_promise_stays_unmeasurable():
    item = {"metric": "capacity", "target_low": None, "target_high": None, "horizon": "FY27", "call": "Jul 2026"}
    assert guidance.check(item, metrics.compute(_sc()))["verdict"] == "unmeasurable"


def test_results_card_fallback_from_tables():
    card = enrich._from_screener(_sc())
    rev = card["rows"][0]
    assert rev["name"] == "Revenue" and rev["value"] == 1390
    assert rev["qoq"] == round((1390 - 1290) / 1290 * 100, 1)
    assert rev["yoy"] == round((1390 - 1180) / 1180 * 100, 1)


def test_people_regex_fallback():
    p = enrich._people_from_text("Cessation of Mr. Rakesh Kumar as Chief Financial Officer w.e.f. October 31, 2026")
    assert p[0]["name"] == "Mr. Rakesh Kumar" and p[0]["change"] == "ceased" and p[0]["role"] == "Chief Financial Officer"


def test_volume_and_move_alerts():
    series = [[f"d{i}", 100, 1000] for i in range(25)] + [["d25", 106, 3100]]
    got = alerts.evaluate("X", series, volume_multiple=2, lookback=20, move_pct=4)
    kinds = {a["kind"]: a["value"] for a in got}
    assert kinds == {"volume": 3.1, "move": 6.0}
