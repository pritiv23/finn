// Small shared helpers: escaping, number formatting, time, storage, tiny SVG charts.

export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

export const $ = (sel, root = document) => root.querySelector(sel);

const IN = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
const IN1 = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 1 });

export function num(v, digits = 0) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return (digits ? IN1 : IN).format(v);
}

export function crore(v) {
  if (v === null || v === undefined) return "—";
  return `₹${IN.format(v)} cr`;
}

export function pct(v, { sign = true, digits = 1 } = {}) {
  if (v === null || v === undefined) return "—";
  const s = sign && v > 0 ? "+" : "";
  return `${s}${v.toFixed(digits)}%`;
}

export const tone = (v) => (v === null || v === undefined ? "flat" : v > 0.05 ? "up" : v < -0.05 ? "down" : "flat");

export function when(iso, now = new Date()) {
  if (!iso) return "";
  const t = new Date(iso);
  const mins = Math.round((now - t) / 60000);
  if (mins < 60) return `${Math.max(1, mins)}m ago`;
  if (mins < 60 * 12) return `${Math.round(mins / 60)}h ago`;
  const day = t.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });
  const time = t.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false });
  return `${day}, ${time}`;
}

// localStorage can be missing or throw (private mode, embedded previews): degrade to memory.
const mem = {};
export const store = {
  get(key, fallback) {
    try {
      const v = localStorage.getItem(`finn:${key}`);
      return v === null ? fallback : JSON.parse(v);
    } catch { return key in mem ? mem[key] : fallback; }
  },
  set(key, value) {
    mem[key] = value;
    try { localStorage.setItem(`finn:${key}`, JSON.stringify(value)); } catch { /* memory only */ }
  },
};

let toastTimer;
export function toast(text, action) {
  const el = $("#toast");
  el.innerHTML = `<span>${esc(text)}</span>${action ? `<button type="button">${esc(action.label)}</button>` : ""}`;
  el.hidden = false;
  if (action) el.querySelector("button").onclick = () => { el.hidden = true; action.run(); };
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.hidden = true), 4000);
}

// ---- charts ----------------------------------------------------------------------

export function sparkline(values, { w = 74, h = 26, highlight = false } = {}) {
  const v = values.filter((x) => x != null);
  if (v.length < 2) return "";
  const lo = Math.min(...v), hi = Math.max(...v), span = hi - lo || 1;
  const pts = v.map((x, i) => `${(i / (v.length - 1)) * w},${h - 2 - ((x - lo) / span) * (h - 4)}`).join(" ");
  const last = v[v.length - 1], first = v[0];
  const color = last >= first ? "var(--up)" : "var(--down)";
  return `<svg viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" aria-hidden="true">
    <polyline points="${pts}" fill="none" stroke="${highlight ? "var(--amber)" : color}" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/></svg>`;
}

const short = (label) => (label || "").replace(/^Mar (\d{2})(\d{2})$/, "FY$2").replace(/^(\w{3}) (\d{2})(\d{2})$/, "$1 '$3");

// Bars (one series) with an optional line on a second scale — revenue + margin.
export function barsWithLine(labels, bars, line, { barColor = "var(--ink-2)", lineColor = "var(--amber)", lineFmt = (x) => `${x}%` } = {}) {
  const W = 320, H = 150, top = 18, base = 122;
  const n = labels.length;
  if (!n) return "";
  const bmax = Math.max(...bars.filter((x) => x != null), 1);
  const slot = W / n, bw = Math.min(26, slot * 0.55);
  const lv = (line || []).filter((x) => x != null);
  const lmin = Math.min(...lv), lmax = Math.max(...lv), lspan = lmax - lmin || 1;
  let out = "";
  bars.forEach((b, i) => {
    if (b == null) return;
    const hgt = (b / bmax) * (base - top - 14);
    const x = i * slot + (slot - bw) / 2;
    out += `<rect x="${x}" y="${base - hgt}" width="${bw}" height="${hgt}" rx="3" fill="${barColor}" opacity="${i === n - 1 ? 1 : 0.55}"/>`;
    out += `<text x="${i * slot + slot / 2}" y="${base + 16}" text-anchor="middle">${esc(short(labels[i]))}</text>`;
  });
  if (lv.length > 1) {
    const y = (v) => top + 6 + (1 - (v - lmin) / lspan) * 40;
    const pts = line.map((v, i) => (v == null ? null : `${i * slot + slot / 2},${y(v)}`)).filter(Boolean).join(" ");
    out += `<polyline points="${pts}" fill="none" stroke="${lineColor}" stroke-width="2.2" stroke-linejoin="round"/>`;
    line.forEach((v, i) => {
      if (v == null) return;
      out += `<circle cx="${i * slot + slot / 2}" cy="${y(v)}" r="3" fill="${lineColor}"/>`;
      if (i === 0 || i === n - 1) out += `<text x="${i * slot + slot / 2}" y="${y(v) - 8}" text-anchor="middle" style="fill:var(--amber-ink)">${esc(lineFmt(v))}</text>`;
    });
  }
  return `<svg viewBox="0 0 ${W} ${H}" role="img">${out}</svg>`;
}

// Paired bars: profit vs the cash it produced, per year.
export function pairedBars(labels, a, b, { aColor = "var(--rule)", bColor = "var(--ink)" } = {}) {
  const W = 320, H = 150, top = 10, mid = 112;
  const n = labels.length;
  const all = [...a, ...b].filter((x) => x != null);
  if (!n || !all.length) return "";
  const max = Math.max(...all.map(Math.abs), 1);
  const scale = (v) => (Math.abs(v) / max) * (mid - top - 4);
  const slot = W / n, bw = Math.min(13, slot * 0.3);
  let out = `<line x1="0" x2="${W}" y1="${mid}" y2="${mid}" stroke="var(--rule)"/>`;
  labels.forEach((l, i) => {
    const cx = i * slot + slot / 2;
    [[a[i], aColor, -bw - 1], [b[i], bColor, 1]].forEach(([v, c, dx]) => {
      if (v == null) return;
      const h = scale(v);
      out += `<rect x="${cx + dx}" y="${v >= 0 ? mid - h : mid}" width="${bw}" height="${Math.max(1, h)}" rx="2" fill="${v < 0 ? "var(--down)" : c}"/>`;
    });
    out += `<text x="${cx}" y="${H - 6}" text-anchor="middle">${esc(short(l))}</text>`;
  });
  return `<svg viewBox="0 0 ${W} ${H}" role="img">${out}</svg>`;
}
