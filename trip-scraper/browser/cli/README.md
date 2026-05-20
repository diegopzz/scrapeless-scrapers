# Trip.com — CLI surface

Scrape Trip.com hotel search and hotel detail pages from the command line with the
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

## 3. Scrape your first page

Every scrape is the same four moves: open a session, navigate, wait for a stable marker, run an
in-page extractor. Start with a city hotel list.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name trip-cli --ttl 300 --proxy-country US --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate, then wait for the hotel cards to render
scrapeless-scraping-browser --session-id "$SID" open "https://www.trip.com/hotels/list?city=53&checkin=2026/06/15&checkout=2026/06/16"
scrapeless-scraping-browser --session-id "$SID" wait "[id][class*='hotel-card'], [id][class*='compressmeta-hotel-wrap']"

# run the in-page extractor — its JSON comes back in data.result
# save the search extractor (a single expression returning a JSON string)
cat > search.js <<'JS'
// In-page extractor for a Trip.com city hotel list page.
// Returns a JSON string — a list of SearchResult (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const params = new URLSearchParams(location.search);
    const checkin = params.get("checkin") || "";
    const checkout = params.get("checkout") || "";

    function parseIntOrNull(text) {
      if (!text) return null;
      const m = /([\d,]+)/.exec(text);
      if (!m) return null;
      const n = parseInt(m[1].replace(/,/g, ""), 10);
      return Number.isFinite(n) ? n : null;
    }
    function detailUrl(hotelId) {
      const p = new URLSearchParams({ hotelId: String(hotelId) });
      if (checkin) p.set("checkIn", checkin);
      if (checkout) p.set("checkOut", checkout);
      return `https://www.trip.com/hotels/detail/?${p.toString()}`;
    }
    const txt = (node) => (node?.textContent ?? "").trim();

    const out = [];
    // Trip ships two layouts: the older `.hotel-card` and the newer
    // `.compressmeta-hotel-wrap-v8` ("version B").
    document
      .querySelectorAll("[id][class*='hotel-card'], [id][class*='compressmeta-hotel-wrap']")
      .forEach((el) => {
        const id = el.getAttribute("id") || "";
        if (!/^\d+$/.test(id)) return;
        const name =
          txt(el.querySelector(".list-card-title .name")) ||
          txt(el.querySelector(".list-card-title")) ||
          txt(el.querySelector(".hotel-title")) ||
          txt(el.querySelector(".name"));
        // Score: a `.real` block whose text is a plain number (e.g. "9.4").
        let score = null;
        el.querySelectorAll(".real").forEach((r) => {
          if (score) return;
          const t = txt(r);
          if (/^\d+(\.\d+)?$/.test(t)) score = t;
        });
        if (!score) score = txt(el.querySelector(".score")) || null;
        // Word-form review tag near the score.
        const wordEl = txt(el.querySelector(".describe, .review-rt, .outstanding"));
        const wordMatch = wordEl
          ? /\b(Outstanding|Excellent|Very Good|Good|Pleasant|Fair|Wonderful|Fabulous|Exceptional)\b/i.exec(wordEl)
          : null;
        const reviewWord = wordMatch ? wordMatch[1] : null;
        const reviewBlock = Array.from(el.querySelectorAll(".count, .review-rt"))
          .map((e) => e.textContent)
          .join(" ");
        const reviewCountMatch = reviewBlock
          ? /([\d,]+)\s+reviews?/i.exec(reviewBlock)
          : null;
        const reviewCount = reviewCountMatch ? parseIntOrNull(reviewCountMatch[1]) : null;
        // Price: `.real.labelColor` carries the headline price in version B;
        // older layout uses `.price-line`.
        const price =
          txt(el.querySelector(".real.labelColor")) ||
          txt(el.querySelector(".price-line")) ||
          null;
        const totalPrice = txt(el.querySelector(".price-explain")) || null;
        const tags = [];
        el.querySelectorAll(".member-reward-tag, .encourage-tag, .highlight-tag, .hotel-tag").forEach((t) => {
          const v = txt(t);
          if (v && !tags.includes(v)) tags.push(v);
        });
        const locText =
          txt(el.querySelector(".transport, [class*='location'], [class*='landmark']")).replace(/\s+/g, " ") ||
          null;
        const image =
          el.querySelector(".multi-images img, img.m-lazyImg__img")?.getAttribute("src") || null;
        out.push({
          id,
          name,
          url: detailUrl(id),
          score,
          reviewWord,
          reviewCount,
          price,
          totalPrice,
          tags,
          location: locText,
          image,
        });
      });
    return out;
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat search.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a list of `SearchResult`:

