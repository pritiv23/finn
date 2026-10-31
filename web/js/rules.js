// The investor's rules, and everything derived from them. Same logic as
// finn/push/alerts.py, run on the device so a threshold change shows up instantly.

import { store } from "./ui.js";

export const CATEGORY_NAMES = {
  results: "Results", "M&A": "M&A", management_change: "Management", fund_raise: "Fund raise",
  litigation: "Legal & regulatory", credit_rating: "Credit rating", pledging: "Pledging", dividend: "Dividend",
  bonus_split: "Bonus/split", capex: "Capex", press_release: "Business news", insider_trading: "Insider deals",
  earnings_call: "Earnings call",
};

export function getRules(defaults = {}) {
  return {
    volume_multiple: defaults.volume_multiple ?? 2,
    volume_lookback_days: defaults.volume_lookback_days ?? 20,
    price_move_pct: defaults.price_move_pct ?? 4,
    always_surface: defaults.always_surface ?? Object.keys(CATEGORY_NAMES).slice(0, 7),
    ...store.get("rules", {}),
  };
}

export const saveRules = (r) => store.set("rules", r);

export function dayStats(eod, lookback) {
  if (!eod || eod.length < 2) return null;
  const [date, close, vol] = eod[eod.length - 1];
  const prev = eod[eod.length - 2][1];
  const win = eod.slice(-lookback - 1, -1).map((r) => r[2]).filter(Boolean);
  const avg = win.length ? win.reduce((a, b) => a + b, 0) / win.length : null;
  return { date, close, change: prev ? ((close - prev) / prev) * 100 : null, volume: vol, volMult: avg ? vol / avg : null };
}

export function priceAlerts(holdings, rules) {
  const out = [];
  for (const h of holdings) {
    const s = dayStats(h.eod, rules.volume_lookback_days);
    if (!s) continue;
    const hits = [];
    if (s.volMult != null && s.volMult >= rules.volume_multiple) hits.push("volume");
    if (s.change != null && Math.abs(s.change) >= rules.price_move_pct) hits.push("move");
    if (hits.length) out.push({ symbol: h.symbol, name: h.name, hits, ...s });
  }
  return out;
}

// Categories the classifier never puts at the top on its own. If the investor
// switches one on, its non-routine filings become headlines.
const GLANCE_ONLY = new Set(["dividend", "capex", "press_release", "insider_trading", "earnings_call"]);

// A filing's tier under the investor's rules. The classifier decides what's
// routine; the investor decides which material categories deserve the top.
export function effectiveTier(f, rules) {
  const on = rules.always_surface.includes(f.category);
  if (f.tier === 3 && !on) return 2;
  if (f.tier === 2 && on && GLANCE_ONLY.has(f.category)) return 3;
  return f.tier;
}
