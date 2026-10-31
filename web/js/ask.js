// Research: the pull side. Promises first, because that's the analysis
// that summarising can't fake; then the numbers that back or break the story.

import { hasApi, loadResearch, researchIndex } from "./data.js";
import { barsWithLine, crore, esc, num, pairedBars, pct, store } from "./ui.js";

const cap = (t) => (t ? t[0].toUpperCase() + t.slice(1) : t);
const KEPT = ["delivered", "beat", "on_track", "ahead"];
const BROKE = ["missed", "behind"];
const VERDICT = { delivered: "Delivered", beat: "Beat", on_track: "On track", ahead: "Ahead", missed: "Missed", behind: "Behind",
  too_early: "Too early", unmeasurable: "Can't measure" };
const METRIC = { revenue_growth: "Revenue growth", ebitda_margin: "EBITDA margin", pat_growth: "Profit growth", capex: "Capex",
  capacity: "Capacity", volume: "Volume", other: "Other" };

export async function renderAskHome(root, snap) {
  const [index, api] = await Promise.all([researchIndex(), hasApi()]);
  const recent = store.get("recent", []);
  const portfolio = snap?.holdings?.map((h) => h.symbol) || [];
  const chip = (s) => `<a class="btn" href="#/ask/${esc(s)}">${esc(s)}</a>`;
  root.innerHTML = `
    <section class="ask-head">
      <h1>Research a company</h1>
      <form class="search" id="ask-form" role="search">
        <label class="sr" for="q" hidden>NSE symbol</label>
        <input id="q" name="q" autocomplete="off" autocapitalize="characters" spellcheck="false" placeholder="NSE symbol, e.g. ASIANPAINT" enterkeyhint="go">
      </form>
      <div class="suggest">
        ${index.length ? `<div class="suggest-label">Ready to read</div>${index.map(chip).join("")}` : ""}
        ${recent.length ? `<div class="suggest-label">Recent</div>${recent.filter((s) => !index.includes(s)).slice(0, 6).map(chip).join("")}` : ""}
        ${api && portfolio.length ? `<div class="suggest-label">Your portfolio</div>${portfolio.map(chip).join("")}` : ""}
      </div>
      <p class="note">${api
        ? "Built from the company's own annual report, concall transcripts and reported financials. No news, no broker notes."
        : "This copy is running without the research server, so only the companies above are available. Run <code>python -m finn serve</code> to research any symbol."}</p>
    </section>`;
  root.querySelector("#ask-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const q = root.querySelector("#q").value.trim().toUpperCase().replace(/\.NS$/, "");
    if (q) location.hash = `#/ask/${q}`;
  });
}

const STAGES = ["Reading reported financials", "Reading concall transcripts", "Reading the annual report", "Weighing what management said against the numbers"];

export async function renderDossier(root, symbol, focus) {
  let seen = [];
  const progress = (stage) => {
    if (!seen.includes(stage)) seen.push(stage);
    const list = STAGES.map((s) => {
      const hit = seen.find((x) => x.startsWith(s.split(" ").slice(0, 2).join(" ")));
      const now = hit && hit === seen[seen.length - 1];
      return `<li class="${now ? "now" : hit ? "past" : ""}">${esc(hit || s)}</li>`;
    }).join("");
    root.innerHTML = `<section class="progress"><h1 class="headline" style="font-size:26px">${esc(symbol)}</h1>
      <p class="note">First read of a company takes about a minute. After that it's instant.</p><ol>${list}</ol></section>`;
  };
  progress("Reading reported financials");
  let d;
  try {
    d = await loadResearch(symbol, progress);
  } catch (e) {
    root.innerHTML = `<section class="ask-head"><h1>${esc(symbol)}</h1><p class="note">${esc(e.message)}
      ${e.offline ? " Pick one of the ready companies, or run the research server to read any NSE symbol." : ""}</p>
      <p><a class="btn" href="#/ask">Back to research</a></p></section>`;
    return;
  }
  store.set("recent", [symbol, ...store.get("recent", []).filter((s) => s !== symbol)].slice(0, 8));
  root.innerHTML = dossier(d);
  // Section links scroll in place rather than re-routing.
  root.querySelectorAll(".jump a, [data-jump]").forEach((a) => a.addEventListener("click", (e) => {
    e.preventDefault();
    const id = a.dataset.jump !== undefined ? a.getAttribute("href").slice(1) : a.getAttribute("href").split("/").pop();
    root.querySelector(`#${CSS.escape(id)}`)?.scrollIntoView({ behavior: "smooth" });
    history.replaceState(null, "", `#/ask/${d.symbol}/${id}`);
  }));
  if (focus) root.querySelector(`#${CSS.escape(focus)}`)?.scrollIntoView();
  else window.scrollTo(0, 0);
}

