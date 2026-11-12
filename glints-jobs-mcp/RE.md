# Reverse-engineering log — Glints (2026-11-12)

Probed from a datacenter IP with `curl_cffi` (Chrome TLS) and FlareSolverr.

## Endpoints

| Purpose | URL | Result |
|---|---|---|
| Search | `https://glints.com/id/opportunities/jobs/explore?keyword=data%20engineer&country=ID` | **200**, 30 jobs in `__NEXT_DATA__` |
| Job detail | `https://glints.com/id/opportunities/jobs/<anything>/<jobId>` | **200**, full job in `initialData.data` |

Both return without a Cloudflare interstitial when using Chrome TLS
impersonation. The `/<slug>/` segment is ignored — `/jobs/<jobId>` also works.

## Data locations

- Search: `props.pageProps.initialJobs.jobsInPage[]`
- Detail: `props.pageProps.initialData.data`
  - `descriptionJsonString` — Draft.js blocks; join `blocks[].text`
  - `company.descriptionJsonString`, `company.status` (`VERIFIED`), `salaries[]`,
    `skills[]`, `location.parents[]` (city/province levels)

## Query parameters

- `keyword` — works (URL-encoded)
- `country=ID` — required for Indonesian listings
- `locationName=Jakarta` — **ignored** by SSR (same 30 jobs); filter client-side
- `page=2` — returns 0 jobs; pagination is not URL-based in SSR

## Failure modes

- Direct fetch can still be challenged on some IP ranges → FlareSolverr fallback
  (embedded at `localhost:8191`).
- Per-URL errors are collected; one bad job never fails the batch.
