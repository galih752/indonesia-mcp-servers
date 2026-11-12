"""Glints Jobs MCP — Indonesian job search tools for AI agents.

Tools
-----
search_jobs  find Glints jobs by keyword (optional city filter)
get_job      one job by URL with the full description

Clients connect over Streamable HTTP at /mcp with their Apify token:

    https://<username>--glints-jobs-mcp.apify.actor/mcp
    Authorization: Bearer <APIFY_TOKEN>

Each successful tool call charges one pay-per-event `tool-call`.
"""

from __future__ import annotations

import json
import os

import httpx
import uvicorn
from fastmcp import FastMCP

from .glints import fetch_page, is_search_url, parse_job, parse_search
from .glints import search_jobs as fetch_jobs

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
    name="glints-jobs-mcp",
    instructions=(
        "Indonesian job market tools for Glints. Use search_jobs to find open "
        "roles by keyword and optional city, then get_job by URL for the full "
        "description. Returns salary range, skills, experience and company details."
    ),
)


def _out(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)


@mcp.tool()
async def search_jobs(keyword: str, location: str = "", limit: int = 10) -> str:
    """Search Glints job listings in Indonesia.

    Args:
        keyword: Role or skill, e.g. 'data engineer', 'UI designer', 'admin'.
        location: Optional city/province filter, e.g. 'Jakarta' or 'Bandung'.
        limit: Number of jobs (1-50, default 10).

    Returns:
        JSON with count and items (title, company, city, salary, skills, url).
    """
    items, errors = await fetch_jobs(
        keyword,
        limit=max(1, min(limit, 50)),
        location=location.strip() or None,
    )
    if not items:
        return _out({"count": 0, "items": [], "errors": errors[:3]})
    await _charge()
    return _out({"count": len(items), "items": items, "errors": errors[:3]})


@mcp.tool()
async def get_job(url: str) -> str:
    """Fetch one Glints job by URL with the full description.

    Args:
        url: A glints.com job URL, e.g. https://glints.com/id/opportunities/jobs/<id>.

    Returns:
        JSON with title, company, salary, location, skills, description and url.
    """
    if "glints.com" not in url:
        return _out({"error": "url must be a glints.com URL"})
    try:
        html = await fetch_page(url)
        if is_search_url(url):
            items = parse_search(html)
            await _charge()
            return _out({"count": len(items), "items": items})
        job = parse_job(html)
    except ValueError as exc:
        return _out({"error": str(exc)})
    await _charge()
    return _out(job)


app = mcp.http_app(transport="streamable-http")


def main() -> None:
    port = int(os.environ.get("APIFY_CONTAINER_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
