# Reverse-engineering log — Indonesian news (2026-11-12)

All probes run from this machine (datacenter IP) with `curl` / `curl_cffi`.

## RSS feeds

| Source | URL | Result |
|---|---|---|
| Tempo | `https://rss.tempo.co/nasional` | **200**, 50 items |
| CNN Indonesia | `https://www.cnnindonesia.com/nasional/rss` | **200**, 100 items |
| Antara | `https://www.antaranews.com/rss/terkini.xml` | **200**, 50 items |
| Detik | `https://rss.detik.com/index.php/detikcom` | timeout / blocked |
| Kompas | `https://www.kompas.com/rss`, `https://indeks.kompas.com/rss` | **404** (dead) |

Detik and Kompas article pages still work by URL, so they remain supported in
`single`/`batch` mode. Their RSS is not used.

## Article extraction

- CNN Indonesia and Antara: plain `httpx` + browser UA returns 200 with
  `NewsArticle` JSON-LD.
- **Tempo: plain httpx = 403** regardless of UA; `curl_cffi` with
  `impersonate="safari"` = **200** with full JSON-LD. Implemented as fallback.
- Body text: Antara uses `div.wrap__article-detail-content.post-content` with
  no `articleBody`; CNN uses `div.detail-text` (nested divs require depth-aware
  slicing). Both handled by `src/extract.py`.

## Sample verified records (2026-11-12)

- tempo: "KKP Bangun 506 Dapur Perebusan…" — content 4078 chars
- cnnindonesia: "Gibran Resmi Mundur…" — content 3204 chars
- antaranews: "Bappenas petakan isu strategis…" — content 1964 chars

## Failure modes

- One dead feed or one blocked article never fails the run: skipped with a log
  warning, the remaining articles are still returned.
- Rate limits: none observed at 20 articles/run; keep the cap.
