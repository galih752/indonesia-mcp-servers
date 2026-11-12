# Indonesia MCP servers

Two hosted [Model Context Protocol](https://modelcontextprotocol.io) servers that
give AI agents live access to Indonesian news and the Indonesian job market.
Both run on Apify standby — connect to a URL, nothing to install.

| Server | What you get | Endpoint |
|---|---|---|
| [Indonesian News](#indonesian-news) | Newest national headlines with full article text, keyword search, article by URL | `https://galih-rakasiwi--indonesian-news-mcp.apify.actor/mcp` |
| [Glints Jobs](#glints-jobs) | Glints roles by keyword and city: salary, skills, experience, full job by URL | `https://galih-rakasiwi--glints-jobs-mcp.apify.actor/mcp` |

Both use **Streamable HTTP** and authenticate with an Apify API token
(`Authorization: Bearer <APIFY_TOKEN>`). Get a free token at
<https://console.apify.com/settings/integrations>. Billing is pay-per-completed
tool call ($0.002 news / $0.003 jobs on the FREE tier); failed calls are free.

## One URL, five tools (Apify MCP gateway)

If you already use the [Apify MCP server](https://mcp.apify.com), you can load
five Indonesian data tools in one connection — no separate server install:

```
https://mcp.apify.com/?tools=galih_rakasiwi/indonesian-news-by-url,galih_rakasiwi/glints-jobs-by-url,galih_rakasiwi/traveloka-hotels-scraper,galih_rakasiwi/sports-scores-api,galih_rakasiwi/medium-api
```

```bash
claude mcp add --transport http indonesia-data \
  "https://mcp.apify.com/?tools=galih_rakasiwi/indonesian-news-by-url,galih_rakasiwi/glints-jobs-by-url,galih_rakasiwi/traveloka-hotels-scraper,galih_rakasiwi/sports-scores-api,galih_rakasiwi/medium-api" \
  --header "Authorization: Bearer $APIFY_TOKEN"
```

The agent then sees each actor as a tool (`galih_rakasiwi--indonesian-news-by-url`,
…). This is the fastest path for Claude/Cursor users who already have an Apify
token.

## Connect

### Claude Code

```bash
claude mcp add --transport http indonesian-news \
  https://galih-rakasiwi--indonesian-news-mcp.apify.actor/mcp \
  --header "Authorization: Bearer $APIFY_TOKEN"

claude mcp add --transport http glints-jobs \
  https://galih-rakasiwi--glints-jobs-mcp.apify.actor/mcp \
  --header "Authorization: Bearer $APIFY_TOKEN"
```

### mcp.json (Cursor, VS Code, Claude Desktop-style clients)

```json
{
  "mcpServers": {
    "indonesian-news": {
      "url": "https://galih-rakasiwi--indonesian-news-mcp.apify.actor/mcp",
      "headers": { "Authorization": "Bearer <YOUR_APIFY_TOKEN>" }
    },
    "glints-jobs": {
      "url": "https://galih-rakasiwi--glints-jobs-mcp.apify.actor/mcp",
      "headers": { "Authorization": "Bearer <YOUR_APIFY_TOKEN>" }
    }
  }
}
```

---

## Indonesian News

Newest Indonesian headlines with the full article body, keyword search across
the newest headlines, and any article by URL as clean JSON.

**Tools**

| Tool | Description |
|---|---|
| `latest_news(limit, keyword, sources)` | Newest national headlines with full article text (limit 1–20) |
| `search_headlines(keyword, limit, sources)` | Fast headline-only keyword match |
| `get_article(url)` | One article by URL: title, author, date, description, full text |

Sources: CNN Indonesia and Antara RSS, verified from Apify datacenter IPs.
Tempo RSS works, but Tempo article pages may require a residential proxy.
By URL: any Indonesian site with `NewsArticle` JSON-LD.

Example prompt: *"Summarise the top Indonesian headlines right now."*

Server code: [`indonesian-news-mcp/`](indonesian-news-mcp)
Apify Store: https://apify.com/galih_rakasiwi/indonesian-news-mcp

## Glints Jobs

Search Glints roles by keyword with an optional city filter, then fetch any job
with salary range, skills, experience, company details and the full description.

**Tools**

| Tool | Description |
|---|---|
| `search_jobs(keyword, location, limit)` | Find jobs by keyword + optional city (limit 1–50) |
| `get_job(url)` | One job by URL: salary, skills, experience, full description |

Cloudflare is handled in-container with TLS impersonation; if a challenge cannot
be solved the call returns a clear error instead of hanging.

Example prompt: *"Find data engineer jobs in Jakarta and compare their salary ranges."*

Server code: [`glints-jobs-mcp/`](glints-jobs-mcp)
Apify Store: https://apify.com/galih_rakasiwi/glints-jobs-mcp

---

## Run locally (optional)

Each server is a FastMCP app served with uvicorn:

```bash
cd indonesian-news-mcp
pip install -r requirements.txt
APIFY_CONTAINER_PORT=8000 python -m src.main     # MCP at http://localhost:8000/mcp
```

Set `APIFY_TOKEN` and `APIFY_ACTOR_RUN_ID` to enable per-call charging when
running inside an Apify actor; locally you can omit both.

## Disclaimer

These are unofficial integrations. Indonesian News reads publicly available RSS
and article pages. Glints Jobs reads publicly available job listings. Names and
trademarks belong to their respective owners. Respect the source sites' terms and
rate limits.

## License

MIT — see [LICENSE](LICENSE).
