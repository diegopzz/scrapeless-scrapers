# YouTube — MCP surface

Scrape YouTube watch pages conversationally from any MCP-capable AI agent or client — no code. The LLM drives a Scrapeless cloud browser through MCP tools and you ask for
the fields described in [`../../DATA_MODEL.md`](../../DATA_MODEL.md).

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

## 3. Scrape a video page

Once the server is connected, ask in plain language:

```
Using the scrapeless tools, open https://www.youtube.com/watch?v=1Y-XvvWlyzk and
return the Video wrapper from ../../DATA_MODEL.md ({ video, channel,
commentContinuationToken }) parsed from the embedded ytInitialPlayerResponse and
ytInitialData JSON.
```

## 4. Output shape

The MCP surface emits whatever shape you ask for. To stay aligned with the `cli/`, `nodejs/`, and
`python/` surfaces, ask for the `Video` wrapper fields documented in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in [`results/`](results/).

## 5. Notes

- Tool arguments are camelCase (`sessionId`, `proxyCountry`); `browser_close` rejects snake_case.
- The watch page embeds everything in two `<script>` blobs — `ytInitialPlayerResponse`
  (videoDetails) and `ytInitialData` (render tree). Ask the model to grab and parse those rather
  than scraping rendered DOM.
- Comments, channel videos, and search come from YouTube's internal `youtubei/v1` endpoints — ask
  the model to `POST` from inside the page, or just use the `nodejs/` / `python/` surface.
- For repeatable, schema-validated output, use the `cli/`, `nodejs/`, or `python/` surfaces — the
  MCP surface is best for ad-hoc, conversational scraping.
