"""RSS discovery + batch scraping for Indonesian news outlets.

Feeds proven live from a datacenter IP on 2026-11-12 (see RE.md):
  tempo        https://rss.tempo.co/nasional              200, 50 items
  cnnindonesia https://www.cnnindonesia.com/nasional/rss  200, 100 items
  antaranews   https://www.antaranews.com/rss/terkini.xml 200, 50 items

Detik/Kompas RSS are dead or blocked; their article URLs still work in
single-URL mode, so they stay supported there.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from html import unescape
from typing import Any

import httpx

from .extract import scrape_article

FEEDS: dict[str, str] = {
    "tempo": "https://rss.tempo.co/nasional",
    "cnnindonesia": "https://www.cnnindonesia.com/nasional/rss",
    "antaranews": "https://www.antaranews.com/rss/terkini.xml",
}

# Tempo serves RSS from datacenter IPs but blocks its article pages (403 even
# with browser TLS), so it is opt-in; the default pair works from Apify.
DEFAULT_SOURCES = ["cnnindonesia", "antaranews"]

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml,application/xml,text/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9",
}


def parse_feed(xml_text: str, source: str) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    channel = root.find("channel") or root
    out: list[dict[str, Any]] = []
    for item in channel.findall("item"):
        link = (item.findtext("link") or "").strip()
        title = unescape(re.sub(r"<[^>]+>", "", item.findtext("title") or "")).strip()
        if not link or not title:
            continue
        out.append(
            {
                "source": source,
                "title": title,
                "url": link,
                "published": (item.findtext("pubDate") or "").strip(),
            }
        )
    return out


async def fetch_feed(source: str, per_source: int = 15) -> list[dict[str, Any]]:
    url = FEEDS.get(source)
    if not url:
        return []
    async with httpx.AsyncClient(headers=_HEADERS, timeout=25, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
    return parse_feed(resp.text, source)[:per_source]


def _interleave(batches: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Round-robin across sources so one outlet does not dominate the demo."""
    out: list[dict[str, Any]] = []
    i = 0
    while True:
        added = False
        for batch in batches:
            if i < len(batch):
                out.append(batch[i])
                added = True
        if not added:
            return out
        i += 1


async def latest_candidates(
    sources: list[str] | None = None,
    per_source: int = 15,
    keyword: str | None = None,
) -> list[dict[str, Any]]:
    chosen = [s for s in (sources or DEFAULT_SOURCES) if s in FEEDS] or DEFAULT_SOURCES
    batches = []
    for source in chosen:
        try:
            batches.append(await fetch_feed(source, per_source))
        except Exception as exc:  # noqa: BLE001 - one dead feed must not kill the run
            print(f"[feed] WARNING: {source} feed unavailable: {exc}", flush=True)
            batches.append([])
    candidates = _interleave(batches)
    if keyword:
        needle = keyword.lower()
        candidates = [c for c in candidates if needle in c["title"].lower()]
    return candidates


async def latest_news(
    limit: int = 10,
    sources: list[str] | None = None,
    keyword: str | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Scrape the newest headlines; returns (records, per-article errors)."""
    candidates = await latest_candidates(sources, per_source=max(limit, 10), keyword=keyword)
    if not candidates:
        return [], ["no matching RSS items"]

    items: list[dict[str, Any]] = []
    errors: list[str] = []
    for candidate in candidates[: limit * 3]:
        if len(items) >= limit:
            break
        try:
            record = await scrape_article(
                candidate["url"],
                source=candidate["source"],
                keyword=keyword,
            )
        except Exception as exc:  # noqa: BLE001 - skip one blocked publisher, keep the rest
            errors.append(f"{candidate['source']}: {exc}")
            print(f"[latest] skip {candidate['url']}: {exc}", flush=True)
            continue
        items.append(record)
    return items, errors


async def scrape_many(urls: list[str], limit: int = 20) -> tuple[list[dict[str, Any]], list[str]]:
    """Scrape an explicit list of article URLs."""
    items: list[dict[str, Any]] = []
    errors: list[str] = []
    for url in urls[:limit]:
        try:
            record = await scrape_article(url)
        except Exception as exc:  # noqa: BLE001 - partial success is the contract
            errors.append(f"{url}: {exc}")
            print(f"[batch] skip {url}: {exc}", flush=True)
            continue
        items.append(record)
    return items, errors
