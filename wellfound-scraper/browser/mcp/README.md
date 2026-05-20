# Wellfound — MCP surface

Scrape Wellfound (formerly AngelList) search and company-profile pages conversationally from any MCP
client using the
[Scrapeless MCP server](https://github.com/scrapeless-ai/scrapeless-mcp-server). No code — the LLM
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

## 3. Scrape a company profile

Once the server is connected, ask in plain language. Wellfound hydrates company data into
`<script id="__NEXT_DATA__">`, so ask the model to read the `apolloState` graph:

```
Using the scrapeless tools, open https://wellfound.com/company/openai and return the
CompanyData fields from ../../DATA_MODEL.md (id, name, slug, badges, companySize,
highConcept, logoUrl, highlightedJobListings).
```

## 4. Scrape a search page

Use a `/role/l/<role>/<city>` URL — the bare `/role/<role>` path returns an empty interstitial:

```
Using the scrapeless tools, open https://wellfound.com/role/l/engineer/san-francisco and
return each result company as { id, name, slug, companySize, highConcept, logoUrl,
badges, highlightedJobListings }.
```

## 5. Job listings

Each company's `highlightedJobListings` follows the `JobData` table — keep the upstream field names
verbatim, including the `remtoe` typo:

```
From https://wellfound.com/company/openai, return each highlighted job listing as
{ id, title, slug, remtoe, primaryRoleTitle, locationNames, liveStartAt, jobType,
description }.
```

## 6. Output shape

The MCP surface emits whatever shape you ask for. To stay aligned with the `cli/`, `nodejs/`, and
`python/` surfaces, ask for the `CompanyData` and `JobData` fields documented in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in [`results/`](results/).

## 7. Notes

- Tool arguments are camelCase (`sessionId`, `proxyCountry`); `browser_close` rejects snake_case.
- Set `proxyCountry` to `US` at session creation — Wellfound serves the fully-rendered Apollo state
  most reliably from US egress.
- The upstream `remtoe` misspelling (for `remote`) is preserved verbatim from Wellfound's own Apollo
  graph; do not "correct" it if you want output that matches the other surfaces.
- For repeatable, schema-validated output, use the `cli/`, `nodejs/`, or `python/` surfaces — the
  MCP surface is best for ad-hoc, conversational scraping.
