// Routing and boot. Hash routes so the app works on any static host:
//   #/brief   #/ask   #/ask/SYMBOL[/section]   #/watch

import { renderAskHome, renderDossier } from "./ask.js";
import { renderBrief } from "./brief.js";
import { loadSnapshot } from "./data.js";
import { $, esc } from "./ui.js";
import { renderWatch } from "./watch.js";

let snap = null;
let loadedAt = 0;

async function route() {
  const view = $("#view");
  const [, tab = "brief", sym, focus] = (location.hash || "#/brief").split("/");
  document.querySelectorAll(".tabs a").forEach((a) => (a.dataset.tab === tab ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current")));

  if (!snap && tab !== "ask") {
    try { snap = await loadSnapshot(); loadedAt = Date.now(); } catch (e) {
      view.innerHTML = `<section class="ask-head"><h1>No data yet</h1><p class="note">${esc(e.message)}</p></section>`;
      return;
    }
  }
  if (snap) {
    $("#sample-banner").hidden = !snap.sample;
    const t = new Date(snap.generated_at);
    $("#top-meta").textContent = `As of ${t.toLocaleDateString("en-IN", { day: "numeric", month: "short" })}, ${t.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false })}`;
  }

  if (tab === "ask" && sym) await renderDossier(view, decodeURIComponent(sym), focus);
  else if (tab === "ask") await renderAskHome(view, snap);
  else if (tab === "watch") renderWatch(view, snap);
  else renderBrief(view, snap);
  if (!(tab === "ask" && sym && focus)) window.scrollTo(0, 0);
}

window.addEventListener("hashchange", route);
// Coming back to the app after a while should show the latest brief.
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible" && snap && Date.now() - loadedAt > 30 * 60e3) { snap = null; route(); }
});
// Load the snapshot even if the first screen is research, for the banner and suggestions.
loadSnapshot().then((s) => { if (!snap) { snap = s; loadedAt = Date.now(); } $("#sample-banner").hidden = !s.sample; }).catch(() => {});
route();
