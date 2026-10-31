"""Paths, portfolio and environment. One place, so nothing else reads env vars directly."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Read .env without adding a dependency. Real environment variables win.
_env = ROOT / ".env"
if _env.exists():
    for _line in _env.read_text().splitlines():
        _k, _, _v = _line.partition("=")
        _v = _v.split("#", 1)[0].strip()
        if _k.strip() and not _k.startswith("#") and _v:
            os.environ.setdefault(_k.strip(), _v)
WEB_DIR = ROOT / "web"
DATA_OUT = WEB_DIR / "data"            # what the frontend reads when no API is running
CACHE_DIR = Path(os.getenv("FINN_CACHE_DIR", ROOT / ".cache"))

# A real browser UA. NSE and BSE reject the default python-requests one.
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)


@dataclass
class Holding:
    symbol: str
    name: str
    sector: str


@dataclass
class AlertDefaults:
    volume_multiple: float = 2.0
    volume_lookback_days: int = 20
    price_move_pct: float = 4.0
    always_surface: list[str] = field(default_factory=list)


@dataclass
class Portfolio:
    holdings: list[Holding]
    research_demo: list[str]
    alerts: AlertDefaults

    @property
    def symbols(self) -> list[str]:
        return [h.symbol for h in self.holdings]


def load_portfolio(path: Path | None = None) -> Portfolio:
    path = path or Path(os.getenv("FINN_PORTFOLIO", ROOT / "portfolio.toml"))
    raw = tomllib.loads(path.read_text())
    return Portfolio(
        holdings=[Holding(**h) for h in raw["holding"]],
        research_demo=raw.get("research", {}).get("demo", []),
        alerts=AlertDefaults(**raw.get("alerts", {})),
    )