```json
[
  {
    "id": "106534464",
    "name": "Four Points By Sheraton Hainan Qiongzhong",
    "url": "https://www.trip.com/hotels/detail/?hotelId=106534464&checkIn=2026%2F06%2F15&checkOut=2026%2F06%2F16",
    "score": "9.4",
    "reviewWord": null,
    "reviewCount": null,
    "price": "US$57",
    "totalPrice": "Total (incl. taxes & fees): US$66",
    "tags": ["30-minute Cancellation Window", "Breakfast included"],
    "location": null,
    "image": "https://ak-d.tripcdn.com/images/0226f12000bi9etq50043_R_600_600_R5_D.jpg_.webp"
  }
]
```

## 4. Scrape a hotel detail page

Reuse the same session — just `open` a hotel detail URL and wait for the hotel name.

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://www.trip.com/hotels/detail/?hotelId=106534464&checkIn=2026/06/15&checkOut=2026/06/16"
scrapeless-scraping-browser --session-id "$SID" wait "h1, [class*='headInfo'], [class*='hotelName']"
# save the hotel extractor (a single expression returning a JSON string)
cat > hotel.js <<'JS'
// In-page extractor for a Trip.com hotel detail page.
// Returns a JSON string — a single Hotel (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const hotelId = new URLSearchParams(location.search).get("hotelId") || "";
    const url = location.href;

    function parseIntOrNull(text) {
      if (!text) return null;
      const m = /([\d,]+)/.exec(text);
      if (!m) return null;
      const n = parseInt(m[1].replace(/,/g, ""), 10);
      return Number.isFinite(n) ? n : null;
    }
    const txt = (node) => (node?.textContent ?? "").trim();

    // Title can live in `h1.hotelTitle__hotelName`, `.headInfo .name`, or just `h1`.
    const name =
      txt(document.querySelector("h1.headInfo .name")) ||
      txt(document.querySelector("h1[class*='hotelName']")) ||
      txt(document.querySelector("h1")) ||
      txt(document.querySelector(".hotel-name"));
    const address = txt(document.querySelector("[class*='address']")) || null;
    const score =
      txt(
        Array.from(document.querySelectorAll("[class*='real']")).find((el) =>
          /^[0-9.]+$/.test((el.textContent ?? "").trim())
        )
      ) ||
      txt(document.querySelector(".score")) ||
      null;
    const reviewBlock = txt(
      document.querySelector("[class*='comment-num'], [class*='reviewCount']")
    );
    const reviewCount = parseIntOrNull(reviewBlock);
    const description =
      txt(document.querySelector("[class*='introduction']")) ||
      txt(document.querySelector("[class*='hotel-description']")) ||
      "";
    const amenities = [];
    document
      .querySelectorAll("[class*='facilities'] li, [class*='amenities'] li, [class*='hotelFacility'] li")
      .forEach((el) => {
        const t = txt(el);
        if (t) amenities.push(t);
      });
    const images = [];
    document.querySelectorAll("img").forEach((el) => {
      const src = el.getAttribute("src") || el.getAttribute("data-src");
      if (
        src &&
        /tripcdn\.com|ak-d\.tripcdn/.test(src) &&
        /hotel|images/i.test(src) &&
        !images.includes(src)
      ) {
        images.push(src);
      }
    });
    const price = txt(document.querySelector("[class*='price'] [class*='real']")) || null;
    return {
      id: String(hotelId),
      url,
      name,
      address,
      score,
      reviewCount,
      description,
      amenities,
      images: images.slice(0, 30),
      price,
    };
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat hotel.js)" --json
```

`data.result` is a single `Hotel`:

```json
{
  "id": "106534464",
  "url": "https://www.trip.com/hotels/detail/?hotelId=106534464&checkIn=2026%2F06%2F15&checkOut=2026%2F06%2F16",
  "name": "Four Points By Sheraton Hainan Qiongzhong",
  "address": "No. 1 Bailongxi Road, Yinggen Town, Qiongzhong, Hainan, China",
  "score": null,
  "reviewCount": null,
  "description": "",
  "amenities": [],
  "images": ["https://ak-d.tripcdn.com/images/0221z12000blcn0h89AE0_R_960_660_R5_D.jpg"],
  "price": null
}
```

## 5. Output shape

Each `eval/*.js` file is a single expression that returns a JSON string, kept in lockstep with the
selectors in [`../nodejs/trip.mjs`](../nodejs/trip.mjs):

| Extractor | Returns |
| --- | --- |
| `search.js` | list of `SearchResult` |
| `hotel.js` | one `Hotel` |

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in
[`results/`](results/).
