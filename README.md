# Scrapeless Scrapers

Production-grade example scrapers built on the official [Scrapeless](https://www.scrapeless.com/) SDKs. Every browser-rendered site drives a cloud session through Scrapeless's [Scraping Browser](https://www.scrapeless.com/en/scraping-browser) over CDP WebSocket; every SERP-style site uses [Deep SerpApi](https://www.scrapeless.com/en/deep-serp-api).

Every site ships two parallel implementations so you can adopt whichever language fits your stack:

- **Python** — official [`scrapeless`](https://pypi.org/project/scrapeless/) SDK. Browser sites drive a cloud session with Playwright over CDP; SERP sites use `client.deepserp.scrape()`.
- **Node.js** — official [`@scrapeless-ai/sdk`](https://www.npmjs.com/package/@scrapeless-ai/sdk). Browser sites drive a cloud session with `puppeteer-core` over CDP; SERP sites use `client.deepserp.scrape()`.

Every example runs end-to-end against the live Scrapeless API and emits schema-valid JSON into `results/`. CI re-runs the suites every 12 hours so the shipped fixtures stay current.

## Install

1. **Sign up:** create a free account at [app.scrapeless.com](https://app.scrapeless.com/passport/register?utm_source=github&utm_medium=partnership&utm_campaign=scrapeless_scrapers). New accounts include free Scraping Browser runtime.
2. **Set your API key** in the environment (or in a local `.env`, see `.env.example`):
   ```bash
   export SCRAPELESS_API_KEY=sk_...     # what the official SDKs read
   # or, accepted as an alias by every example in this repo:
   export SCRAPELESS_KEY=sk_...
   ```
   **Never commit the key.** Use repository secrets in CI.

## Supported sites

| Site | Folder | Surfaces |
| --- | --- | --- |
| 1688 | [1688-scraper](1688-scraper/) | [py](1688-scraper/browser/python/) · [node](1688-scraper/browser/nodejs/) |
| Adidas | [adidas-scraper](adidas-scraper/) | [py](adidas-scraper/browser/python/) · [node](adidas-scraper/browser/nodejs/) · [cli](adidas-scraper/browser/cli/) · [mcp](adidas-scraper/browser/mcp/) |
| Alibaba | [alibaba-scraper](alibaba-scraper/) | [py](alibaba-scraper/browser/python/) · [node](alibaba-scraper/browser/nodejs/) |
| AliExpress | [aliexpress-scraper](aliexpress-scraper/) | [py](aliexpress-scraper/browser/python/) · [node](aliexpress-scraper/browser/nodejs/) · [cli](aliexpress-scraper/browser/cli/) · [mcp](aliexpress-scraper/browser/mcp/) |
| Allegro | [allegro-scraper](allegro-scraper/) | [py](allegro-scraper/browser/python/) · [node](allegro-scraper/browser/nodejs/) · [cli](allegro-scraper/browser/cli/) |
| Amazon | [amazon-scraper](amazon-scraper/) | [py](amazon-scraper/browser/python/) · [node](amazon-scraper/browser/nodejs/) · [cli](amazon-scraper/browser/cli/) · [mcp](amazon-scraper/browser/mcp/) |
| Big Lots | [biglots-scraper](biglots-scraper/) | [py](biglots-scraper/browser/python/) · [node](biglots-scraper/browser/nodejs/) · [cli](biglots-scraper/browser/cli/) · [mcp](biglots-scraper/browser/mcp/) |
| Bing | [bing-scraper](bing-scraper/) | [py](bing-scraper/browser/python/) · [node](bing-scraper/browser/nodejs/) · [cli](bing-scraper/browser/cli/) · [mcp](bing-scraper/browser/mcp/) |
| Booking.com | [bookingcom-scraper](bookingcom-scraper/) | [py](bookingcom-scraper/browser/python/) · [node](bookingcom-scraper/browser/nodejs/) · [cli](bookingcom-scraper/browser/cli/) · [mcp](bookingcom-scraper/browser/mcp/) |
| Bunnings | [bunnings-scraper](bunnings-scraper/) | [py](bunnings-scraper/browser/python/) · [node](bunnings-scraper/browser/nodejs/) |
| ChatGPT | [chatgpt-scraper](chatgpt-scraper/) | [py](chatgpt-scraper/browser/python/) · [node](chatgpt-scraper/browser/nodejs/) |
| Craigslist | [craigslist-scraper](craigslist-scraper/) | [py](craigslist-scraper/browser/python/) · [node](craigslist-scraper/browser/nodejs/) · [cli](craigslist-scraper/browser/cli/) · [mcp](craigslist-scraper/browser/mcp/) |
| Crunchbase | [crunchbase-scraper](crunchbase-scraper/) | [py](crunchbase-scraper/browser/python/) · [node](crunchbase-scraper/browser/nodejs/) |
| Depop | [depop-scraper](depop-scraper/) | [py](depop-scraper/browser/python/) · [node](depop-scraper/browser/nodejs/) · [cli](depop-scraper/browser/cli/) · [mcp](depop-scraper/browser/mcp/) |
| DigiKey | [digikey-scraper](digikey-scraper/) | [py](digikey-scraper/browser/python/) · [node](digikey-scraper/browser/nodejs/) |
| Domain.com.au | [domaincom-scraper](domaincom-scraper/) | [py](domaincom-scraper/browser/python/) · [node](domaincom-scraper/browser/nodejs/) |
| eBay | [ebay-scraper](ebay-scraper/) | [py](ebay-scraper/browser/python/) · [node](ebay-scraper/browser/nodejs/) · [cli](ebay-scraper/browser/cli/) |
| Etsy | [etsy-scraper](etsy-scraper/) | [py](etsy-scraper/browser/python/) · [node](etsy-scraper/browser/nodejs/) |
| Expedia | [expedia-scraper](expedia-scraper/) | [py](expedia-scraper/browser/python/) · [node](expedia-scraper/browser/nodejs/) · [cli](expedia-scraper/browser/cli/) · [mcp](expedia-scraper/browser/mcp/) |
| Fashionphile | [fashionphile-scraper](fashionphile-scraper/) | [py](fashionphile-scraper/browser/python/) · [node](fashionphile-scraper/browser/nodejs/) · [cli](fashionphile-scraper/browser/cli/) · [mcp](fashionphile-scraper/browser/mcp/) |
| Flipkart | [flipkart-scraper](flipkart-scraper/) | [py](flipkart-scraper/browser/python/) · [node](flipkart-scraper/browser/nodejs/) · [cli](flipkart-scraper/browser/cli/) · [mcp](flipkart-scraper/browser/mcp/) |
| G2 | [g2-scraper](g2-scraper/) | [py](g2-scraper/browser/python/) · [node](g2-scraper/browser/nodejs/) · [mcp](g2-scraper/browser/mcp/) |
| GameStop | [gamestop-scraper](gamestop-scraper/) | [py](gamestop-scraper/browser/python/) · [node](gamestop-scraper/browser/nodejs/) |
| Glassdoor | [glassdoor-scraper](glassdoor-scraper/) | [py](glassdoor-scraper/browser/python/) · [node](glassdoor-scraper/browser/nodejs/) · [cli](glassdoor-scraper/browser/cli/) · [mcp](glassdoor-scraper/browser/mcp/) |
| GOAT | [goat-scraper](goat-scraper/) | [py](goat-scraper/browser/python/) · [node](goat-scraper/browser/nodejs/) · [mcp](goat-scraper/browser/mcp/) |
| Google | [google-scraper](google-scraper/) | [py](google-scraper/browser/python/) · [node](google-scraper/browser/nodejs/) · [cli](google-scraper/browser/cli/) |
| Google AI Mode | [google-ai-mode-scraper](google-ai-mode-scraper/) | [py](google-ai-mode-scraper/browser/python/) · [node](google-ai-mode-scraper/browser/nodejs/) |
| Google Jobs | [google-jobs-scraper](google-jobs-scraper/) | [py](google-jobs-scraper/browser/python/) · [node](google-jobs-scraper/browser/nodejs/) · [cli](google-jobs-scraper/browser/cli/) · [mcp](google-jobs-scraper/browser/mcp/) |
| Google Maps | [google-maps-scraper](google-maps-scraper/) | [py](google-maps-scraper/browser/python/) · [node](google-maps-scraper/browser/nodejs/) · [cli](google-maps-scraper/browser/cli/) · [mcp](google-maps-scraper/browser/mcp/) |
| Google News | [google-news-scraper](google-news-scraper/) | [py](google-news-scraper/browser/python/) · [node](google-news-scraper/browser/nodejs/) · [cli](google-news-scraper/browser/cli/) · [mcp](google-news-scraper/browser/mcp/) |
| Google Play | [google-play-scraper](google-play-scraper/) | [py](google-play-scraper/browser/python/) · [node](google-play-scraper/browser/nodejs/) · [cli](google-play-scraper/browser/cli/) · [mcp](google-play-scraper/browser/mcp/) |
| Grok | [grok-scraper](grok-scraper/) | [py](grok-scraper/browser/python/) · [node](grok-scraper/browser/nodejs/) · [cli](grok-scraper/browser/cli/) · [mcp](grok-scraper/browser/mcp/) |
| Homegate | [homegate-scraper](homegate-scraper/) | [py](homegate-scraper/browser/python/) · [node](homegate-scraper/browser/nodejs/) · [mcp](homegate-scraper/browser/mcp/) |
| Idealista | [idealista-scraper](idealista-scraper/) | [py](idealista-scraper/browser/python/) · [node](idealista-scraper/browser/nodejs/) · [cli](idealista-scraper/browser/cli/) · [mcp](idealista-scraper/browser/mcp/) |
| ImmobilienScout24 (DE) | [immobilienscout24-scraper](immobilienscout24-scraper/) | [py](immobilienscout24-scraper/browser/python/) · [node](immobilienscout24-scraper/browser/nodejs/) · [cli](immobilienscout24-scraper/browser/cli/) · [mcp](immobilienscout24-scraper/browser/mcp/) |
| ImmoScout24 (CH) | [immoscout24-scraper](immoscout24-scraper/) | [py](immoscout24-scraper/browser/python/) · [node](immoscout24-scraper/browser/nodejs/) |
| Immowelt | [immowelt-scraper](immowelt-scraper/) | [py](immowelt-scraper/browser/python/) · [node](immowelt-scraper/browser/nodejs/) · [cli](immowelt-scraper/browser/cli/) · [mcp](immowelt-scraper/browser/mcp/) |
| Indeed | [indeed-scraper](indeed-scraper/) | [py](indeed-scraper/browser/python/) · [node](indeed-scraper/browser/nodejs/) |
| Instagram | [instagram-scraper](instagram-scraper/) | [py](instagram-scraper/browser/python/) · [node](instagram-scraper/browser/nodejs/) |
| Lazada | [lazada-scraper](lazada-scraper/) | [py](lazada-scraper/browser/python/) · [node](lazada-scraper/browser/nodejs/) · [cli](lazada-scraper/browser/cli/) · [mcp](lazada-scraper/browser/mcp/) |
| Leboncoin | [leboncoin-scraper](leboncoin-scraper/) | [py](leboncoin-scraper/browser/python/) · [node](leboncoin-scraper/browser/nodejs/) · [mcp](leboncoin-scraper/browser/mcp/) |
| LinkedIn | [linkedin-scraper](linkedin-scraper/) | [py](linkedin-scraper/browser/python/) · [node](linkedin-scraper/browser/nodejs/) |
| Macy's | [macys-scraper](macys-scraper/) | [py](macys-scraper/browser/python/) · [node](macys-scraper/browser/nodejs/) · [cli](macys-scraper/browser/cli/) · [mcp](macys-scraper/browser/mcp/) |
| MercadoLibre | [mercadolibre-scraper](mercadolibre-scraper/) | [py](mercadolibre-scraper/browser/python/) · [node](mercadolibre-scraper/browser/nodejs/) · [cli](mercadolibre-scraper/browser/cli/) · [mcp](mercadolibre-scraper/browser/mcp/) |
| Nordstrom | [nordstorm-scraper](nordstorm-scraper/) | [py](nordstorm-scraper/browser/python/) · [node](nordstorm-scraper/browser/nodejs/) · [cli](nordstorm-scraper/browser/cli/) |
| OpenSea | [opensea-scraper](opensea-scraper/) | [py](opensea-scraper/browser/python/) · [node](opensea-scraper/browser/nodejs/) · [cli](opensea-scraper/browser/cli/) · [mcp](opensea-scraper/browser/mcp/) |
| Perplexity | [perplexity-scraper](perplexity-scraper/) | [py](perplexity-scraper/browser/python/) · [node](perplexity-scraper/browser/nodejs/) · [cli](perplexity-scraper/browser/cli/) · [mcp](perplexity-scraper/browser/mcp/) |
| Priceline | [priceline-scraper](priceline-scraper/) | [py](priceline-scraper/browser/python/) · [node](priceline-scraper/browser/nodejs/) |
| Realestate.com.au | [realestatecom-scraper](realestatecom-scraper/) | [py](realestatecom-scraper/browser/python/) · [node](realestatecom-scraper/browser/nodejs/) |
| Realtor.com | [realtorcom-scraper](realtorcom-scraper/) | [py](realtorcom-scraper/browser/python/) · [node](realtorcom-scraper/browser/nodejs/) · [mcp](realtorcom-scraper/browser/mcp/) |
| Redbubble | [redbubble-scraper](redbubble-scraper/) | [py](redbubble-scraper/browser/python/) · [node](redbubble-scraper/browser/nodejs/) · [cli](redbubble-scraper/browser/cli/) · [mcp](redbubble-scraper/browser/mcp/) |
| Reddit | [reddit-scraper](reddit-scraper/) | [py](reddit-scraper/browser/python/) · [node](reddit-scraper/browser/nodejs/) · [cli](reddit-scraper/browser/cli/) · [mcp](reddit-scraper/browser/mcp/) |
| Redfin | [redfin-scraper](redfin-scraper/) | [py](redfin-scraper/browser/python/) · [node](redfin-scraper/browser/nodejs/) · [cli](redfin-scraper/browser/cli/) · [mcp](redfin-scraper/browser/mcp/) |
| Rightmove | [rightmove-scraper](rightmove-scraper/) | [py](rightmove-scraper/browser/python/) · [node](rightmove-scraper/browser/nodejs/) · [cli](rightmove-scraper/browser/cli/) · [mcp](rightmove-scraper/browser/mcp/) |
| SeLoger | [seloger-scraper](seloger-scraper/) | [py](seloger-scraper/browser/python/) · [node](seloger-scraper/browser/nodejs/) · [cli](seloger-scraper/browser/cli/) · [mcp](seloger-scraper/browser/mcp/) |
| Shein | [shein-scraper](shein-scraper/) | [py](shein-scraper/browser/python/) · [node](shein-scraper/browser/nodejs/) · [cli](shein-scraper/browser/cli/) |
| SimilarWeb | [similarweb-scraper](similarweb-scraper/) | [py](similarweb-scraper/browser/python/) · [node](similarweb-scraper/browser/nodejs/) · [cli](similarweb-scraper/browser/cli/) · [mcp](similarweb-scraper/browser/mcp/) |
| StockX | [stockx-scraper](stockx-scraper/) | [py](stockx-scraper/browser/python/) · [node](stockx-scraper/browser/nodejs/) |
| Threads | [threads-scraper](threads-scraper/) | [py](threads-scraper/browser/python/) · [node](threads-scraper/browser/nodejs/) |
| TikTok | [tiktok-scraper](tiktok-scraper/) | [py](tiktok-scraper/browser/python/) · [node](tiktok-scraper/browser/nodejs/) |
| Trip.com | [trip-scraper](trip-scraper/) | [py](trip-scraper/browser/python/) · [node](trip-scraper/browser/nodejs/) · [cli](trip-scraper/browser/cli/) · [mcp](trip-scraper/browser/mcp/) |
| TripAdvisor | [tripadvisor-scraper](tripadvisor-scraper/) | [py](tripadvisor-scraper/browser/python/) · [node](tripadvisor-scraper/browser/nodejs/) · [cli](tripadvisor-scraper/browser/cli/) · [mcp](tripadvisor-scraper/browser/mcp/) |
| Trivago | [trivago-scraper](trivago-scraper/) | [py](trivago-scraper/browser/python/) · [node](trivago-scraper/browser/nodejs/) · [cli](trivago-scraper/browser/cli/) · [mcp](trivago-scraper/browser/mcp/) |
| Trustpilot | [trustpilot-scraper](trustpilot-scraper/) | [py](trustpilot-scraper/browser/python/) · [node](trustpilot-scraper/browser/nodejs/) · [cli](trustpilot-scraper/browser/cli/) · [mcp](trustpilot-scraper/browser/mcp/) |
| Twitter (X) | [twitter-scraper](twitter-scraper/) | [py](twitter-scraper/browser/python/) · [node](twitter-scraper/browser/nodejs/) · [mcp](twitter-scraper/browser/mcp/) |
| Vestiaire Collective | [vestiairecollective-scraper](vestiairecollective-scraper/) | [py](vestiairecollective-scraper/browser/python/) · [node](vestiairecollective-scraper/browser/nodejs/) · [cli](vestiairecollective-scraper/browser/cli/) · [mcp](vestiairecollective-scraper/browser/mcp/) |
| Walmart | [walmart-scraper](walmart-scraper/) | [py](walmart-scraper/browser/python/) · [node](walmart-scraper/browser/nodejs/) · [cli](walmart-scraper/browser/cli/) · [mcp](walmart-scraper/browser/mcp/) |
| Wellfound | [wellfound-scraper](wellfound-scraper/) | [py](wellfound-scraper/browser/python/) · [node](wellfound-scraper/browser/nodejs/) · [cli](wellfound-scraper/browser/cli/) · [mcp](wellfound-scraper/browser/mcp/) |
| Worten | [worten-scraper](worten-scraper/) | [py](worten-scraper/browser/python/) · [node](worten-scraper/browser/nodejs/) · [cli](worten-scraper/browser/cli/) · [mcp](worten-scraper/browser/mcp/) |
| Xbox | [xbox-scraper](xbox-scraper/) | [py](xbox-scraper/browser/python/) · [node](xbox-scraper/browser/nodejs/) · [cli](xbox-scraper/browser/cli/) · [mcp](xbox-scraper/browser/mcp/) |
| YellowPages | [yellowpages-scraper](yellowpages-scraper/) | [py](yellowpages-scraper/browser/python/) · [node](yellowpages-scraper/browser/nodejs/) · [cli](yellowpages-scraper/browser/cli/) |
| Yelp | [yelp-scraper](yelp-scraper/) | [py](yelp-scraper/browser/python/) · [node](yelp-scraper/browser/nodejs/) · [cli](yelp-scraper/browser/cli/) |
| YouTube | [youtube-scraper](youtube-scraper/) | [py](youtube-scraper/browser/python/) · [node](youtube-scraper/browser/nodejs/) · [cli](youtube-scraper/browser/cli/) · [mcp](youtube-scraper/browser/mcp/) |
| Zara | [zara-scraper](zara-scraper/) | [py](zara-scraper/browser/python/) · [node](zara-scraper/browser/nodejs/) · [cli](zara-scraper/browser/cli/) · [mcp](zara-scraper/browser/mcp/) |
| Zillow | [zillow-scraper](zillow-scraper/) | [py](zillow-scraper/browser/python/) · [node](zillow-scraper/browser/nodejs/) · [cli](zillow-scraper/browser/cli/) · [mcp](zillow-scraper/browser/mcp/) |
| Zoopla | [zoopla-scraper](zoopla-scraper/) | [py](zoopla-scraper/browser/python/) · [node](zoopla-scraper/browser/nodejs/) · [cli](zoopla-scraper/browser/cli/) · [mcp](zoopla-scraper/browser/mcp/) |

Click any cell in the **Surfaces** column to jump straight to that implementation. Every site folder ships its own `README.md` and `DATA_MODEL.md`.

### Live-verified fixtures

Every site in the table above ships at least one committed `results/*.json` produced by a live Scrapeless run. To regenerate any fixture locally:

```bash
export SCRAPELESS_API_KEY=sk_...
cd <site>-scraper/python && SAVE_TEST_RESULTS=true python run.py        # Python
cd <site>-scraper/nodejs && SAVE_TEST_RESULTS=true node run.mjs         # Node.js
```

## The two-surface model

| Surface | Built on | When to use it |
| --- | --- | --- |
| **Python** | `scrapeless` SDK + Playwright (browser sites) / `deepserp.scrape` (SERP sites) | Data pipelines, Jupyter, FastAPI services. Async functions, typed dataclasses. |
| **Node.js** | `@scrapeless-ai/sdk` + `puppeteer-core` (browser sites) / `deepserp.scrape` (SERP sites) | Web apps, serverless functions, JS/TS stacks. |

Both surfaces emit data matching the same `DATA_MODEL.md` schema per site. The data shape is the contract; the surface is developer ergonomics.