function citeFor(d) {
  const src = Object.fromEntries((d.sources || []).map((s) => [s.id, s]));
  return (id) => {
    if (!id) return "";
    return String(id).split(/[ ,]+/).filter(Boolean).map((one) => {
      if (/^G\d+$/.test(one)) return `<a class="cite" href="#g-${esc(one)}" data-jump>${esc(one)}</a>`;
      const s = src[one];
      return s?.url ? `<a class="cite" href="${esc(s.url)}" target="_blank" rel="noopener" title="${esc(s.label)}">${esc(one)}</a>`
        : `<span class="cite" title="${esc(s?.label || "")}">${esc(one)}</span>`;
    }).join("");
  };
}

function promises(d, cite) {
  const g = d.guidance || {};
  const items = [...(g.items || [])];
  if (!items.length) {
    return `<section class="block" id="promises"><h2>Promised vs delivered</h2>
      <p class="empty">${esc(g.note || "No forward-looking numbers found in the last four calls.")}</p></section>`;
  }
  const rank = (it) => (KEPT.includes(it.verdict) || BROKE.includes(it.verdict) ? 0 : 1);
  items.sort((a, b) => rank(a) - rank(b));
  const kept = items.filter((i) => KEPT.includes(i.verdict)).length;
  const broke = items.filter((i) => BROKE.includes(i.verdict)).length;
  const open = items.length - kept - broke;
  const range = (it) => it.target_low != null && it.target_high != null ? (it.target_low === it.target_high ? `${it.target_low}%` : `${it.target_low}–${it.target_high}%`)
    : it.target_low != null ? `${it.target_low}%+` : it.target_high != null ? `up to ${it.target_high}%` : "";
  const row = (it) => `<li id="g-${esc(it.id)}">
      <div class="promise-top"><span class="verdict ${esc(it.verdict)}">${VERDICT[it.verdict] || esc(it.verdict)}</span>
        <span>${esc(METRIC[it.metric] || it.metric)}, said ${esc(it.call)}${it.speaker ? ` by ${esc(it.speaker)}` : ""}</span></div>
      <blockquote>${esc(it.quote)}</blockquote>
      <div class="outcome">${it.actual != null
        ? `Reported <b>${it.metric === "ebitda_margin" ? `${it.actual}%` : pct(it.actual)}</b> ${esc(it.basis)}${range(it) ? ` against ${range(it)} promised` : ""}.`
        : esc(cap(it.why || it.basis) || (it.verdict === "too_early" ? "The period it refers to hasn't been reported yet." : "No number to check it against."))}
        ${it.judged_by === "model" ? `<span class="by-model">Judged from the text, not computed.</span>` : ""}
        ${it.source_url ? `<a class="cite" href="${esc(it.source_url)}" target="_blank" rel="noopener">${esc(it.call)}${it.page ? ` p${it.page}` : ""}</a>` : ""}</div>
    </li>`;
  // Checked promises first; only a few unverifiable ones on show, the rest folded.
  const shown = items.slice(0, kept + broke + 3), rest = items.slice(kept + broke + 3);
  const li = shown.map(row).join("") + (rest.length ? `<li style="border:0;padding:0"><details class="fold" style="margin:6px 0 0">
    <summary>${rest.length} more statements we can't check yet</summary><ul class="promises">${rest.map(row).join("")}</ul></details></li>` : "");
  const now = d.synthesis?.guidance_now || [];
  const nvn = d.synthesis?.narrative_vs_numbers || [];
  return `<section class="block" id="promises"><h2>Promised vs delivered</h2>
    <p class="lede">What management guided on the last ${g.calls?.length || 4} calls, checked against the quarters reported since.</p>
    <div class="score"><div><b>${kept}</b>kept</div><div><b>${broke}</b>missed</div><div><b>${open}</b>open</div></div>
    <ul class="promises">${li}</ul>
    ${now.length ? `<h2 style="margin-top:22px;font-size:16px">What they guide now</h2><ul class="nvn">${now.map((x) =>
      `<li><div class="said"><b>${esc(x.metric)}:</b> ${esc(x.what)}${cite(x.source)}</div></li>`).join("")}</ul>` : ""}
    ${nvn.length ? `<h2 style="margin-top:22px;font-size:16px">Story vs numbers</h2><ul class="nvn">${nvn.map((x) => `<li>
      <div class="stance ${esc(x.stance)}">${x.stance === "agrees" ? "Numbers agree" : x.stance === "diverges" ? "Numbers disagree" : "Unclear"}</div>
      <div class="said">${esc(x.claim)}</div><div class="shows">${esc(x.reality)}${cite(x.source)}</div></li>`).join("")}</ul>` : ""}
  </section>`;
}

