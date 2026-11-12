# Indonesian News MCP — News Tools for AI Agents

An **MCP server** that gives AI agents (Claude, Cursor, Windsurf, …) Indonesian
news superpowers: the newest national headlines with full article text, keyword
search across headlines, and any article by URL from CNN Indonesia, Antara,
Detik, Kompas and Tempo.

## Tools

| Tool | Description |
|---|---|
| `latest_news` | Newest national headlines with full article text (limit 1–20) |
| `search_headlines` | Match a keyword across the newest headlines (fast, no bodies) |
| `get_article` | One article by URL: title, author, date, description, full text |

## Connect

Streamable HTTP transport, authenticated with your Apify token:

```json
{
  "mcpServers": {
    "indonesian-news-mcp": {
      "url": "https://galih_rakasiwi--indonesian-news-mcp.apify.actor/mcp",
      "headers": {
        "Authorization": "Bearer <YOUR_APIFY_TOKEN>"
      }
    }
  }
}
```

Paste this into Claude Desktop's `claude_desktop_config.json`, or add the URL
`https://galih_rakasiwi--indonesian-news-mcp.apify.actor/mcp` in Cursor/Windsurf
MCP settings with the same bearer header.

## Example session

```
User: what's happening in Indonesian politics today?
Agent (tool latest_news): "MPR Rapat Gabungan Bahas Jadwal Paripurna Wapres
  Pengganti Gibran Esok" — cnnindonesia, 2026-11-12 — full text attached.
```

## Sources

- RSS: CNN Indonesia and Antara (verified from Apify datacenter IPs).
- Tempo RSS is available but its article pages may require a residential proxy.
- By URL: any Indonesian site with `NewsArticle` JSON-LD.

## Notes

- Pay per completed tool call; failed calls are free.
- One dead feed never fails the call — the rest of the results still return.
- See [RE.md](RE.md) for the proven endpoint recipes.

## Related searches

indonesian news mcp, mcp server berita indonesia, news mcp server,
ai news agent indonesia, cnn indonesia mcp, antara mcp, detik mcp
