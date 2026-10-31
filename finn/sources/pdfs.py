"""Download filings and pull text out of them, page by page.

Exchange PDFs are the slowest, heaviest thing we touch, so: cache the bytes
forever (filings don't change), cache extracted text, and only read the pages
a task needs.
"""
from __future__ import annotations

import io
import re

import requests

from .. import cache
from ..config import BROWSER_UA

MAX_BYTES = 40 * 1024 * 1024


def download(url: str) -> bytes | None:
    def fetch():
        headers = {"User-Agent": BROWSER_UA, "Accept": "application/pdf,*/*"}
        if "bseindia" in url:
            headers["Referer"] = "https://www.bseindia.com/"
        if "nseindia" in url:
            headers["Referer"] = "https://www.nseindia.com/"
        try:
            r = requests.get(url, headers=headers, timeout=60, stream=True)
            r.raise_for_status()
            data = r.raw.read(MAX_BYTES + 1, decode_content=True)
            if len(data) > MAX_BYTES or not data.startswith(b"%PDF"):
                return None
            return data
        except requests.RequestException:
            return None

    return cache.cached_bytes("pdf", url, fetch)


def pages(url: str, first: int | None = None, fast: bool = False) -> list[str]:
    """Text of each page (optionally only the first N).

    pdfplumber keeps table columns lined up, which matters for results statements.
    `fast=True` uses pypdf instead: several times quicker, good enough for prose —
    the right choice for a 300-page annual report or a transcript.
    """
    key = f"{url}:{first}:{fast}"

    def extract():
        data = download(url)
        if not data:
            return None
        out = []
        try:
            if fast:
                from pypdf import PdfReader

                reader = PdfReader(io.BytesIO(data))
                for i, page in enumerate(reader.pages):
                    if first is not None and i >= first:
                        break
                    out.append(page.extract_text() or "")
            else:
                import pdfplumber

                with pdfplumber.open(io.BytesIO(data)) as pdf:
                    for i, page in enumerate(pdf.pages):
                        if first is not None and i >= first:
                            break
                        out.append(page.extract_text() or "")
        except Exception:
            return None
        return out

    return cache.cached_json("pdftext", key, extract) or []


def find_pages(texts: list[str], patterns: list[str], window: int = 0) -> list[int]:
    """Indices of pages matching any pattern, plus `window` pages after each hit."""
    rx = re.compile("|".join(patterns), re.I)
    hits: set[int] = set()
    for i, t in enumerate(texts):
        if rx.search(t):
            hits.update(range(i, min(len(texts), i + window + 1)))
    return sorted(hits)
