# Booking.com — MCP surface

Scrape Booking.com search results, hotel detail pages, and reviews conversationally from any MCP
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

Booking.com is aggressive about anti-bot, so ask the LLM to open the session with a residential
proxy country that matches the locale on the URL (Booking blocks mismatched proxy regions). The
sample URLs below use the `en-gb` locale, so `GB` is a safe default.

## 3. Scrape a hotel page

Once the server is connected, ask in plain language. Start with a hotel detail page:

```
Using the scrapeless tools (open the session with proxyCountry GB), open
https://www.booking.com/hotel/gb/gardencourthotel.en-gb.html and return the
Hotel fields from ../../DATA_MODEL.md (url, id, title, description, address,
images, lat, lng, features, price).
```

`price` is the 61-day availability calendar — ask the LLM to read it from the page's
`AvailabilityCalendar` GraphQL response if you need each night's `{ checkin, minLengthOfStay,
avgPriceFormatted, available }`.

## 4. Scrape a search-results page

```
Using the scrapeless tools, open
https://www.booking.com/searchresults.en-gb.html?ss=Malta&dest_id=3939&dest_type=region&group_adults=1&no_rooms=1&group_children=0&lang=en-gb
(proxyCountry MT) and return each property card as { displayName.text,
basicPropertyData.pageName, basicPropertyData.location.address,
basicPropertyData.reviewScore.score, basicPropertyData.reviewScore.reviewCount,
basicPropertyData.starRating.value, location.mainDistance,
priceDisplayInfoIrene.displayPrice.amountPerStay.amount,
policies.showFreeCancellation }.
```

## 5. Scrape reviews

The reviews load behind the "Read all reviews" button on the hotel page:

```
Open https://www.booking.com/hotel/gb/gardencourthotel.en-gb.html with the
scrapeless browser, click "Read all reviews", and return each review card as
{ guestName, reviewScore, reviewTitle, textDetails.positiveText,
textDetails.negativeText, stayDate, createdDateTime, countryCode }.
```

## 6. Output shape

The MCP surface emits whatever shape you ask for. To stay aligned with the `cli/`, `nodejs/`, and
`python/` surfaces, ask for the `Location`, `SearchResult`, `Hotel`, `PriceData`, and `Review`
fields documented in [`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in
[`results/`](results/).

## 7. Notes

- Tool arguments are camelCase (`sessionId`, `proxyCountry`); `browser_close` rejects snake_case.
- For repeatable, schema-validated output, use the `cli/`, `nodejs/`, or `python/` surfaces — the
  MCP surface is best for ad-hoc, conversational scraping. The `cli/` surface covers `search` and
  `hotel`; the `price[]` calendar and `reviews` are MCP/`nodejs`-only, and location suggestions
  are `nodejs`/`python`-only.
