# Glints Jobs MCP — Indonesian Job Search for AI Agents

An **MCP server** that gives AI agents (Claude, Cursor, Windsurf, …) access to
the Indonesian job market on Glints: search open roles by keyword and city, then
fetch any job with salary range, skills, experience and the full description.

## Tools

| Tool | Description |
|---|---|
| `search_jobs` | Find jobs by keyword + optional city (limit 1–50) |
| `get_job` | One job by URL: salary, skills, experience, full description |

## Connect

Streamable HTTP transport, authenticated with your Apify token:

```json
{
  "mcpServers": {
    "glints-jobs-mcp": {
      "url": "https://galih_rakasiwi--glints-jobs-mcp.apify.actor/mcp",
      "headers": {
        "Authorization": "Bearer <YOUR_APIFY_TOKEN>"
      }
    }
  }
}
```

Paste this into Claude Desktop's `claude_desktop_config.json`, or add the URL
`https://galih_rakasiwi--glints-jobs-mcp.apify.actor/mcp` in Cursor/Windsurf MCP
settings with the same bearer header.

## Example session

```
User: find data engineer jobs in Jakarta that pay more than 10 million
Agent (tool search_jobs): 10 roles — "Data Engineer, PT Sigma Global
  Teknologi, Jakarta Selatan, IDR 6–7.7M/month, skills: PostgreSQL, Linux".
```

## How the Cloudflare bypass works

1. `curl_cffi` with Chrome TLS impersonation fetches the page — works without a
   challenge in most cases.
2. If challenged, the call returns a clear error instead of hanging.
3. Search pages expose 30 jobs; the city filter is applied client-side.

## Notes

- Pay per completed tool call; failed calls are free.
- See [RE.md](RE.md) for the proven endpoint recipes.

## Related searches

glints mcp, mcp server lowongan kerja, indonesia jobs mcp, job search mcp,
ai hiring agent indonesia, glints scraper mcp
