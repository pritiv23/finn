// Where data comes from, in order of preference:
//   1. the API (python -m finn serve) — live, and can research any symbol
//   2. static files written by the pipeline (web/data/…) — for static hosting
//   3. bundled sample data — so the app always opens
// The UI never needs to know which one answered, except to label sample data.

async function getJSON(url, opts) {
  const r = await fetch(url, { cache: "no-cache", ...opts });
  if (!r.ok) {
    const e = new Error(`${r.status}`);
    e.status = r.status;
    try { e.body = await r.json(); } catch { /* not json */ }
    throw e;
  }
  return r.json();
}

let apiUp = null;
export async function hasApi() {
  if (apiUp !== null) return apiUp;
  try {
    const h = await getJSON("api/health", { signal: AbortSignal.timeout(2500) });
    apiUp = !!h.ok;
  } catch { apiUp = false; }
  return apiUp;
}

export async function loadSnapshot() {
  const tries = ["data/snapshot.json", "data/sample/snapshot.json"];
  if (await hasApi()) tries.unshift("api/snapshot");
  for (const url of tries) {
    try { return await getJSON(url); } catch { /* next */ }
  }
  throw new Error("No data found. Run `python -m finn refresh`.");
}

export async function researchIndex() {
  const out = new Set();
  for (const url of ["data/research/index.json", "data/sample/research/index.json"]) {
    try { (await getJSON(url)).forEach((s) => out.add(s)); } catch { /* none */ }
  }
  return [...out];
}

// onStage(text) is called while a fresh dossier is being built on the server.
export async function loadResearch(symbol, onStage = () => {}) {
  symbol = symbol.toUpperCase().trim();
  let apiError = null;
  if (await hasApi()) {
    for (let i = 0; i < 90; i++) {
      let res;
      try {
        res = await getJSON(`api/research/${encodeURIComponent(symbol)}`, { method: i === 0 ? "POST" : "GET" });
      } catch (e) { apiError = e.body?.job?.error || null; break; }
      if (res?.metrics) return res;
      if (res?.job) { onStage(res.job.stage); await new Promise((r) => setTimeout(r, 2000)); continue; }
      break;
    }
  }
  for (const url of [`data/research/${symbol}.json`, `data/sample/research/${symbol}.json`]) {
    try { return await getJSON(url); } catch { /* next */ }
  }
  const err = new Error(apiError || `No dossier for ${symbol} on this deployment.`);
  err.offline = !apiError;
  throw err;
}
