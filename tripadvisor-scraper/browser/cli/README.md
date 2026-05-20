# TripAdvisor — CLI surface

Scrape TripAdvisor hotels-listing and hotel-review pages from the command line with the
[`scrapeless-scraping-browser`](https://www.npmjs.com/package/scrapeless-scraping-browser)
CLI. One Scrapeless cloud session drives a real browser; each page is extracted in-browser with the
CLI's `eval` subcommand. Output matches the `nodejs/` and `python/` surfaces — see
[`../../DATA_MODEL.md`](../../DATA_MODEL.md).

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

## 3. Scrape a hotels listing

Every scrape is the same four moves: open a session, navigate, wait for a stable marker, run an
in-page extractor. TripAdvisor shows a "Pardon Our Interruption" / Captcha shell to fresh proxies,
so warm up on the homepage first.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name tripadvisor-cli --ttl 300 --proxy-country US --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# warm-up: load the homepage so TripAdvisor drops cookies
scrapeless-scraping-browser --session-id "$SID" open "https://www.tripadvisor.com/"
scrapeless-scraping-browser --session-id "$SID" wait "body"

# navigate to the hotels listing, then wait for the result list
scrapeless-scraping-browser --session-id "$SID" open "https://www.tripadvisor.com/Hotels-g60763-New_York_City_New_York-Hotels.html"
scrapeless-scraping-browser --session-id "$SID" wait "div[data-test-target='hotels-main-list']"

# run the in-page extractor — pass the SEARCH_JS expression as the eval arg
# save the search extractor (a single expression returning a JSON string)
cat > search.js <<'JS'
// In-page extractor for a TripAdvisor hotels search/listing page.
// Returns a JSON string — a list of Preview/SearchResult (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const baseUrl = location.href;
    const txt = (node) => (node?.textContent ?? "").trim();
    const parsed = [];

    document
      .querySelectorAll("div[data-test-target='hotels-main-list'] ol li")
      .forEach((li) => {
        const titles = Array.from(
          li.querySelectorAll("div[data-automation=hotel-card-title] a h3")
        ).map((h) => txt(h));
        const title = titles.length > 1 ? titles[1] : titles[0] ?? null;
        const href = li
          .querySelector("div[data-automation=hotel-card-title] a")
          ?.getAttribute("href");
        if (!href) return;
        let abs;
        try {
          abs = new URL(href, baseUrl);
        } catch (e) {
          return;
        }
        abs.search = "";
        abs.hash = "";
        parsed.push({ url: abs.toString(), name: title });
      });
    if (parsed.length) return parsed;

    // Fallback: the older `.listing_title` layout.
    document.querySelectorAll("div.listing_title > a").forEach((a) => {
      const href = a.getAttribute("href") ?? "";
      const text = txt(a);
      let url;
      try {
        url = new URL(href, baseUrl).toString();
      } catch (e) {
        return;
      }
      parsed.push({ url, name: text.split(". ").slice(-1)[0] });
    });
    return parsed;
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat search.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a list of `Preview`/`SearchResult` (one per hotel card):

```json
[
  { "url": "https://www.tripadvisor.com/Hotel_Review-g60763-d93589-Reviews-...", "name": "The Plaza" }
]
```

## 4. Scrape a hotel review page

Reuse the same session — `open` a `Hotel_Review` URL and wait for the review cards. The extractor
reads the `LodgingBusiness` JSON-LD block for `basic_data`, plus the on-page description, amenities,
and review cards.

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://www.tripadvisor.com/Hotel_Review-g190327-d264936-Reviews-1926_Hotel_Spa-Sliema_Island_of_Malta.html"
scrapeless-scraping-browser --session-id "$SID" wait "div[data-test-target='HR_CC_CARD']"
# save the hotels extractor (a single expression returning a JSON string)
cat > hotels.js <<'JS'
// In-page extractor for a TripAdvisor hotel detail page.
// Returns a JSON string — a single Hotel (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const txt = (node) => (node?.textContent ?? "").trim();

    // Prefer the explicit JSON-LD LodgingBusiness block. Several `<script>` tags
    // (analytics, tracking) mention "aggregateRating" too, so filter to ld+json.
    let basicData = {};
    const ldNodes = document.querySelectorAll(
      'script[type="application/ld+json"]'
    );
    for (const el of ldNodes) {
      const t = el.textContent;
      if (!t) continue;
      let parsed;
      try {
        parsed = JSON.parse(t);
      } catch (e) {
        continue;
      }
      const candidates = Array.isArray(parsed)
        ? parsed
        : parsed["@graph"]
        ? parsed["@graph"]
        : [parsed];
      let found = false;
      for (const node of candidates) {
        if (!node || typeof node !== "object") continue;
        const ty = node["@type"];
        if (
          ty === "LodgingBusiness" ||
          ty === "Hotel" ||
          (Array.isArray(ty) && ty.some((x) => /Lodging|Hotel/.test(x)))
        ) {
          basicData = node;
          found = true;
          break;
        }
      }
      if (found) break;
    }
    if (!Object.keys(basicData).length) {
      const basicScript = Array.from(document.querySelectorAll("script")).find(
        (s) => (s.textContent || "").includes("aggregateRating")
      );
      if (basicScript) {
        try {
          basicData = JSON.parse(basicScript.textContent);
        } catch (e) {}
      }
    }

    const description =
      txt(
        document.querySelector(
          "div[data-automation='aboutTabDescription'] div div div"
        )
      ) || null;

    const featues = [];
    document.querySelectorAll("div[data-test-target*='amenity']").forEach((el) => {
      const t = txt(el);
      if (t) featues.push(t);
    });

    const reviews = [];
    document
      .querySelectorAll("div[data-test-target='HR_CC_CARD']")
      .forEach((card) => {
        const title =
          txt(
            card.querySelector("div[data-test-target='review-title'] span")
          ) || null;
        const textParts = Array.from(
          card.querySelectorAll(
            "div._c div[class*='fIrGe'] span[class*='JguWG'] span"
          )
        ).map((s) => s.textContent ?? "");
        const text = textParts.join("");
        // cheerio's :contains('of 5 bubbles') — last matching node's text.
        const bubbleNodes = Array.from(card.querySelectorAll("*")).filter((e) =>
          /of 5 bubbles/.test(e.textContent || "")
        );
        const rateText = bubbleNodes.length
          ? bubbleNodes[bubbleNodes.length - 1].textContent
          : "";
        const rateMatch = rateText.match(/([\d.]+) of 5 bubbles/);
        const rate = rateMatch ? parseFloat(rateMatch[1]) : null;
        // span:contains('Date of stay:') → .parent().next('span')
        const labelSpan = (label) =>
          Array.from(card.querySelectorAll("span")).find(
            (s) => (s.textContent || "").trim() === label
          );
        const valueAfter = (label) => {
          const sp = labelSpan(label);
          if (!sp || !sp.parentElement) return null;
          let sib = sp.parentElement.nextElementSibling;
          if (sib && sib.tagName === "SPAN") return txt(sib) || null;
          return null;
        };
        const tripDate = valueAfter("Date of stay:");
        const tripType = valueAfter("Trip type:");
        reviews.push({ title, text, rate, tripDate, tripType });
      });

    // NB: the upstream reference typo "featues" preserved for parity.
    return { basic_data: basicData, description, featues, reviews };
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat hotels.js)" --json
```

`data.result` is a single `Hotel` (the field `featues` preserves the upstream typo for parity):

```json
{
  "basic_data": { "@type": "LodgingBusiness", "name": "1926 Hotel & Spa", "aggregateRating": { "ratingValue": 4.5, "reviewCount": 1234 } },
  "description": "...",
  "featues": ["Free Wifi", "Pool", "..."],
  "reviews": [
    { "title": "Great stay", "text": "...", "rate": 5, "tripDate": "March 2024", "tripType": "Couples" }
  ]
}
```

## 5. Output shape

Each in-page extractor is a single expression
that returns a JSON string, kept in lockstep with the selectors in
[`../nodejs/tripadvisor.mjs`](../nodejs/tripadvisor.mjs):

| Extractor | Returns |
| --- | --- |
| `SEARCH_JS` | list of `Preview`/`SearchResult` |
| `HOTEL_JS` | one `Hotel` (`{ basic_data, description, featues, reviews }`) |

The `location` autocomplete kind is **not** part of this surface — it types into TripAdvisor's
homepage search box and captures the typeahead GraphQL XHR, which needs keyboard input + network
interception and doesn't fit the CLI's in-page `eval` model. Use the `nodejs/` or `python/` surface
(or the `mcp/` surface) for `location`.

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in [`results/`](results/).
