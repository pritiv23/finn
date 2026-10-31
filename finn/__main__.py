"""Command line.

  python -m finn refresh [--days 7]     fetch prices + filings, write web/data/snapshot.json
  python -m finn research DIXON [...]   build dossiers into web/data/research/
  python -m finn demo                   refresh + research for every demo symbol
  python -m finn serve [--port 8000]    API + app on one port
  python -m finn usage                  what the model calls so far have cost, in tokens
"""
from __future__ import annotations

import argparse
import json
import sys
import time


def main(argv=None):
    ap = argparse.ArgumentParser(prog="finn")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("refresh")
    r.add_argument("--days", type=int, default=7)
    rs = sub.add_parser("research")
    rs.add_argument("symbols", nargs="+")
    sub.add_parser("demo")
    s = sub.add_parser("serve")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--host", default="0.0.0.0")
    sub.add_parser("usage")
    a = ap.parse_args(argv)

    if a.cmd in ("refresh", "demo"):
        from .push import digest

        t = time.time()
        snap = digest.build(days=getattr(a, "days", 7))
        path = digest.write(snap)
        tiers = {1: 0, 2: 0, 3: 0}
        for f in snap["filings"]:
            tiers[f["tier"]] += 1
        print(f"wrote {path}: {len(snap['filings'])} filings "
              f"({tiers[3]} headline, {tiers[2]} glance, {tiers[1]} routine) in {time.time() - t:.0f}s")

    if a.cmd in ("research", "demo"):
        from .config import load_portfolio
        from .pull import research

        symbols = a.symbols if a.cmd == "research" else load_portfolio().research_demo
        for sym in symbols:
            t = time.time()
            try:
                d = research.build(sym, progress=lambda s: print(f"  {sym}: {s}…"))
                print(f"wrote {research.write(d)} in {time.time() - t:.0f}s")
            except Exception as e:
                print(f"  {sym}: failed — {e}", file=sys.stderr)

    if a.cmd == "serve":
        import uvicorn

        uvicorn.run("finn.api:app", host=a.host, port=a.port)

    if a.cmd == "usage":
        from .config import CACHE_DIR

        p = CACHE_DIR / "usage.json"
        print(p.read_text() if p.exists() else json.dumps({}))


if __name__ == "__main__":
    main()
