# FINN

A mobile-first investment agent built around one idea: **an investor's day should have an end.**

FINN reads every exchange filing and end-of-day move across a portfolio and opens with a single sentence: *"4 things need you. 33 other filings didn't."* The four are cards you either clear or dig into. When they're gone, you're caught up. Research is one tap from any card, and it leads with the question that separates analysis from summary: **did management deliver what they promised?**

## The three screens

**Brief (push).** Pick a window (24h, 3 days, 7 days). Every filing in it is sorted into three tiers:

| Tier | What happens | Cost |
|---|---|---|
| Needs you | A card, enriched for its type (below). Swipe or tap Done to clear it. | a fast-model call, only for these |
| Worth a glance | One line, using the exchange's own summary text | free |
| Routine | Folded behind a count (ESOP allotments, trading-window notices, newspaper ads…) | free |

A strip of ticks under the headline draws every filing in the window, coloured by tier. The ratio of amber to grey is the product's argument in one line.

How each kind of card is enriched:
- **Results:** Revenue, EBITDA, PBT and PAT, QoQ and YoY, read from the results PDF. A cheap model only *finds* the numbers on the page. EBITDA and every percentage are computed in Python, then cross-checked against the reported quarterly tables.
- **Management change:** who leaves, who joins, and the incoming person's background. Under SEBI's Reg. 30 rules, appointment filings include a "brief profile" annexure, so the bio comes from the primary filing itself. A LinkedIn search link sits next to it. LinkedIn is not scraped.
- **Market reaction:** if the stock also moved past your thresholds that day, the card shows it. A move past your thresholds *with no filing* becomes its own card ("with no filing to explain it"), because unexplained moves are where you want to pick up the phone.

**Research (pull).** Any NSE symbol that screener.in covers works, not just the demo set.
1. **Promised vs delivered.** The last four concall transcripts are filtered to guidance-sounding paragraphs, and a fast model lists management's forward-looking statements with quote and page. Code then checks every numeric promise against the quarters reported *after* the call: *"15–18% revenue growth for FY27" → reported 17.5% over the first two quarters → On track.* A promise that can't be measured is judged by the smart model and labelled as judged, not computed.
2. **Story vs numbers, what they guide now, bull and bear.** One smart-model call. It sees only our computed numbers, verbatim transcript excerpts and annual-report MD&A excerpts, and every point must cite a source id.
3. **Numbers, trajectory, cash quality, balance sheet.** All computed in code from the reported multi-year tables (CAGR, margin trend, CFO/PAT conversion, estimated FCF, D/E, working-capital days), plus rule-based flags such as *"Only 65% of five years' profit showed up as operating cash."* Lenders are detected, and ratios that don't apply to them are hidden.

**Watch.** Alert rules are written as sentences with steppers: *"Tell me when volume is above [2.0×] its [20]-day average."* The rules run on the device, so changing a threshold updates the Brief instantly. Category toggles decide which material filings reach the top.

## Architecture

```
portfolio.toml
     │
     ▼
finn/sources/   prices.py (yfinance → Yahoo chart API fallback) · nse.py (announcements API)
                screener.py (tables + AR/transcript links) · pdfs.py (download, cache, page text)
     │
     ├─ finn/push/   classify.py  ~40 ordered regex rules → category + tier  (no model)
     │               enrich.py    results numbers · people · one-liners      (fast model, few calls)
     │               digest.py    → web/data/snapshot.json
     │
     └─ finn/pull/   metrics.py   every number in a dossier                  (no model)
                     guidance.py  transcripts → guidance → code-checked verdicts (fast model)
                     research.py  one grounded synthesis                     (smart model, 1 call)
                                  → web/data/research/SYMBOL.json
finn/api.py     Starlette: /api/snapshot, /api/research/{symbol} (background job + polling), static app
web/            no-build vanilla JS PWA. Reads the API if one is up, else static JSON, else sample data
```

**Model routing.** Groq's free tier by default: `llama-3.1-8b-instant` for extraction, `llama-3.3-70b-versatile` for the one reasoning step. Gemini, or any OpenAI-compatible endpoint, is one env var away. Every response is cached on its prompt hash, and filings never change, so a re-run costs nothing. `python -m finn usage` prints the token ledger. With no key at all, everything except the transcript reading and the written synthesis still works.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # add a free GROQ_API_KEY
python -m finn demo               # real snapshot + dossiers for the demo companies
python -m finn serve              # http://localhost:8000, open it on your phone via your LAN IP
python -m pytest -q               # 32 offline tests
```

Until you run `demo`, the app shows clearly labelled **sample data** (invented filings and a fictional company), so you can see the product first.

## Deploy

- **Full app (research on any symbol):** push to GitHub and create a Render web service from `render.yaml`. Set `GROQ_API_KEY`.
- **Static only:** after `python -m finn demo`, the `web/` folder is a complete site (GitHub Pages, Netlify, Vercel). The Brief and the pre-built dossiers work, with no server needed.
- NSE sometimes blocks cloud IPs. If the hosted refresh fails, run `python -m finn refresh` locally and commit `web/data/snapshot.json`.

## Deliberately left out

- **Real push notifications.** The snapshot and rules are ready for it (a cron job plus web-push). For a demo, an in-app inbox you can finish made the point better.
- **Free-form chat.** Research is structured on purpose: a promise scorecard is more useful than a chat box that summarises. Chat over a dossier is the next step.
- **BSE as a second filings source,** and intraday data. The brief asks for end-of-day.

## Next

Web-push on rule hits, chat over a dossier ("why did margins fall in Q3?"), tracking promises across quarters so every new call updates the scorecard, and portfolio weights so a 1% position can't outrank a 10% one.
