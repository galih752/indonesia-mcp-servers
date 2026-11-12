"""Indonesian News MCP — news tools for AI agents.

Tools
-----
latest_news       newest national headlines with full article text
search_headlines  match a keyword across the newest headlines (fast, no bodies)
get_article       one article by URL

Clients connect over Streamable HTTP at /mcp with their Apify token:

    https://<username>--indonesian-news-mcp.apify.actor/mcp
    Authorization: Bearer <APIFY_TOKEN>

Each successful tool call charges one pay-per-event `tool-call`.
"""

from __future__ import annotations

import json
import os

import httpx
import uvicorn
from fastmcp import FastMCP

from .extract import scrape_article
from .feeds import DEFAULT_SOURCES, latest_candidates
from .feeds import latest_news as fetch_latest_news

_CHARGE_EVENT = "tool-call"


async def _charge() -> None:
    token = os.environ.get("APIFY_TOKEN")
    run_id = os.environ.get("APIFY_ACTOR_RUN_ID")
    if not token or not run_id:
        return
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                f"https://api.apify.com/v2/actor-runs/{run_id}/charge",
                json={"eventName": _CHARGE_EVENT, "count": 1},
                headers={"Authorization": f"Bearer {token}"},
            )
    except Exception:
        pass


mcp = FastMCP(
    name="indonesian-news-mcp",
    instructions=(
        "Indonesian news tools. Use latest_news to read the newest national "
        "headlines with full article text (CNN Indonesia and Antara RSS), "
        "search_headlines to find headlines about a topic, and get_article to "
        "fetch one article by URL from Detik, Kompas, Tempo, CNN Indonesia or Antara."
    ),
)


def _out(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)


def _sources(value: str | None) -> list[str]:
    chosen = [s.strip() for s in (value or "").split(",") if s.strip()]
    return [s for s in chosen if s] or list(DEFAULT_SOURCES)


@mcp.tool()
async def latest_news(limit: int = 10, keyword: str = "", sources: str = "") -> str:
    """Get the newest Indonesian national headlines with full article text.

    Args:
        limit: Number of articles (1-20, default 10).
        keyword: Optional headline filter, e.g. 'ekonomi' or 'pemilu'.
        sources: Comma-separated feeds: cnnindonesia, antaranews (default both). Tempo may need a proxy.

    Returns:
        JSON with count and items (title, source, published_at, description, content, url).
    """
    items, errors = await fetch_latest_news(
        limit=max(1, min(limit, 20)),
        sources=_sources(sources),
        keyword=keyword.strip() or None,
    )
    if not items:
        return _out({"count": 0, "items": [], "errors": errors[:5]})
    await _charge()
    return _out({"count": len(items), "items": items, "errors": errors[:5]})


@mcp.tool()
async def search_headlines(keyword: str, limit: int = 10, sources: str = "") -> str:
    """Search the newest Indonesian headlines for a keyword (headline-only, fast).

    Args:
        keyword: Word or phrase to match in headlines, e.g. 'inflasi' or 'Gibran'.
        limit: Number of matches (1-30, default 10).
        sources: Comma-separated feeds: cnnindonesia, antaranews (default both).

    Returns:
        JSON with count and items (title, source, published, url).
    """
    candidates = await latest_candidates(
        sources=_sources(sources),
        per_source=30,
        keyword=keyword.strip() or None,
    )
    items = candidates[: max(1, min(limit, 30))]
    if items:
        await _charge()
    return _out({"count": len(items), "items": items})


@mcp.tool()
async def get_article(url: str) -> str:
    """Fetch one Indonesian news article by URL as clean JSON.

    Args:
        url: Article URL from detik.com, kompas.com, tempo.co, cnnindonesia.com, antaranews.com, etc.

    Returns:
        JSON with title, author, published_at, description, content, image and url.
    """
    try:
        record = await scrape_article(url)
    except ValueError as exc:
        return _out({"error": str(exc)})
    await _charge()
    return _out(record)


app = mcp.http_app(transport="streamable-http")


def main() -> None:
    port = int(os.environ.get("APIFY_CONTAINER_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
