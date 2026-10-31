// Watch: the investor's rules, written as sentences they can change, and the
// portfolio sorted by how unusual today was.

import { CATEGORY_NAMES, dayStats, getRules, priceAlerts, saveRules } from "./rules.js";
import { esc, num, pct, sparkline, tone } from "./ui.js";

const stepper = (key, value, step, unit = "") =>
  `<span class="stepper"><button type="button" data-step="${key}" data-d="-${step}" aria-label="Decrease">−</button><output>${value}${unit}</output><button type="button" data-step="${key}" data-d="${step}" aria-label="Increase">+</button></span>`;

const LIMITS = { volume_multiple: [1.2, 6], volume_lookback_days: [5, 60], price_move_pct: [1, 15] };

export function renderWatch(root, snap) {
  const draw = () => {
    const r = getRules(snap.defaults);
    const alerts = priceAlerts(snap.holdings, r);
    const hot = new Set(alerts.map((a) => a.symbol));
    const rows = snap.holdings.map((h) => ({ h, s: dayStats(h.eod, r.volume_lookback_days) }))
      .sort((a, b) => (hot.has(b.h.symbol) - hot.has(a.h.symbol)) || ((b.s?.volMult || 0) - (a.s?.volMult || 0)));

    root.innerHTML = `
      <section class="ask-head"><h1>What counts as unusual</h1></section>
      <ul class="rules">
        <li class="rule">Tell me when volume is above ${stepper("volume_multiple", r.volume_multiple.toFixed(1), 0.5, "×")} its ${stepper("volume_lookback_days", r.volume_lookback_days, 5)}-day average.</li>
        <li class="rule">Tell me when a stock closes more than ${stepper("price_move_pct", r.price_move_pct, 0.5, "%")} up or down.
          <span class="muted">${alerts.length ? `${alerts.length} of your ${snap.holdings.length} holdings trip these rules today.` : "Nothing in your portfolio trips these rules today."}</span></li>
        <li class="rule">Put these at the top when they're material:
          <div class="toggles">${Object.entries(CATEGORY_NAMES).map(([k, l]) => `<button type="button" data-cat="${esc(k)}" aria-pressed="${r.always_surface.includes(k)}">${esc(l)}</button>`).join("")}</div>
          <span class="muted">Everything else stays one tap away under "Worth a glance".</span></li>
      </ul>
      <h2 class="sub-h">Portfolio <span>last session${rows[0]?.s ? `, ${esc(new Date(rows[0].s.date).toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" }))}` : ""}</span></h2>
      <ul class="holdings">${rows.map(({ h, s }) => `<li class="${hot.has(h.symbol) ? "hot" : ""}">
          <div><a class="sym" href="#/ask/${esc(h.symbol)}">${esc(h.symbol)}</a><div class="nm">${esc(h.name)}, ${esc(h.sector)}</div></div>
          ${sparkline(h.eod.slice(-60).map((x) => x[1]), { highlight: hot.has(h.symbol) })}
          <div class="px">${s ? `<span class="${tone(s.change)}">${pct(s.change)}</span><small>${s.volMult != null ? `${num(s.volMult, 1)}× vol` : ""}</small>` : "—"}</div>
        </li>`).join("")}</ul>`;

    root.querySelectorAll("[data-step]").forEach((b) => b.addEventListener("click", () => {
      const k = b.dataset.step, [lo, hi] = LIMITS[k];
      const next = Math.min(hi, Math.max(lo, Math.round((r[k] + parseFloat(b.dataset.d)) * 10) / 10));
      saveRules({ ...r, [k]: next }); draw();
    }));
    root.querySelectorAll("[data-cat]").forEach((b) => b.addEventListener("click", () => {
      const k = b.dataset.cat;
      const set = new Set(r.always_surface);
      set.has(k) ? set.delete(k) : set.add(k);
      saveRules({ ...r, always_surface: [...set] }); draw();
    }));
  };
  draw();
}
