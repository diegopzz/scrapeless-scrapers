# Big Lots — CLI surface

Scrape Big Lots category and product pages from the command line with the
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
in-page extractor. Start with a category (search) page.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name biglots-cli --ttl 300 --proxy-country US --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate, then wait for the WooCommerce product cards to render
scrapeless-scraping-browser --session-id "$SID" open "https://biglots.com/product-category/pets/"
scrapeless-scraping-browser --session-id "$SID" wait "li.product"

# run the in-page extractor — its JSON comes back in data.result
# save the search extractor (a single expression returning a JSON string)
cat > search.js <<'JS'
// In-page extractor for a Big Lots category (search) page.
// Returns a JSON string — a list of SearchResult (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    function clean(value) {
      if (value == null) return null;
      const v = String(value).replace(/\s+/g, " ").trim();
      return v || null;
    }

    function toNumber(value) {
      if (value == null) return null;
      const n = parseFloat(String(value).replace(/[^\d.\-]/g, ""));
      return Number.isFinite(n) ? n : null;
    }

    const items = [];
    const seen = new Set();

    document
      .querySelectorAll("li.product, li.wp-block-post.product")
      .forEach((card) => {
        // post-<id> class identifies the WP post id; fall back to data-id if present
        const classes = (card.getAttribute("class") || "").split(/\s+/);
        const postClass = classes.find((c) => /^post-\d+$/.test(c));
        const id = postClass
          ? postClass.replace("post-", "")
          : card.getAttribute("data-id") ?? "";

        const anchor = card.querySelector('a[href*="/product/"]');
        const href = anchor?.getAttribute("href") || "";
        if (!href) return;
        const url = href.startsWith("http")
          ? href
          : `https://biglots.com${href}`;
        if (seen.has(url)) return;
        seen.add(url);

        const name =
          clean(
            card.querySelector("h3 a, h2 a, h3, h2")?.textContent ||
              anchor?.getAttribute("aria-label") ||
              card.querySelector("img")?.getAttribute("alt")
          ) || "";

        const priceText = clean(
          card.querySelector(
            ".wp-block-woocommerce-product-price, .wc-block-components-product-price, .price"
          )?.textContent
        );
        const price = toNumber(priceText);

        const image =
          card.querySelector("img")?.getAttribute("src") ||
          card.querySelector("img")?.getAttribute("data-src") ||
          null;

        const category = clean(
          card.querySelector(
            ".wp-block-post-terms a, .wc-block-grid__product-category"
          )?.textContent
        );

        items.push({
          id: String(id || ""),
          url,
          name,
          image: image || null,
          price,
          priceCurrency:
            priceText && priceText.includes("$") ? "USD" : null,
          category,
        });
      });

    return items;
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
    "id": "3872",
    "url": "https://biglots.com/product/22-6-oz-dentalife-immune-support-dog-treats/",
    "name": "22.6 OZ DENTALIFE IMMUNE SUPPORT DOG TREATS",
    "image": "https://biglots.com/wp-content/uploads/2025/04/dentqalife-large-dog-immune-support-600x600.png",
    "price": 12.99,
    "priceCurrency": "USD",
    "category": "Pets"
  }
]
```

## 4. Scrape a product page

Reuse the same session — just `open` a product URL and wait for the JSON-LD block.

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://biglots.com/product/serta-jumbo-bed-pillow/"
scrapeless-scraping-browser --session-id "$SID" wait "script[type=application/ld+json]"
# save the product extractor (a single expression returning a JSON string)
cat > product.js <<'JS'
// In-page extractor for a Big Lots product detail page.
// Returns a JSON string — a single Product (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const url = location.href;

    function clean(value) {
      if (value == null) return null;
      const v = String(value).replace(/\s+/g, " ").trim();
      return v || null;
    }

    function toNumber(value) {
      if (value == null) return null;
      const n = parseFloat(String(value).replace(/[^\d.\-]/g, ""));
      return Number.isFinite(n) ? n : null;
    }

    function* iterJsonldNodes() {
      const blocks = Array.from(
        document.querySelectorAll('script[type="application/ld+json"]')
      ).map((el) => el.textContent);
      for (const raw of blocks) {
        if (!raw || !raw.trim()) continue;
        let data;
        try {
          data = JSON.parse(raw);
        } catch (e) {
          continue;
        }
        const stack = Array.isArray(data) ? [...data] : [data];
        while (stack.length) {
          const node = stack.shift();
          if (!node || typeof node !== "object") continue;
          if (Array.isArray(node["@graph"])) {
            for (const sub of node["@graph"]) stack.push(sub);
          } else {
            yield node;
          }
        }
      }
    }

    function typeMatches(node, wanted) {
      const t = node["@type"];
      if (typeof t === "string") return t === wanted;
      if (Array.isArray(t)) return t.includes(wanted);
      return false;
    }

    function pickOfferPrice(offer) {
      if (!offer || typeof offer !== "object") return null;
      if (offer.price != null) return toNumber(offer.price);
      const spec = offer.priceSpecification;
      if (Array.isArray(spec) && spec.length) return toNumber(spec[0].price);
      if (spec && typeof spec === "object") return toNumber(spec.price);
      return null;
    }

    function pickOfferCurrency(offer) {
      if (!offer || typeof offer !== "object") return null;
      if (offer.priceCurrency) return String(offer.priceCurrency);
      const spec = offer.priceSpecification;
      if (Array.isArray(spec) && spec.length)
        return spec[0].priceCurrency ?? null;
      if (spec && typeof spec === "object")
        return spec.priceCurrency ?? null;
      return null;
    }

    function shortAvailability(value) {
      if (typeof value !== "string") return null;
      return value.includes("/") ? value.split("/").pop() : value;
    }

    let ld = {};
    for (const node of iterJsonldNodes()) {
      if (typeMatches(node, "Product")) {
        ld = node;
        break;
      }
    }

    const offers = ld.offers;
    let offer = {};
    if (Array.isArray(offers) && offers.length) offer = offers[0];
    else if (offers && typeof offers === "object") offer = offers;

    let images = [];
    const imgRaw = ld.image;
    if (typeof imgRaw === "string") images = [imgRaw];
    else if (Array.isArray(imgRaw))
      images = imgRaw.filter(Boolean).map(String);
    if (!images.length) {
      images = Array.from(
        document.querySelectorAll('meta[property="og:image"]')
      )
        .map((el) => el.getAttribute("content"))
        .filter(Boolean);
    }

    const categories = [];
    document
      .querySelectorAll(
        ".woocommerce-breadcrumb a, .wp-block-woocommerce-breadcrumbs a"
      )
      .forEach((el) => {
        const t = clean(el.textContent);
        if (t && !categories.includes(t)) categories.push(t);
      });

    const sellerNode = offer.seller;
    let sellerName = null;
    if (sellerNode && typeof sellerNode === "object")
      sellerName = sellerNode.name ?? null;
    else if (typeof sellerNode === "string") sellerName = sellerNode;

    const sku = ld.sku != null ? String(ld.sku) : ld["@id"] || url;

    return {
      id: String(sku),
      url,
      name:
        clean(ld.name) ||
        clean(document.querySelector("h1")?.textContent) ||
        "",
      description:
        clean(ld.description) ||
        clean(
          document
            .querySelector('meta[name="description"]')
            ?.getAttribute("content")
        ),
      price: pickOfferPrice(offer),
      priceCurrency: pickOfferCurrency(offer),
      availability: shortAvailability(offer.availability),
      images,
      categories,
      sellerName: clean(sellerName),
    };
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat product.js)" --json
```

`data.result` is a `Product` object:

```json
{
  "id": "3876",
  "url": "https://biglots.com/product/serta-jumbo-bed-pillow/",
  "name": "SERTA JUMBO BED PILLOW",
  "description": null,
  "price": 7.99,
  "priceCurrency": "USD",
  "availability": "InStock",
  "images": ["https://biglots.com/wp-content/uploads/2025/04/large-serta-pillow.png"],
  "categories": [],
  "sellerName": "Big Lots"
}
```

## 5. Output shape

Each `eval/*.js` file is a single expression that returns a JSON string, kept in lockstep with the
selectors in [`../nodejs/biglots.mjs`](../nodejs/biglots.mjs):

| Extractor | Returns |
| --- | --- |
| `search.js` | list of `SearchResult` |
| `product.js` | one `Product` |

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in
[`results/`](results/).

## Notes

- biglots.com runs WordPress + WooCommerce — every PDP emits a JSON-LD `Product` block, and
  category pages render WooCommerce `li.product` cards.
