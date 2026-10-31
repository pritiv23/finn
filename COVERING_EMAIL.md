To: assessment@enam.com
Subject: ENAM - IIT screening - 2027

Hi ENAM team,

Here is my submission for the FINN build challenge.

- Prototype (open on a phone): [deployed link]
- Repository: [GitHub link]
- AI build history: [share link to the Claude conversation(s)]

**What I built**

FINN is built around one idea: an investor's day should have an end. The Brief opens with a single sentence, "4 things need you. 33 other filings didn't.", and each of those things is a card you clear or dig into. When they're gone, you're caught up. Everything else is either one line under "Worth a glance" or folded behind a count. Research works on any NSE symbol and leads with promised vs delivered: guidance from the last four concall transcripts, checked in code against the quarters reported after each call.

**Key decisions**

1. Numbers are computed in code; the model only reads text. Results figures are extracted from the filing, then EBITDA and every QoQ/YoY change are calculated in Python and cross-checked against the reported tables. A promise verdict like "15–18% guided, 17.5% reported, on track" is arithmetic, not opinion.
2. Classification uses rules, not a model. NSE's subject lines are consistent enough that ordered regexes sort filings into the reference taxonomy instantly, for free and the same way every time. The model budget goes to the few filings worth reading.
3. Cost. A fast model handles bulk extraction and a strong model makes one call per research report. Everything is cached on the prompt hash, and the transcripts are keyword-filtered before any model sees them. It runs on free tiers.
4. Management bios come from the filing. SEBI requires a brief profile of appointees in the disclosure, so the background is primary data. I link to LinkedIn rather than scraping it.
5. An unexplained move gets its own card. A stock that trips your volume or price rule with no filing behind it is often the most important item of the day.
6. The app always opens. It reads the live API if there is one, then static JSON, then labelled sample data, so the demo never breaks.

**Trade-offs and what I left out**

Real push notifications (the rules engine is ready for it), free-form chat, BSE as a second source and portfolio weighting. I preferred a narrow product where every screen works over a broad one.

**Next**

Web-push on rule hits, chat grounded in a dossier, a promise tracker that updates with every new call, and position-size-aware prioritisation.

Thanks for the interesting brief.

[Your name]
[Phone] · [LinkedIn]
