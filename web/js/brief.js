// Brief: the push side. One sentence on top, the few things that need the
// investor as cards they can clear, everything else folded underneath.

import { CATEGORY_NAMES, effectiveTier, getRules, priceAlerts } from "./rules.js";
import { esc, num, pct, store, toast, tone, when } from "./ui.js";

const day = (iso) => new Date(iso).toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });

const glanceText = (f) => {
  const ps = f.people?.people || [];
  if (ps.length) return ps.map((p) => `${p.name}${p.role ? `, ${p.role}` : ""}: ${p.change}`).join("; ");
  return f.summary || f.subject;
};

const WINDOWS = [["24h", 24], ["3 days", 72], ["7 days", 168]];

const WEIGHT = { results: 50, management_change: 46, "M&A": 45, fund_raise: 42, pledging: 42, litigation: 38,
  bonus_split: 34, credit_rating: 32, dividend: 24, capex: 24, press_release: 22, earnings_call: 18 };

const initials = (name) => name.replace(/^(mr|ms|mrs|dr|shri|smt)\.?\s+/i, "").split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();

function resultsBody(f) {
  const r = f.results;
  if (!r || r.pending) return `<p>${esc(r?.source || "Numbers not extracted yet — open the filing.")}</p>`;
  const rows = r.rows.map((x) => `<tr><td>${x.name}</td><td class="v">${x.value == null ? "—" : num(x.value)}</td>
      <td class="${tone(x.qoq)}">${pct(x.qoq)}</td><td class="${tone(x.yoy)}">${pct(x.yoy)}</td></tr>`).join("");
  const q = r.quarters?.[0] ? ` · ${esc(r.quarters[0])}` : "";
  return `<table class="nums"><thead><tr><th>${esc(r.unit || "₹ cr")}${q}</th><th>Quarter</th><th>QoQ</th><th>YoY</th></tr></thead><tbody>${rows}</tbody></table>
    <div class="fine">${r.ebitda_margin != null ? `EBITDA margin ${r.ebitda_margin}%. ` : ""}${esc(r.ebitda_note || "")}
    From ${esc(r.source)}${r.basis ? `, ${esc(r.basis)}` : ""}${r.cross_checked ? ", matches the reported tables" : ""}. ${esc(r.note || "")}</div>`;
}

function headlineForResults(f) {
  const rev = f.results?.rows?.[0], pat = f.results?.rows?.[3];
  if (!rev || rev.yoy == null) return "Quarterly results are out";
  const word = (v) => (v >= 0 ? "up" : "down");
  return `Revenue ${word(rev.yoy)} ${Math.abs(rev.yoy).toFixed(0)}% on the year${pat?.yoy != null ? `, profit ${word(pat.yoy)} ${Math.abs(pat.yoy).toFixed(0)}%` : ""}`;
}

