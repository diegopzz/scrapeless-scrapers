# Redbubble — CLI surface

Scrape Redbubble product and search results pages from the command line with the
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
in-page extractor. Start with a product page.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name redbubble-cli --ttl 300 --proxy-country US --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate, then wait for the JSON-LD block
scrapeless-scraping-browser --session-id "$SID" open "https://www.redbubble.com/i/sticker/Everything-s-good-cat-by-blah707/43977882/7sgk"
scrapeless-scraping-browser --session-id "$SID" wait 'script[type="application/ld+json"]'

# run the in-page extractor — its JSON comes back in data.result
# save the product extractor (a single expression returning a JSON string)
cat > product.js <<'JS'
// In-page extractor for a Redbubble product detail page.
// Returns a JSON string — a single Product (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const url = location.href;

    const clean = (value) => {
      if (value == null) return null;
      const v = String(value).replace(/\s+/g, " ").trim();
      return v || null;
    };
    const toNumber = (value) => {
      if (value == null) return null;
      const n = parseFloat(String(value).replace(/[^\d.\-]/g, ""));
      return Number.isFinite(n) ? n : null;
    };
    const shortAvailability = (value) => {
      if (typeof value !== "string") return null;
      return value.includes("/") ? value.split("/").pop() : value;
    };
    const PDP_URL_RE = /\/i\/([^/]+)\/([^/]+?)(?:-by-([^/]+))?\/(\d+)\/[a-z0-9]+/i;
    const parsePdpUrl = (u) => {
      if (!u) return { medium: null, artist: null, workId: null };
      const m = String(u).match(PDP_URL_RE);
      if (!m) return { medium: null, artist: null, workId: null };
      return { medium: m[1] || null, artist: m[3] || null, workId: m[4] || null };
    };
    const typeMatches = (node, wanted) => {
      const t = node["@type"];
      if (typeof t === "string") return t === wanted;
      if (Array.isArray(t)) return t.includes(wanted);
      return false;
    };

    let next = null;
    const nextNode = document.querySelector("script#__NEXT_DATA__");
    if (nextNode) {
      try { next = JSON.parse(nextNode.textContent); } catch (e) {}
    }
    const pp = next?.props?.pageProps ?? {};

    let ld = {};
    const ldBlocks = Array.from(
      document.querySelectorAll('script[type="application/ld+json"]')
    ).map((el) => el.textContent);
    outer: for (const raw of ldBlocks) {
      if (!raw || !raw.trim()) continue;
      let data;
      try { data = JSON.parse(raw); } catch (e) { continue; }
      const nodes = Array.isArray(data) ? data : [data];
      for (const node of nodes) {
        if (node && typeof node === "object" && typeMatches(node, "Product")) {
          ld = node;
          break outer;
        }
      }
    }

    const offer = (ld.offers && typeof ld.offers === "object")
      ? (Array.isArray(ld.offers) ? (ld.offers[0] ?? {}) : ld.offers)
      : {};
    const rating = (ld.aggregateRating && typeof ld.aggregateRating === "object") ? ld.aggregateRating : {};

    let images = [];
    if (typeof ld.image === "string") images = [ld.image];
    else if (Array.isArray(ld.image)) images = ld.image.filter(Boolean).map(String);

    const { medium, artist, workId } = parsePdpUrl(url);
    const item = pp.initialInventoryItem ?? {};
    const reviewSummary = pp.reviewSummary ?? {};

    const price = toNumber(item?.price?.amount ?? offer.price);
    const currency = item?.price?.currency ?? offer.priceCurrency ?? null;

    let ratingValue = rating.ratingValue != null ? Number(rating.ratingValue) : null;
    if (ratingValue == null && reviewSummary.rating != null) {
      ratingValue = Number(reviewSummary.rating);
    }
    let reviewCount = rating.ratingCount != null ? parseInt(rating.ratingCount, 10) : null;
    if (reviewCount == null && rating.reviewCount != null) {
      reviewCount = parseInt(rating.reviewCount, 10);
    }
    if (reviewCount == null && reviewSummary.count != null) {
      reviewCount = parseInt(reviewSummary.count, 10);
    }

    return {
      id: workId || (item?.workId != null ? String(item.workId) : ""),
      url,
      name: clean(ld.name) || "",
      description: clean(ld.description),
      medium,
      artist,
      price: Number.isFinite(price) ? price : null,
      priceCurrency: currency,
      availability: shortAvailability(offer.availability),
      images,
      rating: Number.isFinite(ratingValue) ? ratingValue : null,
      reviewCount: Number.isFinite(reviewCount) ? reviewCount : null,
    };
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat product.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

The extractor reads the PDP's JSON-LD `Product` block plus extras from `__NEXT_DATA__`.
`data.result` is a single `Product`:

