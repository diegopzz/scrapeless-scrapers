# Rightmove — MCP surface

Scrape Rightmove property pages and location lookups conversationally from any MCP-capable AI agent or client. No code — the LLM drives a Scrapeless cloud browser through MCP
tools and you ask for the fields described in [`../../DATA_MODEL.md`](../../DATA_MODEL.md).

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

Once the server is connected, ask in plain language. Start with a property page:

```
Using the scrapeless tools, open https://www.rightmove.co.uk/properties/149360984
read window.PAGE_MODEL.propertyData, and return the Property fields from
../../DATA_MODEL.md (id, price, bedrooms, address, features, photos, agency, ...).
```

## 4. Scrape locations

The location lookup hits the `los.rightmove.co.uk/typeahead` JSON endpoint:

```
Open https://los.rightmove.co.uk/typeahead?query=cornwall&limit=10&exclude=STREET
with the scrapeless browser and return the matches as "<type>^<id>" strings.
```

## 5. Output shape

The MCP surface emits whatever shape you ask for. To stay aligned with the `cli/`, `nodejs/`, and
`python/` surfaces, ask for the `Property` and `LocationMatch` fields documented in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in [`results/`](results/).

## 6. Notes

- Tool arguments are camelCase (`sessionId`, `proxyCountry`); `browser_close` rejects snake_case.
- Rightmove is geo-locked — create the session with a `GB` proxy country.
- Modern property pages ship `PAGE_MODEL` Devalue-encoded (`{ data: "<stringified array>", encoding }`);
  the flat array must be revived before `propertyData` is reachable.
- For repeatable, schema-validated output, use the `cli/`, `nodejs/`, or `python/` surfaces — the
  MCP surface is best for ad-hoc, conversational scraping.