function peopleBody(f) {
  const ps = f.people?.people || [];
  if (!ps.length) return `<p>${esc(f.summary || f.detail)}</p>`;
  const order = { ceased: 0, resigned: 0, retired: 0, redesignated: 1, appointed: 2 };
  return [...ps].sort((a, b) => (order[a.change] ?? 1) - (order[b.change] ?? 1)).map((p) => {
    const incoming = p.change === "appointed";
    const verb = { appointed: "joins", ceased: "leaves", resigned: "resigns", retired: "retires", redesignated: "moves" }[p.change] || "changes";
    return `<div class="person ${incoming ? "in" : "out"}">
      <div class="avatar" aria-hidden="true">${esc(initials(p.name || "?"))}</div>
      <div><div class="who">${esc(p.name)} ${verb}</div>
        <div class="role">${esc(p.role || "")}${p.effective ? `, from ${esc(p.effective)}` : ""}${p.reason ? `. ${esc(p.reason)}` : ""}</div></div>
      ${p.background ? `<p class="bio">${esc(p.background)}</p>` : ""}
      ${p.previously?.length ? `<ul class="prev">${p.previously.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
      ${p.linkedin && incoming ? `<div class="links"><a href="${esc(p.linkedin)}" target="_blank" rel="noopener">Find on LinkedIn</a></div>` : ""}
    </div>`;
  }).join("");
}

function peopleTitle(f) {
  const ps = f.people?.people || [];
  const role = ps[0]?.role?.replace(/^(the )?/i, "") || "Top management";
  const abbr = { "chief financial officer": "CFO", "chief executive officer": "CEO", "managing director": "MD", "chief operating officer": "COO" }[role.toLowerCase()] || role;
  return `${abbr} change`;
}

function marketLine(a) {
  if (!a) return "";
  const bits = [];
  if (a.change != null) bits.push(`<span class="${tone(a.change)}">${pct(a.change)}</span> on the day`);
  if (a.volMult != null) bits.push(`${a.volMult.toFixed(1)}× usual volume`);
  return `<div class="market-says">Market reaction: ${bits.join(", ")}</div>`;
}

function card(item, anchor) {
  const f = item.filing, a = item.alert;
  const sym = item.symbol;
  let kind, title, body = "";
  if (!f) {
    kind = "Unusual move";
    const parts = [];
    if (a.hits.includes("volume")) parts.push(`Volume ${a.volMult.toFixed(1)}× normal`);
    if (a.hits.includes("move")) parts.push(`${a.change > 0 ? "up" : "down"} ${Math.abs(a.change).toFixed(1)}%`);
    const c = item.context;
    const what = c ? (c.category === "results" ? "results" : (c.label || "a filing").toLowerCase()) : "";
    title = c ? `${parts.join(", ")} after ${what} on ${day(c.time)}` : `${parts.join(", ")}, with no filing to explain it`;
    title = title[0].toUpperCase() + title.slice(1);
    body = c
      ? `<p>Closed at ₹${num(a.close, 1)} on ${esc(day(a.date))}.${c.summary ? ` ${esc(c.summary)}` : ""}</p>`
      : `<p>Closed at ₹${num(a.close, 1)} on ${esc(day(a.date))}. Moves without news are often worth a call.</p>`;
    if (c) kind = "Market reaction";
  } else if (f.category === "results") {
    kind = "Results";
    title = headlineForResults(f);
    body = resultsBody(f);
  } else if (f.category === "management_change") {
    kind = "Management";
    title = peopleTitle(f);
    body = peopleBody(f);
  } else {
    kind = f.label || CATEGORY_NAMES[f.category] || "Filing";
    title = f.summary || f.subject;
  }
  const focus = f?.category === "results" ? "promises" : "";
  return `<li class="item" data-id="${esc(item.id)}">
    <div class="item-top"><a class="sym" href="#/ask/${esc(sym)}">${esc(sym)}</a><span class="kind">${esc(kind)}</span>
      <span class="when">${esc(f ? when(f.time, anchor) : day(a.date))}</span></div>
    <h3>${esc(title)}</h3>
    ${body}
    ${f && a ? marketLine(a) : ""}
    <div class="actions">
      <a class="btn primary" href="#/ask/${esc(sym)}${focus ? `/${focus}` : ""}">${f?.category === "results" ? "Check against guidance" : "Research"}</a>
      ${(f || item.context)?.url ? `<a class="btn" href="${esc((f || item.context).url)}" target="_blank" rel="noopener">Filing</a>` : ""}
      <span class="spacer"></span>
      <button class="btn quiet" data-clear="${esc(item.id)}" type="button">Done</button>
    </div>
  </li>`;
}

function score(item) {
  const f = item.filing;
  let s = f ? WEIGHT[f.category] ?? 20 : 36 + Math.min(10, Math.abs(item.alert.change || 0));
  if (f && item.alert) s += 25;          // the market reacted too
  return s;
}

export function renderBrief(root, snap) {
  const rules = getRules(snap.defaults);
  const anchor = new Date(snap.generated_at);
  let hours = store.get("window", 24);
  const cleared = new Set(store.get("cleared", []));

  const draw = () => {
    const since = anchor.getTime() - hours * 3600e3;
    const inWindow = snap.filings.filter((f) => f.time && new Date(f.time).getTime() >= since)
      .map((f) => ({ ...f, tier: effectiveTier(f, rules) }));
    // Companies often file the same results more than once: keep one card each.
    const best = {};
    for (const f of inWindow) if (f.category === "results" && f.tier === 3) {
      const b = best[f.symbol];
      if (!b || (!b.results?.rows && f.results?.rows)) best[f.symbol] = f;
    }
    for (const f of inWindow) if (f.category === "results" && f.tier === 3 && best[f.symbol] !== f) f.tier = 2;
    const alerts = priceAlerts(snap.holdings, rules);
    const alertBy = Object.fromEntries(alerts.map((a) => [a.symbol, a]));

    const heads = inWindow.filter((f) => f.tier === 3).map((f) => ({ id: f.id, symbol: f.symbol, filing: f, alert: alertBy[f.symbol] }));
    const explained = new Set(heads.map((h) => h.symbol));
    const recentFiling = (sym) => snap.filings.find((f) => f.symbol === sym && f.tier >= 2 && f.time
      && anchor.getTime() - new Date(f.time).getTime() < 4 * 24 * 3600e3);
    for (const a of alerts) if (!explained.has(a.symbol)) {
      heads.push({ id: `alert-${a.symbol}-${a.date}`, symbol: a.symbol, alert: a, context: recentFiling(a.symbol) });
    }
    heads.sort((x, y) => score(y) - score(x) || (y.filing?.time || "").localeCompare(x.filing?.time || ""));

    const open = heads.filter((h) => !cleared.has(h.id));
    const glance = inWindow.filter((f) => f.tier === 2);
    const routine = inWindow.filter((f) => f.tier === 1);
    const others = inWindow.length - heads.filter((h) => h.filing).length;
    const n = open.length;

    const sentence = n
      ? `<span class="count">${n} ${n === 1 ? "thing needs" : "things need"} you.</span><span class="rest">${others} other filing${others === 1 ? "" : "s"} didn't.</span>`
      : heads.length
        ? `<span class="count">You're caught up.</span><span class="rest">${inWindow.length} filings, ${heads.length} cleared.</span>`
        : `<span class="count">Nothing needs you.</span><span class="rest">${inWindow.length ? `All ${inWindow.length} filings were routine.` : "No filings in this window."}</span>`;

    const ticks = [...inWindow].reverse().slice(-140).map((f) => {
      const id = heads.find((h) => h.filing?.id === f.id)?.id;
      return `<i class="t${f.tier}${id && cleared.has(id) ? " cleared" : ""}"></i>`;
    }).join("");

    const routineHint = [...new Set(routine.map((f) => f.label))].slice(0, 3).join(", ").toLowerCase();

    root.innerHTML = `
      <section class="brief-head">
        <div class="controls">
          <div class="segmented" role="group" aria-label="Time window">
            ${WINDOWS.map(([l, h]) => `<button type="button" data-hours="${h}" aria-pressed="${h === hours}">${l}</button>`).join("")}
          </div>
        </div>
        <h1 class="headline${n ? "" : " done"}">${sentence}</h1>
        <div class="ticks" aria-hidden="true">${ticks}</div>
        <div class="ticks-legend"><span><b>${heads.filter((h) => h.filing).length}</b> need you</span><span><b>${glance.length}</b> worth a glance</span><span><b>${routine.length}</b> routine</span></div>
      </section>

      <ol class="stack" aria-label="Needs your attention">${open.map((h) => card(h, anchor)).join("")}</ol>
      ${!n && heads.length ? `<div class="caught-up"><strong>That's everything.</strong>The next brief builds after market close.</div>` : ""}
      ${cleared.size && heads.some((h) => cleared.has(h.id)) ? `<div class="section-pad" style="margin-top:12px"><button class="btn quiet" id="restore" type="button">Show ${heads.filter((h) => cleared.has(h.id)).length} cleared</button></div>` : ""}

      ${glance.length ? `<details class="fold" open><summary>Worth a glance <span class="n">${glance.length}</span></summary>
        <ul class="rows">${glance.map((f) => `<li><a class="sym" href="#/ask/${esc(f.symbol)}">${esc(f.symbol)}</a>
          <span class="what">${f.url ? `<a href="${esc(f.url)}" target="_blank" rel="noopener">${esc(glanceText(f))}</a>` : esc(glanceText(f))}</span>
          <span class="sub">${esc(f.label)}, ${esc(when(f.time, anchor))}</span></li>`).join("")}</ul></details>` : ""}

      ${routine.length ? `<details class="fold"><summary>Routine <span class="n">${routine.length}</span><span class="hint">${esc(routineHint)}</span></summary>
        <ul class="rows routine">${routine.map((f) => `<li><span class="sym">${esc(f.symbol)}</span><span>${f.url ? `<a href="${esc(f.url)}" target="_blank" rel="noopener">${esc(f.label)}</a>` : esc(f.label)}</span>
          <span>${esc(when(f.time, anchor))}</span></li>`).join("")}</ul></details>` : ""}
    `;

    root.querySelectorAll("[data-hours]").forEach((b) => b.addEventListener("click", () => {
      hours = +b.dataset.hours; store.set("window", hours); draw();
    }));
    root.querySelectorAll("[data-clear]").forEach((b) => b.addEventListener("click", () => clear(b.dataset.clear)));
    root.querySelector("#restore")?.addEventListener("click", () => {
      heads.forEach((h) => cleared.delete(h.id)); store.set("cleared", [...cleared]); draw();
    });
    root.querySelectorAll(".item").forEach(enableSwipe);
  };

  const clear = (id) => {
    const el = root.querySelector(`.item[data-id="${CSS.escape(id)}"]`);
    cleared.add(id); store.set("cleared", [...cleared]);
    const finish = () => draw();
    if (el) { el.classList.add("leaving"); setTimeout(finish, 180); } else finish();
    toast("Cleared", { label: "Undo", run: () => { cleared.delete(id); store.set("cleared", [...cleared]); draw(); } });
  };

  // Swipe left to clear — the same as pressing Done.
  function enableSwipe(el) {
    let x0 = null, dx = 0;
    el.addEventListener("pointerdown", (e) => { if (e.target.closest("a,button")) return; x0 = e.clientX; dx = 0; el.classList.add("swiping"); });
    el.addEventListener("pointermove", (e) => {
      if (x0 === null) return;
      dx = Math.min(0, e.clientX - x0);
      el.style.transform = `translateX(${dx}px)`;
    });
    const end = () => {
      if (x0 === null) return;
      el.classList.remove("swiping"); x0 = null;
      if (dx < -90) clear(el.dataset.id); else el.style.transform = "";
    };
    el.addEventListener("pointerup", end);
    el.addEventListener("pointercancel", end);
    el.addEventListener("pointerleave", end);
  }

  draw();
}
