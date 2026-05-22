# Google Jobs — MCP surface

Scrape Google Jobs listings conversationally from any MCP-capable AI agent using the
[Scrapeless MCP server](https://github.com/scrapeless-ai/scrapeless-mcp-server).

## 1. Install

```jsonc
{
  "mcpServers": {
    "scrapeless": {
      "command": "npx",
      "args": ["-y", "scrapeless-mcp-server"],
      "env": { "SCRAPELESS_KEY": "sk_..." }
    }
  }
}
```

## 2. Scrape jobs

```
Using the scrapeless tools, open
https://www.google.com/search?q=software+engineer+jobs+austin+tx&gl=us&hl=en
and wait for networkidle (or wait 8000ms). Then extract the Google Jobs panel —
parse from the "Job postings" heading, reading each card's: title (first line),
company (second line), location and source (the line containing " • via "),
posted_at (time-ago pattern), salary, and job_type. Return a JSON array of
JobListing objects as described in DATA_MODEL.md.
```

## 3. Output shape

`data.result` is an array of `JobListing` objects. Full field tables are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in [`results/`](results/).
