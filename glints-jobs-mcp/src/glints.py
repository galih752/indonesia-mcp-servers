"""Glints scraping + parsing.

Proven recipe (2026-11-12, datacenter IP):
  search  https://glints.com/id/opportunities/jobs/explore?keyword=<kw>&country=ID
          → __NEXT_DATA__.props.pageProps.initialJobs.jobsInPage (30 jobs)
  detail  https://glints.com/id/opportunities/jobs/<anything>/<jobId>
          → __NEXT_DATA__.props.pageProps.initialData.data (full job + description)

curl_cffi with Chrome impersonation returns 200 without Cloudflare
interstitial. FlareSolverr (embedded, localhost:8191) stays as a fallback for
IPs that do get challenged.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

_FLARESOLVERR = "http://localhost:8191/v1"
_BASE = "https://glints.com/id/opportunities/jobs"
_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
}
_CHALLENGE_MARKERS = ("Just a moment", "cf-challenge", "Checking your browser")

_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.DOTALL
)


def _via_curl_cffi(url: str, timeout: float) -> str:
    from curl_cffi import requests as crequests

    r = crequests.get(url, impersonate="chrome", timeout=timeout, headers=_HEADERS)
    if r.status_code >= 400:
        raise ValueError(f"HTTP {r.status_code}")
    return r.text


def _via_flaresolverr(url: str, timeout: float) -> str:
    import urllib.request

    req = urllib.request.Request(
        _FLARESOLVERR,
        data=json.dumps({"cmd": "request.get", "url": url, "maxTimeout": int(timeout * 1000)}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    data = json.loads(urllib.request.urlopen(req, timeout=timeout + 30).read())
    if data.get("status") != "ok":
        raise ValueError(f"FlareSolverr: {data.get('message', 'unknown')}")
    return data["solution"]["response"]


def _looks_blocked(html: str) -> bool:
    return any(marker in html for marker in _CHALLENGE_MARKERS) or "__NEXT_DATA__" not in html


async def fetch_page(url: str, timeout: float = 60) -> str:
    """Fetch a Glints page: browser TLS first, FlareSolverr when challenged."""
    try:
        html = await asyncio.to_thread(_via_curl_cffi, url, timeout)
        if not _looks_blocked(html):
            return html
        print("[glints] Cloudflare challenge detected — falling back to FlareSolverr", flush=True)
    except Exception as exc:  # noqa: BLE001 - try the browser solver next
        print(f"[glints] direct fetch failed ({exc}) — trying FlareSolverr", flush=True)

    try:
        return await asyncio.to_thread(_via_flaresolverr, url, timeout)
    except Exception as exc:  # noqa: BLE001 - caller degrades
        raise ValueError(f"Glints fetch failed: {exc}") from exc


def _next_data(html: str) -> dict[str, Any]:
    m = _NEXT_DATA_RE.search(html)
    if not m:
        raise ValueError("__NEXT_DATA__ not found (page blocked or layout changed)")
    return json.loads(m.group(1))


def _description(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        blocks = json.loads(raw).get("blocks") or []
    except (json.JSONDecodeError, AttributeError):
        return None
    text = "\n".join((b.get("text") or "").strip() for b in blocks if b.get("text"))
    return text or None


def _salary(job: dict[str, Any]) -> dict[str, Any]:
    salaries = job.get("salaries") or []
    if not salaries:
        return {"salaryMin": None, "salaryMax": None, "salaryCurrency": None, "salaryPeriod": None}
    first = salaries[0]
    return {
        "salaryMin": first.get("minAmount"),
        "salaryMax": first.get("maxAmount"),
        "salaryCurrency": first.get("CurrencyCode"),
        "salaryPeriod": (first.get("salaryMode") or "").lower() or None,
    }


def _location_names(job: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for key in ("city", "citySubDivision"):
        name = (job.get(key) or {}).get("name")
        if name:
            names.append(name)
    loc = job.get("location") or {}
    if loc.get("formattedName"):
        names.append(loc["formattedName"])
    for parent in loc.get("parents") or []:
        name = parent.get("formattedName") or parent.get("name")
        if name:
            names.append(name)
    return list(dict.fromkeys(names))


def _city(job: dict[str, Any]) -> str | None:
    name = (job.get("city") or {}).get("name")
    if name:
        return name
    for parent in (job.get("location") or {}).get("parents") or []:
        if parent.get("administrativeLevelName") == "City":
            return parent.get("formattedName") or parent.get("name")
    return None


def job_url(job_id: str) -> str:
    return f"{_BASE}/{job_id}"


def normalize(job: dict[str, Any]) -> dict[str, Any]:
    """Normalize a list-page or detail-page Glints job into one flat record."""
    company = job.get("company") or {}
    skills = []
    for item in job.get("skills") or job.get("JobSkills") or []:
        name = (item.get("skill") or {}).get("name")
        if name:
            skills.append(name)
    category = (job.get("hierarchicalJobCategory") or {}).get("name")
    record: dict[str, Any] = {
        "id": job.get("id"),
        "title": job.get("title"),
        "company": company.get("name") or company.get("displayName"),
        "companyVerified": company.get("status") == "VERIFIED",
        "companyIndustry": (company.get("industry") or {}).get("name"),
        "city": _city(job),
        "location": _location_names(job)[:1][0] if _location_names(job) else None,
        "allLocations": _location_names(job),
        "workArrangement": job.get("workArrangementOption"),
        "employmentType": job.get("type"),
        "educationLevel": job.get("educationLevel"),
        "minYearsExperience": job.get("minYearsOfExperience"),
        "maxYearsExperience": job.get("maxYearsOfExperience"),
        "skills": skills,
        "category": category,
        "isHot": job.get("isHot"),
        "status": job.get("status"),
        "createdAt": job.get("createdAt"),
        "updatedAt": job.get("updatedAt"),
        "url": job_url(str(job.get("id") or "")),
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }
    record.update(_salary(job))
    return record


def parse_search(html: str, location: str | None = None) -> list[dict[str, Any]]:
    data = _next_data(html)
    jobs = (
        data.get("props", {})
        .get("pageProps", {})
        .get("initialJobs", {})
        .get("jobsInPage", [])
    )
    records = [normalize(j) for j in jobs if j.get("id") and j.get("title")]
    if location:
        needle = location.lower()
        records = [
            r for r in records if any(needle in (name or "").lower() for name in r["allLocations"])
        ]
    return records


def parse_job(html: str) -> dict[str, Any]:
    data = _next_data(html)
    job = (data.get("props", {}).get("pageProps", {}).get("initialData", {}) or {}).get("data") or {}
    if not job.get("id"):
        raise ValueError("job not found on page")
    record = normalize(job)
    record["description"] = _description(job.get("descriptionJsonString"))
    record["companyDescription"] = _description((job.get("company") or {}).get("descriptionJsonString"))
    record["externalApplyUrl"] = job.get("externalApplyURL")
    record["expiresAt"] = job.get("expiryDate")
    return record


def is_search_url(url: str) -> bool:
    return "/explore" in url or "keyword=" in url


async def search_jobs(
    keyword: str,
    limit: int = 10,
    location: str | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    url = f"{_BASE}/explore?keyword={quote(keyword)}&country=ID"
    try:
        html = await fetch_page(url)
    except ValueError as exc:
        return [], [str(exc)]
    try:
        records = parse_search(html, location=location)
    except (ValueError, json.JSONDecodeError) as exc:
        return [], [str(exc)]
    return records[: max(1, min(limit, 50))], []


async def scrape_urls(urls: list[str], limit: int = 20) -> tuple[list[dict[str, Any]], list[str]]:
    items: list[dict[str, Any]] = []
    errors: list[str] = []
    for url in urls[: max(1, min(limit, 20))]:
        try:
            html = await fetch_page(url)
            if is_search_url(url):
                items.extend(parse_search(html))
            else:
                items.append(parse_job(html))
        except Exception as exc:  # noqa: BLE001 - partial success is the contract
            errors.append(f"{url}: {exc}")
            print(f"[batch] skip {url}: {exc}", flush=True)
    return items, errors


__all__ = [
    "fetch_page",
    "is_search_url",
    "normalize",
    "parse_job",
    "parse_search",
    "search_jobs",
    "scrape_urls",
]