function flagList(m, section) {
  const f = (m.flags || []).filter((x) => x.section === section);
  return f.length ? `<ul class="flags">${f.map((x) => `<li class="${esc(x.tone)}">${esc(x.text)}</li>`).join("")}</ul>` : "";
}

function numbers(m) {
  const s = m.snapshot;
  const kv = [
    ["Revenue, last 12m", crore(s.ttm_revenue)], ["Profit, last 12m", crore(s.ttm_pat)],
    [m.lender ? "Financing margin" : "Operating margin", s.opm != null ? `${s.opm}%` : "—"], ["Net margin", s.ttm_pat_margin != null ? `${s.ttm_pat_margin}%` : "—"],
    [m.lender ? "ROE" : "ROCE", (m.lender ? s.roe : s.roce) != null ? `${m.lender ? s.roe : s.roce}%` : "—"],
    ["Debt / equity", m.lender ? "n/a (lender)" : s.de != null ? `${s.de.toFixed(2)}×` : "—"],
    ["Market cap", crore(s.market_cap)], ["P/E", s.pe != null ? num(s.pe, 1) : "—"],
  ];
  return `<section class="block" id="numbers"><h2>Numbers at a glance</h2>
    <div class="kv">${kv.map(([k, v]) => `<div>${esc(k)}<b>${esc(v)}</b></div>`).join("")}</div></section>`;
}

function trajectory(m) {
  const a = m.annual, t = m.trajectory;
  const line = (label, v3, v5) => v3 == null && v5 == null ? "" : `<div>${label}<b>${v3 != null ? pct(v3, { sign: false }) : "—"}</b><span style="font-size:12px">${v5 != null ? `5y ${pct(v5, { sign: false })}` : ""}</span></div>`;
  return `<section class="block" id="trajectory"><h2>Trajectory</h2>
    <p class="lede">Revenue by year, with operating margin.</p>
    <div class="chart">${barsWithLine(a.years, a.revenue, a.opm)}</div>
    <div class="legend"><span><i style="background:var(--ink-2)"></i>Revenue</span><span><i style="background:var(--amber)"></i>Operating margin</span></div>
    <div class="kv">${line("Revenue growth, 3y a year", t.revenue_cagr_3y, t.revenue_cagr_5y)}${line("Profit growth, 3y a year", t.pat_cagr_3y, t.pat_cagr_5y)}</div>
    ${flagList(m, "trajectory")}</section>`;
}

function cash(m) {
  const a = m.annual, c = m.cash;
  return `<section class="block" id="cash"><h2>Cash quality</h2>
    <p class="lede">${c.conversion_5y_pct != null ? `Over five years, ₹${c.conversion_5y_pct} of operating cash for every ₹100 of reported profit.` : "Does profit turn into cash?"}</p>
    <div class="chart">${pairedBars(a.years, a.pat, a.cfo)}</div>
    <div class="legend"><span><i style="background:var(--rule)"></i>Profit</span><span><i style="background:var(--ink)"></i>Cash from operations</span></div>
    ${c.fcf_5y != null ? `<div class="kv"><div>Free cash flow, 5y (est.)<b>${crore(c.fcf_5y)}</b></div><div>Years with negative FCF<b>${c.negative_fcf_years} of 5</b></div></div>
      <div class="fine">FCF estimated as operating cash minus the change in fixed assets and work in progress, plus depreciation.</div>` : ""}
    ${flagList(m, "cash")}</section>`;
}

