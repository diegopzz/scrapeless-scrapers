# Google Maps — MCP surface

Scrape Google Maps place lists and place detail pages conversationally from any MCP-capable AI
agent or client using the [Scrapeless MCP server](https://github.com/scrapeless-ai/scrapeless-mcp-server).
No code — the LLM drives a Scrapeless cloud browser through MCP tools and you ask for the fields
described in [`../../DATA_MODEL.md`](../../DATA_MODEL.md).

## 1. Install the scrapeless-mcp-server

Add the config from [`mcp.json`](mcp.json) to your MCP client:

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

## 2. Set your API key

Use the key from [app.scrapeless.com](https://app.scrapeless.com) as `SCRAPELESS_KEY`.

## 3. Scrape a place list

Google Maps loads client-side. Navigate via `window.location.href` (not the `open` tool directly)
to avoid the load-event timeout. Then ask for the place cards:

```
Using the scrapeless tools, create a browser session with proxyCountry US.
Navigate to https://www.google.com/maps/search/coffee+shops+in+Austin+TX by evaluating
window.location.href = '<url>' in the page, then wait 10000ms for the page to settle.
Extract the first 5 place cards from [role='feed'] [role='article'] elements. For each card,
read the innerText to get: name (from a.hfpxzc aria-label), category, address, rating, and
description. Return a JSON array of Place objects matching DATA_MODEL.md.
```

## 4. Scrape a place detail page

```
Using the scrapeless tools, create a browser session with proxyCountry US.
Navigate to https://www.google.com/maps/place/Epoch+Coffee/@30.3186037,-97.7296551,15z/data=!4m6!3m5!1s0x8644ca6bc309e81b:0x1f1a903bbb66839!8m2!3d30.3186037!4d-97.7245402!16s%2Fg%2F1v76_180
by evaluating window.location.href = '<url>', then wait 10000ms.
Extract the Place fields: name from h1, address from aria-label starting with "Address: ",
phone from aria-label starting with "Phone: ", website from aria-label starting with "Website: ",
rating from div.F7nice text, category from button.DkEaL text. Return a single Place object.
```

## 5. Output shape

The MCP surface emits whatever shape you ask for. To stay aligned with the other surfaces, ask for
the `Place` fields documented in [`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are
in [`results/`](results/).

## 6. Notes

- Tool arguments are camelCase (`sessionId`, `proxyCountry`); `browser_close` rejects snake_case.
- Google Maps blocks the CLI `open` command's `load`-event wait — always navigate via eval.
- The `window.APP_INITIALIZATION_STATE` blob is present but extremely large (250KB+); prefer the
  DOM-based extraction described above.
- For repeatable, schema-validated output, use the `cli/`, `nodejs/`, or `python/` surfaces.
