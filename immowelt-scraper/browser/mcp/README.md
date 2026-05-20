# Immowelt — MCP surface

Scrape Immowelt property (expose) pages conversationally from any MCP-capable AI agent or client using the
[Scrapeless MCP server](https://github.com/scrapeless-ai/scrapeless-mcp-server). No code — the LLM
drives a Scrapeless cloud browser through MCP tools and you ask for the fields described in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md).

Immowelt.de is a German real estate portal that boots from embedded Next.js / UFRN state. Tell the
model to read the `__UFRN_LIFECYCLE_SERVERREQUEST__` payload from a `<script>` tag rather than
scraping the rendered DOM. Use a German proxy so listings resolve.

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

## 3. Scrape a property listing

Once the server is connected, ask in plain language:

```
Using the scrapeless tools with a DE proxy, open https://www.immowelt.de/expose/k2ag632, wait for
the page body, then read the script tag containing __UFRN_LIFECYCLE_SERVERREQUEST__, JSON.parse its
embedded payload, find the listing object (the node that has both "sections" and "id"), and return
just { sections, id, brand, tags, contactSections } — the PropertyResult from ../../DATA_MODEL.md.
```

## 4. Output shape

The MCP surface emits whatever shape you ask for. To stay aligned with the `cli/`, `nodejs/`, and
`python/` surfaces, ask for the `PropertyResult` fields documented in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md) — `sections`, `id`, `brand`, `tags`, `contactSections`.
A live-captured sample is in [`results/properties.json`](results/properties.json).

> The `nodejs/` `scrape_search` surface is **not** exposed conversationally here. Immowelt
> LZ-String + Base64 encodes the `classified-serp-init-data` search blob; decoding it reliably needs
> the bundled `lz-string` dependency, not a one-shot in-page read. Use the `nodejs/` or `python/`
> surface for search/listing crawls.

## 5. Notes

- Tool arguments are camelCase (`sessionId`, `proxyCountry`); `browser_close` rejects snake_case.
- Set `proxyCountry: "DE"` at session creation — Immowelt geo-gates listings, and a non-DE egress
  often returns an interstitial instead of the expose page.
- For repeatable, schema-validated output, use the `cli/`, `nodejs/`, or `python/` surfaces — the
  MCP surface is best for ad-hoc, conversational scraping.
