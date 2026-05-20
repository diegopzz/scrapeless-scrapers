# Glassdoor — MCP surface

Scrape Glassdoor jobs and salaries pages conversationally from any MCP-capable AI agent or client — no code. The [Scrapeless MCP server](https://github.com/scrapeless-ai/scrapeless-mcp-server)
drives a Scrapeless cloud browser through MCP tools and you ask for the fields described in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md).

## 1. Install the scrapeless-mcp-server

Install the [`scrapeless-mcp-server`](https://github.com/scrapeless-ai/scrapeless-mcp-server) and add it from [`mcp.json`](mcp.json) to your MCP client:

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

Any MCP-capable AI agent or client works. Add the block above wherever your client stores its MCP servers. Two transports are available:

- **stdio** (shown above) — the client launches `npx -y scrapeless-mcp-server`.
- **HTTP** — agents that connect to a remote MCP URL can point at `https://api.scrapeless.com/mcp` with the header `x-api-token: sk_...`.

## 2. Set your API key

Use the key from [app.scrapeless.com](https://app.scrapeless.com) as `SCRAPELESS_KEY` in the config
above. Sign up there if you do not have one yet — new accounts include free Scraping Browser
runtime.

## 3. Scrape a jobs page

Once the server is connected, ask in plain language. Start with a jobs page:

```
Using the scrapeless tools, open https://www.glassdoor.com/Jobs/eBay-Jobs-E7853.htm
and return each job card as { jobTitle, jobLink, job_location, jobSalary, jobDate }.
```

## 4. Scrape a salaries page

```
Open https://www.glassdoor.com/Salary/eBay-Salaries-E7853.htm with the scrapeless
browser and extract the Salary fields from ../../DATA_MODEL.md (results,
numPages, salaryCount, jobTitleCount).
```

## 5. Output shape

The MCP surface emits whatever shape you ask for. To stay aligned with the `cli/`, `nodejs/`, and
`python/` surfaces, ask for the `Job` and `Salary` fields documented in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in [`results/`](results/).

## 6. Notes

- Tool arguments are camelCase (`sessionId`, `proxyCountry`); `browser_close` rejects snake_case.
- Per-call `proxyCountry` may be ignored — set the country at session creation if you need
  region-specific listings.
- For repeatable, schema-validated output, use the `cli/`, `nodejs/`, or `python/` surfaces — the
  MCP surface is best for ad-hoc, conversational scraping.