function balance(m) {
  const a = m.annual;
  if (m.lender) return `<section class="block" id="balance"><h2>Balance sheet</h2><p class="empty">For a lender, borrowing is the raw material, so debt-to-equity and working-capital days don't apply. Read asset quality in the annual report.</p></section>`;
  const lastWc = a.wc_days.filter((x) => x != null).slice(-1)[0];
  return `<section class="block" id="balance"><h2>Balance sheet</h2>
    <p class="lede">Borrowings by year, with debt-to-equity.</p>
    <div class="chart">${barsWithLine(a.years, a.borrowings, a.de, { lineFmt: (x) => `${x.toFixed(2)}×` })}</div>
    <div class="legend"><span><i style="background:var(--ink-2)"></i>Borrowings</span><span><i style="background:var(--amber)"></i>Debt / equity</span></div>
    <div class="kv"><div>Working-capital days<b>${lastWc != null ? num(lastWc) : "—"}</b></div><div>Net worth<b>${crore(a.equity.filter((x) => x != null).slice(-1)[0])}</b></div></div>
    ${flagList(m, "balance")}</section>`;
}

function business(d, cite) {
  const b = d.synthesis?.business;
  const segs = b?.segments || [];
  return `<section class="block" id="business"><h2>Business</h2>
    <p style="margin:8px 0 0">${esc(b?.summary || d.about || "No description available.")}</p>
    ${segs.length ? `<ul class="segments">${segs.map((s) => `<li><span>${esc(s.name)}${s.note ? ` <span style="color:var(--muted)">· ${esc(s.note)}</span>` : ""}${cite(s.source)}</span>
      <b>${s.share_pct != null ? `${s.share_pct}%` : ""}</b>${s.share_pct != null ? `<div class="bar"><span style="width:${Math.min(100, s.share_pct)}%"></span></div>` : ""}</li>`).join("")}</ul>` : ""}
  </section>`;
}

function cases(d, cite) {
  const s = d.synthesis;
  if (!s?.bull?.length && !s?.bear?.length) return "";
  const list = (xs) => `<ul>${xs.map((x) => `<li>${esc(x.point)}${cite(x.source)}</li>`).join("")}</ul>`;
  return `<section class="block" id="cases"><h2>Bull and bear</h2>
    <div class="cases"><div><h3 class="up">If it works</h3>${list(s.bull || [])}</div><div><h3 class="down">If it doesn't</h3>${list(s.bear || [])}</div></div></section>`;
}

function dossier(d) {
  const m = d.metrics, s = m.snapshot;
  const cite = citeFor(d);
  const jump = [["promises", "Promises"], ["numbers", "Numbers"], ["trajectory", "Trajectory"], ["cash", "Cash"], ["balance", "Balance sheet"],
    ["business", "Business"], ...(d.synthesis?.bull?.length ? [["cases", "Bull & bear"]] : []), ["sources", "Sources"]];
  return `
    <section class="dossier-head">
      <div class="sym">${esc(d.symbol)}${d.sample ? " · sample company" : ""}</div>
      <h1>${esc(d.name)}</h1>
      <div class="price">${[s.price != null ? `₹${num(s.price, 1)}` : "", s.market_cap != null ? `${crore(s.market_cap)} market cap` : "", d.basis ? `${esc(d.basis)} figures` : ""].filter(Boolean).join(", ")}</div>
    </section>
    ${d.synthesis?.one_line ? `<p class="takeaway">${esc(d.synthesis.one_line)}</p>` : ""}
    <nav class="jump" aria-label="Sections">${jump.map(([id, l]) => `<a href="#/ask/${esc(d.symbol)}/${id}">${l}</a>`).join("")}</nav>
    ${promises(d, cite)}${numbers(m)}${trajectory(m)}${cash(m)}${balance(m)}${business(d, cite)}${cases(d, cite)}
    <section class="block" id="sources"><h2>Sources</h2>
      <p class="lede">Primary documents only. Numbers are computed in code; the model only reads text.</p>
      <ul class="sources">${(d.sources || []).map((x) => `<li><span class="cite">${esc(x.id)}</span>${x.url ? `<a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.label)}</a>` : esc(x.label)}</li>`).join("")}</ul>
      <div class="fine">Built ${esc(new Date(d.generated_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }))} with ${esc(d.model)}.</div>
    </section>`;
}