```json
{
  "id": "43977882",
  "url": "https://www.redbubble.com/i/sticker/Everything-s-good-cat-by-blah707/43977882/7sgk",
  "name": "Everything's good cat Sticker",
  "medium": "sticker",
  "artist": "blah707",
  "price": 2.87,
  "priceCurrency": "USD",
  "availability": "InStock",
  "images": ["https://ih1.redbubble.net/image.1030459700.7882/..."],
  "rating": 4.8,
  "reviewCount": 3156
}
```

## 4. Scrape a search results page

Reuse the same session — just `open` a `/shop/<query>` URL and wait for the Next.js data script.

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://www.redbubble.com/shop/cat"
scrapeless-scraping-browser --session-id "$SID" wait "script#__NEXT_DATA__"
# save the search extractor (a single expression returning a JSON string)
cat > search.js <<'JS'
// In-page extractor for a Redbubble search results page.
// Returns a JSON string — a list of SearchResult (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const clean = (value) => {
      if (value == null) return null;
      const v = String(value).replace(/\s+/g, " ").trim();
      return v || null;
    };
    const toNumber = (value) => {
      if (value == null) return null;
      const n = parseFloat(String(value).replace(/[^\d.\-]/g, ""));
      return Number.isFinite(n) ? n : null;
    };
    const PDP_URL_RE = /\/i\/([^/]+)\/([^/]+?)(?:-by-([^/]+))?\/(\d+)\/[a-z0-9]+/i;
    const parsePdpUrl = (u) => {
      if (!u) return { medium: null, artist: null, workId: null };
      const m = String(u).match(PDP_URL_RE);
      if (!m) return { medium: null, artist: null, workId: null };
      return { medium: m[1] || null, artist: m[3] || null, workId: m[4] || null };
    };

    let next = null;
    const nextNode = document.querySelector("script#__NEXT_DATA__");
    if (nextNode) {
      try { next = JSON.parse(nextNode.textContent); } catch (e) {}
    }
    const results = next?.props?.pageProps?.results ?? [];
    const items = [];

    for (const row of results) {
      const inv = row?.inventoryItem ?? {};
      const work = inv.work ?? {};
      const url = inv.productPageUrl || (inv.productPageUrls?.url ?? "");
      const { medium, artist, workId } = parsePdpUrl(url);
      const id = workId || (inv.workId != null ? String(inv.workId) : (work.id ?? ""));
      const previews = inv.previewSet?.previews ?? [];
      const image = previews.length ? String(previews[0].url ?? "") || null : null;
      const price = toNumber(inv.price?.amount);
      items.push({
        id: String(id || ""),
        url: url || "",
        name: clean(work.title) || "",
        artist: artist || clean(work.artistUsername) || null,
        medium,
        image,
        price: Number.isFinite(price) ? price : null,
        priceCurrency: inv.price?.currency ?? null,
      });
    }

    if (!items.length) {
      // DOM fallback — pull anchors + nearby price strings.
      document.querySelectorAll('a[href*="/i/"]').forEach((el) => {
        const href = el.getAttribute("href") || "";
        if (!/\/i\/[^/]+\//.test(href)) return;
        const abs = href.startsWith("http") ? href : `https://www.redbubble.com${href}`;
        const { medium, artist, workId } = parsePdpUrl(abs);
        if (!workId) return;
        if (items.find((x) => x.id === workId)) return;
        const card = el.closest("div");
        const name = clean(card?.querySelector("h3, h2")?.textContent) ||
          clean(el.getAttribute("aria-label")) || "";
        const priceText = clean(card?.querySelector('[class*="Price_"]')?.textContent);
        const price = toNumber(priceText);
        const image = card?.querySelector("img")?.getAttribute("src") || null;
        items.push({
          id: workId,
          url: abs,
          name,
          artist,
          medium,
          image: image || null,
          price: Number.isFinite(price) ? price : null,
          priceCurrency: priceText && priceText.includes("$") ? "USD" : null,
        });
      });
    }

    return items;
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat search.js)" --json
```

`data.result` is a list of `SearchResult`:

```json
[
  {
    "id": "43977882",
    "url": "https://www.redbubble.com/i/sticker/Everything-s-good-cat-by-blah707/43977882/7sgk",
    "name": "Everything's good cat",
    "artist": "blah707",
    "medium": "sticker",
    "image": "https://ih1.redbubble.net/image.1030459700.7882/...",
    "price": 2.99,
    "priceCurrency": "USD"
  }
]
```

## 5. Output shape

Each `eval/*.js` file is a single expression that returns a JSON string, kept in lockstep with the
selectors in [`../nodejs/redbubble.mjs`](../nodejs/redbubble.mjs):

| Extractor | Returns |
| --- | --- |
| `product.js` | one `Product` |
| `search.js` | list of `SearchResult` |

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in
[`results/`](results/).
