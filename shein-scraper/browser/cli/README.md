# SHEIN — CLI surface

Scrape SHEIN search and product pages from the command line with the
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
scrapeless-scraping-browser new-session --name shein-cli --ttl 300 --proxy-country US --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate, then wait for the product title to render
scrapeless-scraping-browser --session-id "$SID" open "https://us.shein.com/Solid-Pattern-Crop-Tank-Top-p-12042156.html"
scrapeless-scraping-browser --session-id "$SID" wait "h1"

# run the in-page extractor — its JSON comes back in data.result.
# The extractor JS is the PRODUCT_JS heredoc; paste it as the eval argument.
# save the product extractor (a single expression returning a JSON string)
cat > product.js <<'JS'
// In-page extractor for a SHEIN product detail page.
// Returns a JSON string — a single Product (see ../../../DATA_MODEL.md).
//
// Mirrors parseProduct in ../nodejs/shein.mjs. SHEIN bounces dead PDPs (and
// most bot-flagged sessions) back to the homepage — when the title is missing,
// throw so the run script doesn't emit a hollow stub.
JSON.stringify(
  (function () {
    const DEFAULT_HOST = "https://us.shein.com";

    function text$(el) {
      return ((el?.textContent || "").replace(/\s+/g, " ").trim()) || null;
    }
    function uniq(arr) {
      return Array.from(new Set(arr.filter(Boolean)));
    }
    function toFloat(t) {
      if (!t) return null;
      const m = String(t).replace(/[^0-9.]/g, "");
      if (!m) return null;
      const n = parseFloat(m);
      return Number.isNaN(n) ? null : n;
    }
    function toInt(t) {
      if (!t) return null;
      const m = String(t).replace(/[^0-9]/g, "");
      if (!m) return null;
      const n = parseInt(m, 10);
      return Number.isNaN(n) ? null : n;
    }
    function idFromUrl(url) {
      if (!url) return "";
      const m = url.match(/-p-(\d+)\.html/);
      if (m) return m[1];
      const m2 = url.match(/\/(\d{8,})\.html/);
      if (m2) return m2[1];
      return "";
    }
    function attr(sel, name) {
      return document.querySelector(sel)?.getAttribute(name) || null;
    }
    function firstText(selector) {
      const el = document.querySelector(selector);
      return el ? text$(el) : null;
    }

    const url = location.href;

    const title =
      text$(document.querySelector("h1")) ||
      firstText(
        "[class*='product-intro__head-name'], [class*='product-name'], [data-name='product-title']"
      ) ||
      attr("meta[property='og:title']", "content") ||
      "";

    if (!title) {
      const pageTitle = (document.querySelector("title")?.textContent || "").trim();
      const hint = /Women.s.{0,3}Men.s Clothing,?\s*Shop Online Fashion/i.test(pageTitle)
        ? "bounced to homepage"
        : "missing product fields";
      throw new Error(`shein: ${hint} (anti-bot block or retired SKU) — ${url}`);
    }

    const price =
      firstText(
        "[class*='product-intro__head-mainprice'], [class*='from-skc'] [class*='price'], [class*='price-content'] .from"
      ) ||
      firstText("[class*='product-price'], [class*='sale-price']") ||
      null;
    const originalPrice =
      firstText(
        "[class*='product-intro__head-original-price'], [class*='product-intro__head-discount'] del, del[class*='retail']"
      ) || null;
    const discount =
      firstText(
        "[class*='product-intro__head-discount'], [class*='discount-badge']"
      ) || null;
    const currency =
      attr("meta[itemprop='priceCurrency']", "content") ||
      attr("meta[property='og:price:currency']", "content") ||
      null;

    const rating = toFloat(
      firstText(
        "[class*='ProductReviews_score'], [class*='rating-star'] [class*='value'], .score-num"
      )
    );
    const reviews = toInt(
      firstText(
        "[class*='ProductReviews_count'], [class*='review-count'], .review-num"
      )
    );

    const galleryImgs = Array.from(
      document.querySelectorAll(
        "[class*='product-intro__main-img-pic'] img, [class*='product-intro__thumbs'] img, [class*='gallery'] img, [class*='product-image'] img"
      )
    ).map(
      (e) =>
        e.getAttribute("src") ||
        e.getAttribute("data-src") ||
        e.getAttribute("data-srcset")
    );
    const ogImgs = Array.from(
      document.querySelectorAll("meta[property='og:image']")
    ).map((e) => e.getAttribute("content"));
    const images = uniq([...galleryImgs, ...ogImgs])
      .map((u) => (u && u.startsWith("//") ? "https:" + u : u))
      .filter(Boolean);

    const color =
      firstText(
        "[class*='product-intro__color-block'][class*='active'] + [class*='color-name'], [class*='current-color-name']"
      ) || null;
    const sizes = uniq(
      Array.from(
        document.querySelectorAll(
          "[class*='product-intro__sizes-radio'] [class*='size-list__item'], [class*='product-intro__size-radio'] [class*='size'], [class*='size-radio'] [class*='item']"
        )
      ).map((e) => text$(e))
    );

    const brand =
      firstText("[class*='product-intro__head-brand'], a[class*='brand-link']") ||
      attr("meta[property='og:brand']", "content") ||
      null;
    const availability =
      attr("meta[itemprop='availability']", "content") ||
      firstText("[class*='out-of-stock'], [class*='sold-out']") ||
      null;
    const description =
      attr("meta[name='description']", "content") ||
      attr("meta[property='og:description']", "content") ||
      null;
    const categories = uniq(
      Array.from(
        document.querySelectorAll(
          "[class*='breadcrumb'] a, [class*='crumb'] a, [class*='c-breadcrumb'] a"
        )
      ).map((e) => text$(e))
    );

    return {
      id: String(idFromUrl(url) || ""),
      url,
      title: title || "",
      brand,
      price,
      originalPrice,
      discount,
      currency,
      rating,
      reviews,
      images,
      color,
      sizes,
      availability,
      description,
      categories,
    };
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat product.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a `Product` object:

```json
{
  "id": "12042156",
  "url": "https://us.shein.com/Solid-Pattern-Crop-Tank-Top-p-12042156.html",
  "title": "Solid Pattern Crop Tank Top",
  "brand": null,
  "price": "$5.49",
  "originalPrice": null,
  "discount": null,
  "currency": "USD",
  "rating": null,
  "reviews": null,
  "images": ["https://img.ltwebstatic.com/images3/.../P0.jpg"],
  "color": null,
  "sizes": ["XS", "S", "M", "L"],
  "availability": null,
  "description": null,
  "categories": []
}
```

## 4. Scrape a search page

Reuse the same session — just `open` a search URL and wait for the product cards. SHEIN search URLs
are `https://us.shein.com/pdsearch/<query-slug>/?page=<n>`.

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://us.shein.com/pdsearch/summer-dress/?page=1"
scrapeless-scraping-browser --session-id "$SID" wait "section[class*='product-card'], div[class*='product-card']"
# save the search extractor (a single expression returning a JSON string)
cat > search.js <<'JS'
// In-page extractor for a SHEIN search results page.
// Returns a JSON string — a list of SearchResult (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const DEFAULT_HOST = "https://us.shein.com";

    function text$(node) {
      return (node?.textContent || "").replace(/\s+/g, " ").trim() || null;
    }
    function toFloat(t) {
      if (!t) return null;
      const m = String(t).replace(/[^0-9.]/g, "");
      if (!m) return null;
      const n = parseFloat(m);
      return Number.isNaN(n) ? null : n;
    }
    function idFromUrl(url) {
      if (!url) return "";
      const m = url.match(/-p-(\d+)\.html/);
      if (m) return m[1];
      const m2 = url.match(/\/(\d{8,})\.html/);
      if (m2) return m2[1];
      return "";
    }

    const out = [];
    const seen = new Set();
    const cards = [
      "section[class*='product-card']",
      "section[data-locate-key]",
      "div[class*='product-list-item']",
      "div[class*='S-product-card']",
      "div[class*='product-card']",
      "li[class*='product-card']",
      "a[href*='-p-'][href$='.html']",
    ];
    for (const sel of cards) {
      document.querySelectorAll(sel).forEach((el) => {
        const isAnchor = el.tagName === "A";
        const a = isAnchor
          ? el
          : el.querySelector("a[href*='-p-'], a[href*='.html']");
        let href = a?.getAttribute("href") || "";
        if (href.startsWith("//")) href = "https:" + href;
        if (!href) return;
        if (href.startsWith("/")) href = DEFAULT_HOST + href;
        const id = idFromUrl(href);
        if (!id || seen.has(id)) return;
        seen.add(id);
        const title =
          text$(
            el.querySelector(
              "[class*='goods-title-link'], [class*='product-card__goods-name'], [class*='card-name'], a[title]"
            )
          ) ||
          a?.getAttribute("title") ||
          text$(a) ||
          "";
        const imgEl = el.querySelector("img");
        const image =
          imgEl?.getAttribute("src") || imgEl?.getAttribute("data-src") || null;
        const price =
          text$(
            el.querySelector(
              "[class*='product-card__price-sale'], [class*='product-card-sale-price'], [class*='from-skc']"
            )
          ) ||
          text$(el.querySelector("[class*='price']")) ||
          null;
        const originalPrice =
          text$(
            el.querySelector(
              "[class*='product-card__price-original'], del, [class*='retail']"
            )
          ) || null;
        const discount =
          text$(
            el.querySelector(
              "[class*='product-card__discount'], [class*='discount-badge']"
            )
          ) || null;
        const rating = toFloat(
          text$(el.querySelector("[class*='product-card__rate'], [class*='rating']"))
        );
        out.push({
          id,
          title,
          url: href,
          image: image && image.startsWith("//") ? "https:" + image : image,
          price,
          originalPrice,
          discount,
          rating,
        });
      });
    }
    return out;
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat search.js)" --json
```

`data.result` is a list of `SearchResult`:

```json
[
  {
    "id": "12345678",
    "title": "Women's Summer Floral Print Dress",
    "url": "https://us.shein.com/Womens-Summer-Floral-Print-Dress-p-12345678.html",
    "image": "https://img.ltwebstatic.com/images3/.../thumb.jpg",
    "price": "$12.99",
    "originalPrice": "$18.99",
    "discount": "-30%",
    "rating": 4.8
  }
]
```

## 5. Output shape

Each extractor (the `SEARCH_JS` / `PRODUCT_JS` extractor) is a single expression
that returns a JSON string, kept in lockstep with the selectors in
[`../nodejs/shein.mjs`](../nodejs/shein.mjs):

| Extractor    | Returns                |
| ------------ | ---------------------- |
| `SEARCH_JS`  | list of `SearchResult` |
| `PRODUCT_JS` | one `Product`          |

`SEARCH_JS` walks the rendered card grid (multiple `product-card` selector variants), dedups by the
goods id parsed from each card link, and reads price / image / rating off the card. `PRODUCT_JS`
reads the PDP `h1`, price block, gallery imagery, size radios, breadcrumb categories, and the
`og:`/`itemprop` meta tags. Full field tables — types, which are required, where each comes from —
are in [`../../DATA_MODEL.md`](../../DATA_MODEL.md).

SHEIN is aggressive about anti-bot interstitials: a flagged session can bounce a PDP back to the
homepage, in which case the extractor returns an empty `title`. Re-run, or override the sample
target (below) with a live SKU.
