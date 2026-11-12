"""Article extraction: JSON-LD → OpenGraph → body fallback.

Kept dependency-free (stdlib + httpx), with an optional curl_cffi browser-TLS
fallback for publishers that block plain HTTP clients (e.g. Tempo).
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from html import unescape
from typing import Any

import httpx

_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
)
_HEADERS = {
    "User-Agent": _UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
}

_BODY_CLASSES = (
    r'class="[^"]*(?:body-text|read__content|article-content|'
    r'entry-content|post-content|detail__body|content__article|detail-text)[^"]*"'
)

_TAG_RE = re.compile(r"<(/?)div\b", re.IGNORECASE)


def _jsonld_blocks(html: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in re.finditer(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    ):
        raw = m.group(1).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        items = data if isinstance(data, list) else [data]
        for it in items:
            if isinstance(it, dict):
                out.append(it)
    return out


def find_article(html: str) -> dict[str, Any]:
    """Return the first NewsArticle/Article JSON-LD block, else {}."""
    for it in _jsonld_blocks(html):
        if it.get("@type") in ("NewsArticle", "Article", "ReportageNewsArticle"):
            return it
    # Some sites wrap the article in an @graph.
    for it in _jsonld_blocks(html):
        graph = it.get("@graph")
        if isinstance(graph, list):
            for node in graph:
                if isinstance(node, dict) and node.get("@type") in (
                    "NewsArticle",
                    "Article",
                    "ReportageNewsArticle",
                ):
                    return node
    return {}


def meta(html: str, prop: str) -> str | None:
    m = re.search(
        rf'<meta[^>]*(?:property|name)=["\']{re.escape(prop)}["\'][^>]*content=["\']([^"\']*)["\']',
        html,
    )
    if not m:
        return None
    return unescape(m.group(1))


def _div_inner(html: str, start: int) -> str | None:
    """Return the inner HTML of the <div> that starts at `start`, depth-aware."""
    depth = 0
    pos = start
    inner_start: int | None = None
    for m in _TAG_RE.finditer(html, start):
        if m.group(1):  # closing tag
            depth -= 1
            if depth == 0:
                return html[inner_start:m.start()] if inner_start is not None else None
        else:
            if depth == 0:
                tag_end = html.find(">", m.end())
                inner_start = tag_end + 1 if tag_end >= 0 else None
            depth += 1
    return None


def _paragraphs_text(chunk: str) -> str:
    paras = re.findall(r"<p[^>]*>(.*?)</p>", chunk, re.DOTALL)
    text = " ".join(re.sub(r"<[^>]+>", " ", p).strip() for p in paras)
    if not text.strip():
        text = re.sub(r"<[^>]+>", " ", chunk)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def extract_body(html: str) -> str | None:
    best = ""
    for m in re.finditer(rf"<div[^>]*{_BODY_CLASSES}[^>]*>", html):
        inner = _div_inner(html, m.start())
        if not inner:
            continue
        text = _paragraphs_text(inner)
        if len(text) > len(best):
            best = text
        if len(best) > 800:
            break
    return best or None


def _author(jsonld: dict[str, Any], html: str) -> str | None:
    author = jsonld.get("author")
    if isinstance(author, list):
        author = author[0] if author else {}
    if isinstance(author, dict):
        author = author.get("name", "")
    return author or meta(html, "article:author") or meta(html, "author")


def _image(jsonld: dict[str, Any], html: str) -> str | None:
    image = jsonld.get("image")
    if isinstance(image, dict):
        return image.get("url")
    if isinstance(image, list) and image:
        first = image[0]
        return first.get("url") if isinstance(first, dict) else str(first)
    if isinstance(image, str):
        return image
    return meta(html, "og:image")


def parse_article(
    html: str,
    url: str,
    *,
    source: str | None = None,
    keyword: str | None = None,
) -> dict[str, Any]:
    """Turn an article page into one clean record.

    Raises ValueError when the page carries no usable article metadata.
    """
    jsonld = find_article(html)
    title = (jsonld.get("headline") or jsonld.get("name") or meta(html, "og:title") or "").strip()
    if not title:
        raise ValueError("no article metadata found")

    record: dict[str, Any] = {
        "source": source,
        "title": title,
        "author": _author(jsonld, html),
        "published_at": jsonld.get("datePublished") or meta(html, "article:published_time"),
        "modified_at": jsonld.get("dateModified") or meta(html, "article:modified_time"),
        "description": jsonld.get("description") or meta(html, "og:description"),
        "image": _image(jsonld, html),
        "content": jsonld.get("articleBody") or extract_body(html),
        "url": url,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }
    if keyword:
        record["matched_keyword"] = keyword
    return record


async def fetch_html(url: str, timeout: float = 25.0) -> str:
    """Fetch article HTML: plain httpx first, browser-TLS curl_cffi as fallback."""
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url)
        if resp.status_code < 400 and len(resp.text) > 2_000:
            return resp.text
    except httpx.HTTPError:
        pass

    def _via_curl_cffi() -> str:
        from curl_cffi import requests as crequests  # optional dependency

        r = crequests.get(
            url,
            impersonate="safari",
            timeout=timeout,
            headers={"Accept-Language": "id-ID,id;q=0.9"},
        )
        if r.status_code >= 400:
            raise ValueError(f"HTTP {r.status_code} with browser TLS")
        return r.text

    try:
        return await asyncio.to_thread(_via_curl_cffi)
    except Exception as exc:  # noqa: BLE001 - caller decides how to degrade
        raise ValueError(f"fetch failed: {exc}") from exc


async def scrape_article(
    url: str,
    *,
    source: str | None = None,
    keyword: str | None = None,
) -> dict[str, Any]:
    html = await fetch_html(url)
    return parse_article(html, url, source=source, keyword=keyword)
