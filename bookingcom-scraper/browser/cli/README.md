# Booking.com — CLI surface

Scrape Booking.com search-results and hotel detail pages from the command line with the
[`scrapeless-scraping-browser`](https://www.npmjs.com/package/scrapeless-scraping-browser)
CLI. One Scrapeless cloud session drives a real browser; each page is extracted in-browser with the
CLI's `eval` subcommand. Output matches the `nodejs/` and `python/` surfaces — see
[`../../DATA_MODEL.md`](../../DATA_MODEL.md).

The CLI surface covers the two pure-DOM surfaces — `search` (a list of `SearchResult`) and `hotel`
(a single `Hotel`). The `price[]` availability calendar, the `reviews`, and the location-autocomplete
surfaces all depend on Booking GraphQL POSTs / network capture that a single in-page `eval` cannot
perform; use the `nodejs/` surface or the conversational `mcp/` surface for those.

## 1. Install

```bash
npm install -g scrapeless-scraping-browser
```

`node` is also required — the steps below use it to pull values out of the CLI's JSON envelope
(`jq` works too, if preferred).

## 2. Set your API key

```bash
export SCRAPELESS_API_KEY=sk_...      # sign up at https://app.scrapeless.com
```

## 3. Scrape your first page

Every scrape is the same four moves: open a session, navigate, wait for a stable marker, run an
in-page extractor. Booking.com is aggressive about anti-bot, so the session is opened with a
residential proxy country (`GB`, matching the `en-gb` locale on the URLs). Start with a hotel page.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name bookingcom-cli --ttl 300 --proxy-country GB --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate, then wait for the property heading to render
scrapeless-scraping-browser --session-id "$SID" open "https://www.booking.com/hotel/gb/gardencourthotel.en-gb.html"
scrapeless-scraping-browser --session-id "$SID" wait "h2"

# run the in-page hotel extractor — its JSON comes back in data.result
# save the hotel extractor (a single expression returning a JSON string)
cat > hotel.js <<'JS'
// In-page extractor for a Booking.com hotel detail page.
// Returns a JSON string — a single Hotel (see ../../../DATA_MODEL.md).
// NOTE: the per-night `price[]` calendar comes from a GraphQL POST that the CLI
// `eval` surface cannot make — it is emitted as `[]` here. Use the nodejs/ or
// python/ surfaces when you need the pricing calendar.
JSON.stringify(
  (function () {
    const html = document.documentElement.outerHTML;
    const url = location.href;

    const features = {};
    document
      .querySelectorAll(
        "[data-testid='property-most-popular-facilities-wrapper']"
      )
      .forEach((el) => {
        const header = el.querySelector("h3")?.textContent.trim() || "";
        const items = [];
        el.querySelectorAll("li").forEach((li) => {
          const t = li.textContent.trim();
          if (t) items.push(t);
        });
        if (header && items.length) features[header] = items;
      });

    const latlng = document
      .querySelector(
        "div[data-testid='PropertyHeaderAddressDesktop-wrapper'] a"
      )
      ?.getAttribute("data-atlas-latlng");
    let lat = "",
      lng = "";
    if (latlng) [lat, lng] = latlng.split(",");

    const idMatch = /b_hotel_id:\s*'(.+?)'/.exec(html);

    const description =
      document
        .querySelector(
          "[data-capla-component-boundary='b-property-web-property-page/PropertyDescriptionDesktop']"
        )
        ?.textContent.trim() || "";

    const images = [];
    document.querySelectorAll("#photo_wrapper img").forEach((el) => {
      const src = el.getAttribute("src");
      if (src) images.push(src);
    });

    return {
      url,
      id: idMatch ? idMatch[1] : null,
      title: document.querySelector("h2")?.textContent || null,
      description,
      address:
        document
          .querySelector(
            "div[data-testid='PropertyHeaderAddressDesktop-wrapper'] button div"
          )
          ?.textContent || null,
      images,
      lat,
      lng,
      features,
      price: [],
    };
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat hotel.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

`$HOTEL_JS` is the in-page extractor (the `HOTEL_JS` extractor). It
returns a `Hotel` object:

```json
{
  "url": "https://www.booking.com/hotel/gb/gardencourthotel.en-gb.html",
  "id": "102764",
  "title": "Garden Court Hotel",
  "description": "The 19th-century Garden Court Hotel is superbly situated in ...",
  "address": "30-31 Kensington Gardens Square, Notting Hill, ...",
  "images": ["https://cf.bstatic.com/xdata/images/hotel/max1024x768/11922647.jpg?..."],
  "lat": "51.514317059181394",
  "lng": "-0.19066348671913147",
  "features": { "Most popular facilities": ["Free WiFi", "Parking", "Family rooms"] },
  "price": []
}
```

> `price[]` is empty from the CLI surface — the 61-day availability calendar is served by a
> separate `AvailabilityCalendar` GraphQL POST. Use `nodejs/` (`scrape_hotel`) or the `mcp/` surface
> to populate it.

## 4. Scrape a search-results page

Reuse the same session — just `open` a search-results URL and wait for the property cards.

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://www.booking.com/searchresults.en-gb.html?ss=Malta&dest_id=3939&dest_type=region&group_adults=1&no_rooms=1&group_children=0&lang=en-gb"
scrapeless-scraping-browser --session-id "$SID" wait "div[data-testid=property-card]"
# save the search extractor (a single expression returning a JSON string)
cat > search.js <<'JS'
// In-page extractor for a Booking.com search-results page.
// Returns a JSON string — a list of SearchResult (see ../../../DATA_MODEL.md).
JSON.stringify(
  Array.from(
    document.querySelectorAll("div[data-testid='property-card']")
  ).map((card) => {
    const name =
      card.querySelector("div[data-testid='title']")?.textContent.trim() || "";
    const link =
      card
        .querySelector("a[data-testid='title-link']")
        ?.getAttribute("href") ?? "";
    const location =
      card
        .querySelector("span[data-testid='address']")
        ?.textContent.trim() || "";
    const distance =
      card
        .querySelector("span[data-testid='distance']")
        ?.textContent.trim() || "";

    const score =
      card
        .querySelector("div[data-testid='review-score'] > div")
        ?.textContent.trim() || null;
    const reviewBlock =
      card.querySelector("div[data-testid='review-score']")?.textContent || "";
    const reviewCountM = /([\d,]+)\s+reviews?/.exec(reviewBlock);
    const reviewCount = reviewCountM
      ? parseInt(reviewCountM[1].replace(/,/g, ""), 10)
      : null;
    const reviewWord =
      card
        .querySelector(
          "div[data-testid='review-score'] > div + div > div"
        )
        ?.textContent.trim() || null;

    const priceText =
      card
        .querySelector("span[data-testid='price-and-discounted-price']")
        ?.textContent.trim() || "";
    const photo =
      card.querySelector("img[data-testid='image']")?.getAttribute("src") ??
      null;

    const stars = card.querySelectorAll(
      "div[data-testid='rating-stars'] svg"
    ).length;
    const starRating = stars || null;

    const freeCancellation = (card.textContent || "").includes(
      "Free cancellation"
    );

    return {
      displayName: { text: name },
      basicPropertyData: {
        pageName: link,
        location: { address: location, city: null, countryCode: null },
        reviewScore: {
          score,
          reviewCount,
          totalScoreTextTag: { translation: reviewWord },
        },
        starRating: starRating ? { value: starRating } : null,
        photos: {
          main: photo ? { highResUrl: { relativeUrl: photo } } : null,
        },
      },
      location: {
        displayLocation: location,
        mainDistance: distance || null,
      },
      priceDisplayInfoIrene: {
        displayPrice: priceText
          ? { amountPerStay: { amount: priceText } }
          : null,
      },
      policies: { showFreeCancellation: Boolean(freeCancellation) },
    };
  })
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat search.js)" --json
```

`$SEARCH_JS` is the `SEARCH_JS` extractor. `data.result` is a list of
`SearchResult` (field names mirror Booking's GraphQL fragment):

```json
[
  {
    "displayName": { "text": "Bayview Hotel by ST Hotels" },
    "basicPropertyData": {
      "pageName": "https://www.booking.com/hotel/mt/bayview-apartments.en-gb.html?...",
      "location": { "address": "", "city": null, "countryCode": null },
      "reviewScore": { "score": "Scored 7.7", "reviewCount": 7197, "totalScoreTextTag": { "translation": "Good" } },
      "starRating": { "value": 6 },
      "photos": { "main": { "highResUrl": { "relativeUrl": "https://cf.bstatic.com/xdata/images/hotel/square240/295096407.webp?..." } } }
    },
    "location": { "displayLocation": "", "mainDistance": null },
    "priceDisplayInfoIrene": { "displayPrice": { "amountPerStay": { "amount": "€ 864" } } },
    "policies": { "showFreeCancellation": true }
  }
]
```

## 5. Output shape

Each extractor is a single expression that returns a JSON string, kept in lockstep with the
selectors in [`../nodejs/bookingcom.mjs`](../nodejs/bookingcom.mjs) (`parseSearchHtml` ↔ search,
`parseHotel` ↔ hotel):

| Extractor | Returns |
| --- | --- |
| `SEARCH_JS` | list of `SearchResult` |
| `HOTEL_JS`  | one `Hotel` (with `price: []`) |

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in
[`results/`](results/) (`search.json`, `hotel.json` — copied from the live-verified `nodejs/` run,
so `hotel.json` shows the full `price[]` calendar the `nodejs/` surface produces).
