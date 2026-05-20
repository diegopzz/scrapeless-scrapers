# ImmobilienScout24 (DE) — MCP surface

Scrape ImmobilienScout24 property (expose) pages conversationally from any MCP-capable AI agent or client using the [Scrapeless MCP server](https://github.com/scrapeless-ai/scrapeless-mcp-server).
No code — the LLM drives a Scrapeless cloud browser through MCP tools and you ask for the fields
described in [`../../DATA_MODEL.md`](../../DATA_MODEL.md).

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

## 3. Scrape a property page

Once the server is connected, ask in plain language. ImmobilienScout24 has one page type — the
property expose page:

```
Using the scrapeless tools, open https://www.immobilienscout24.de/expose/160519246
and return the PropertyResult fields from ../../DATA_MODEL.md (id, title,
description, address, propertyLlink, propertySepcs, price, building,
attachments, agencyName, agencyAddress). Keep the upstream typo'd keys verbatim:
propertyLlink, propertySepcs, priceWithoutHeadting, finalEnergyRrequirement.
```

To crawl a search page, ask the model to first collect the `/expose/<id>` links from a results page
(e.g. `https://www.immobilienscout24.de/Suche/de/bayern/muenchen/wohnung-mieten`), then open each
expose URL and return the same `PropertyResult` shape.

## 4. Output shape

The MCP surface emits whatever shape you ask for. To stay aligned with the `cli/`, `nodejs/`, and
`python/` surfaces, ask for the `PropertyResult` fields documented in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). A sample payload is in [`results/`](results/).

## 5. Notes

- Tool arguments are camelCase (`sessionId`, `proxyCountry`); `browser_close` rejects snake_case.
- ImmobilienScout24 is a German portal — set `proxyCountry` to `DE` at session creation so the page
  renders in German and serves the `is24qa-*` spec classes the field tables rely on. Per-call
  `proxyCountry` may be ignored.
- The expose page is the source of truth for both `scrape_properties` and `scrape_search`; the
  search variant just discovers expose URLs first.
- For repeatable, schema-validated output, use the `cli/`, `nodejs/`, or `python/` surfaces — the
  MCP surface is best for ad-hoc, conversational scraping.
