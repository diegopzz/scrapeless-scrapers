# Depop — CLI surface

Scrape Depop product, search, and shop pages from the command line with the
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
scrapeless-scraping-browser new-session --name depop-cli --ttl 300 --proxy-country US --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate, then wait for the title or the embedded Next.js data
scrapeless-scraping-browser --session-id "$SID" open "https://www.depop.com/products/gasbiegzr-levis-jeans-size-25-light-7515/"
scrapeless-scraping-browser --session-id "$SID" wait "h1, script#__NEXT_DATA__"

# run the in-page extractor — its JSON comes back in data.result
# save the product extractor (a single expression returning a JSON string)
cat > product.js <<'JS'
// In-page extractor for a Depop product page.
// Returns a JSON string — a single Product (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const HOST = "https://www.depop.com";
    const url = location.href;

    const text$ = (node) =>
      (node?.textContent || "").replace(/\s+/g, " ").trim() || null;
    const uniq = (arr) => Array.from(new Set(arr.filter(Boolean)));
    const productSlugFromUrl = (u) => {
      if (!u) return "";
      const m = u.match(/\/products\/([^/?#]+)/);
      return m ? m[1] : "";
    };
    const sellerFromUrl = (u) => {
      if (!u) return null;
      const m = u.match(/\/products\/([^-]+)-/);
      return m ? m[1] : null;
    };

    // JSON-LD nodes (flat + @graph)
    const jsonLdNodes = () => {
      const out = [];
      document
        .querySelectorAll("script[type='application/ld+json']")
        .forEach((el) => {
          const t = el.textContent;
          if (!t) return;
          try {
            const v = JSON.parse(t);
            const arr = Array.isArray(v) ? v : [v];
            for (const n of arr) {
              if (!n || typeof n !== "object") continue;
              if (Array.isArray(n["@graph"])) {
                for (const s of n["@graph"])
                  if (s && typeof s === "object") out.push(s);
              } else {
                out.push(n);
              }
            }
          } catch (e) {}
        });
      return out;
    };
    const typeMatches = (node, wanted) => {
      const t = node["@type"];
      if (typeof t === "string") return t === wanted;
      if (Array.isArray(t)) return t.includes(wanted);
      return false;
    };

    const nodes = jsonLdNodes();
    const product = nodes.find((n) => typeMatches(n, "Product")) || {};

    const slug = productSlugFromUrl(url);

    const title =
      product.name ||
      text$(document.querySelector("h1")) ||
      document
        .querySelector("meta[property='og:title']")
        ?.getAttribute("content") ||
      "";

    const offers = Array.isArray(product.offers)
      ? product.offers[0]
      : product.offers || {};
    const price = offers?.price != null ? String(offers.price) : null;
    const currency =
      offers?.priceCurrency ||
      document
        .querySelector("meta[itemprop='priceCurrency']")
        ?.getAttribute("content") ||
      null;
    const availability =
      typeof offers?.availability === "string" ? offers.availability : null;
    const sold = !!availability && /OutOfStock|SoldOut/i.test(availability);

    const brand =
      (typeof product.brand === "object"
        ? product.brand?.name
        : product.brand) || null;
    const condition = product.itemCondition || null;
    const color = product.color || null;
    const size = product.size || null;
    const description =
      product.description ||
      document
        .querySelector("meta[property='og:description']")
        ?.getAttribute("content") ||
      null;

    const seller =
      sellerFromUrl(url) ||
      text$(
        document.querySelector(
          "a[href^='/'][class*='username'], [data-testid*='username']"
        )
      ) ||
      null;
    const sellerUrl = seller ? `${HOST}/${seller}/` : null;

    const ldImages = Array.isArray(product.image)
      ? product.image
      : product.image
      ? [product.image]
      : [];
    const images = uniq([
      ...ldImages,
      ...Array.from(
        document.querySelectorAll(
          "img[alt][src*='depop'], picture img, [class*='gallery'] img"
        )
      ).map((e) => e.getAttribute("src") || e.getAttribute("data-src")),
      ...Array.from(
        document.querySelectorAll("meta[property='og:image']")
      ).map((e) => e.getAttribute("content")),
    ])
      .map((u) => (u && u.startsWith("//") ? "https:" + u : u))
      .filter(Boolean);

    const hashtags = uniq(
      Array.from(
        document.querySelectorAll(
          "a[href*='/search/?q=%23'], a[href*='/search/?q=#']"
        )
      ).map((e) => text$(e))
    );

    return {
      id: slug || "",
      url,
      title: title || "",
      price,
      currency,
      brand,
      condition,
      size,
      color,
      description,
      images,
      seller,
      sellerUrl,
      hashtags,
      sold,
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
  "id": "gasbiegzr-levis-jeans-size-25-light-7515",
  "url": "https://www.depop.com/products/gasbiegzr-levis-jeans-size-25-light-7515/",
  "title": "Levi's Jeans Size 25 Light Blue wash '94 Baggy,...",
  "price": "10.00",
  "currency": "USD",
  "brand": "Levi's",
  "images": ["https://media-photos.depop.com/b1/222634552/3774452762_.../P0.jpg"],
  "seller": "gasbiegzr",
  "hashtags": [],
  "sold": false
}
```

## 4. Scrape a search page

Reuse the same session — `open` a search URL and wait for the product card links.

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://www.depop.com/search/?q=levi%20jeans"
scrapeless-scraping-browser --session-id "$SID" wait "a[href^='/products/']"
# save the search extractor (a single expression returning a JSON string)
cat > search.js <<'JS'
// In-page extractor for a Depop search results page.
// Returns a JSON string — a list of SearchResult (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const HOST = "https://www.depop.com";

    const text$ = (node) =>
      (node?.textContent || "").replace(/\s+/g, " ").trim() || null;
    const abs = (url) => {
      if (!url) return null;
      if (url.startsWith("//")) return "https:" + url;
      if (url.startsWith("http")) return url;
      return HOST + (url.startsWith("/") ? url : "/" + url);
    };
    const productSlugFromUrl = (u) => {
      if (!u) return "";
      const m = u.match(/\/products\/([^/?#]+)/);
      return m ? m[1] : "";
    };
    const sellerFromUrl = (u) => {
      if (!u) return null;
      const m = u.match(/\/products\/([^-]+)-/);
      return m ? m[1] : null;
    };

    const out = [];
    const seen = new Set();

    document.querySelectorAll("a[href^='/products/']").forEach((a) => {
      const href = a.getAttribute("href") || "";
      const slug = productSlugFromUrl(href);
      if (!slug || seen.has(slug)) return;
      seen.add(slug);
      const img = a.querySelector("img");
      // Cards: <li><a><img></a><p>price</p><p aria-label='Size'>S</p></li>.
      // We look both inside the <a> and at the closest list-item ancestor for
      // sibling metadata.
      const card = a.closest("li, article, div[class*='styles__']");

      const title =
        img?.getAttribute("alt") ||
        text$(
          a.querySelector("p[class*='styles__StyledProductCardTitle']")
        ) ||
        text$(a) ||
        "";
      const image =
        img?.getAttribute("src") || img?.getAttribute("data-src") || null;

      const priceNode = card?.querySelector(
        "p[aria-label='Price'], p[data-testid='product__priceAmount'], p[class*='Price']"
      );
      const origNode = card?.querySelector(
        "p[aria-label='Discounted price'], p[aria-label='original price'], s, del"
      );
      const sizeNode = card?.querySelector(
        "p[aria-label='Size'], [data-testid*='size']"
      );

      const price = text$(priceNode) || null;
      const originalPrice = text$(origNode) || null;
      const seller = sellerFromUrl(href);
      const size = text$(sizeNode) || null;

      out.push({
        id: slug,
        title,
        url: abs(href),
        image,
        price,
        originalPrice,
        seller,
        size,
      });
    });
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
    "id": "jojfu_369-levis-light-wash-distressed-jeans-b9a8",
    "title": "",
    "url": "https://www.depop.com/products/jojfu_369-levis-light-wash-distressed-jeans-b9a8/",
    "image": "https://media-photos.depop.com/b1/364990411/3774927476_.../P10.jpg",
    "price": "$2.00",
    "originalPrice": null,
    "seller": "jojfu_369",
    "size": null
  }
]
```

## 5. Scrape a shop page

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://www.depop.com/depopofficial/"
scrapeless-scraping-browser --session-id "$SID" wait "h1, script#__NEXT_DATA__"
# save the shop extractor (a single expression returning a JSON string)
cat > shop.js <<'JS'
// In-page extractor for a Depop shop / profile page.
// Returns a JSON string — a single Shop (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const HOST = "https://www.depop.com";
    const html = document.documentElement.outerHTML;
    const username =
      (location.pathname.split("/").filter(Boolean)[0] || "").trim();

    const text$ = (node) =>
      (node?.textContent || "").replace(/\s+/g, " ").trim() || null;
    const abs = (url) => {
      if (!url) return null;
      if (url.startsWith("//")) return "https:" + url;
      if (url.startsWith("http")) return url;
      return HOST + (url.startsWith("/") ? url : "/" + url);
    };
    const productSlugFromUrl = (u) => {
      if (!u) return "";
      const m = u.match(/\/products\/([^/?#]+)/);
      return m ? m[1] : "";
    };
    const sellerFromUrl = (u) => {
      if (!u) return null;
      const m = u.match(/\/products\/([^-]+)-/);
      return m ? m[1] : null;
    };
    const toFloat = (t) => {
      if (!t) return null;
      const m = String(t).replace(/[^0-9.]/g, "");
      if (!m) return null;
      const n = parseFloat(m);
      return Number.isNaN(n) ? null : n;
    };
    const toInt = (t) => {
      if (!t) return null;
      const s = String(t).replace(/[,\s]/g, "");
      let m = s.match(/(-?\d+(?:\.\d+)?)\s*([kKmM])\b/);
      if (m) {
        const n = parseFloat(m[1]);
        const mult = m[2].toLowerCase() === "k" ? 1000 : 1000000;
        return Number.isFinite(n) ? Math.round(n * mult) : null;
      }
      const digits = s.replace(/[^0-9-]/g, "");
      if (!digits) return null;
      const n = parseInt(digits, 10);
      return Number.isNaN(n) ? null : n;
    };

    // Next.js page data from `<script id="__NEXT_DATA__">`.
    let next = null;
    const ndRaw = document.querySelector("script#__NEXT_DATA__")?.textContent;
    if (ndRaw) {
      try {
        next = JSON.parse(ndRaw);
      } catch (e) {}
    }

    // Depop's streaming RSC seller payload ships inside a doubly-encoded JSON
    // chunk where each JSON quote is preceded by a literal backslash. The
    // 4-char regex source `\\\"` matches the 2 input characters `\"`.
    const RSC_BS_Q = "\\\\\"";
    const extractRscField = (haystack, key) => {
      const k = key.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const prefix = `${RSC_BS_Q}${k}${RSC_BS_Q}:`;
      let m = haystack.match(
        new RegExp(`${prefix}(true|false|null|-?\\d+(?:\\.\\d+)?)`)
      );
      if (m) {
        const v = m[1];
        if (v === "true") return true;
        if (v === "false") return false;
        if (v === "null") return null;
        return v.includes(".") ? parseFloat(v) : parseInt(v, 10);
      }
      m = haystack.match(
        new RegExp(
          `${prefix}${RSC_BS_Q}((?:(?!${RSC_BS_Q}).)*)${RSC_BS_Q}`
        )
      );
      if (m) return m[1];
      if (new RegExp(`${prefix}\\{\\}`).test(haystack)) return {};
      return null;
    };
    const extractRscSeller = (h) => {
      const re = new RegExp(
        `${RSC_BS_Q}seller${RSC_BS_Q}:\\{.{200,2000}?${RSC_BS_Q}items_sold${RSC_BS_Q}:[0-9]+`,
        "s"
      );
      const m = re.exec(h);
      return m ? m[0] : null;
    };

    // ---- parseSearch (listings on the shop page) ----
    const parseSearch = () => {
      const out = [];
      const seen = new Set();
      document.querySelectorAll("a[href^='/products/']").forEach((a) => {
        const href = a.getAttribute("href") || "";
        const slug = productSlugFromUrl(href);
        if (!slug || seen.has(slug)) return;
        seen.add(slug);
        const img = a.querySelector("img");
        const card = a.closest("li, article, div[class*='styles__']");
        const title =
          img?.getAttribute("alt") ||
          text$(
            a.querySelector("p[class*='styles__StyledProductCardTitle']")
          ) ||
          text$(a) ||
          "";
        const image =
          img?.getAttribute("src") || img?.getAttribute("data-src") || null;
        const priceNode = card?.querySelector(
          "p[aria-label='Price'], p[data-testid='product__priceAmount'], p[class*='Price']"
        );
        const origNode = card?.querySelector(
          "p[aria-label='Discounted price'], p[aria-label='original price'], s, del"
        );
        const sizeNode = card?.querySelector(
          "p[aria-label='Size'], [data-testid*='size']"
        );
        out.push({
          id: slug,
          title,
          url: abs(href),
          image,
          price: text$(priceNode) || null,
          originalPrice: text$(origNode) || null,
          seller: sellerFromUrl(href),
          size: text$(sizeNode) || null,
        });
      });
      return out;
    };

    const page = next?.props?.pageProps || {};
    const profile = page?.user || page?.shop || {};

    const rsc = extractRscSeller(html) || "";

    const rscFirstName = extractRscField(rsc, "first_name");
    const rscLastName = extractRscField(rsc, "last_name");
    const composed =
      [rscFirstName, rscLastName].filter((p) => p).join(" ").trim() || null;

    const sellerNameDom = text$(
      document.querySelector("p[class*='styles_sellerName']")
    );

    const displayName =
      profile?.displayName ||
      composed ||
      sellerNameDom ||
      text$(document.querySelector("h1")) ||
      username;

    const bio =
      profile?.bio ||
      extractRscField(rsc, "bio") ||
      text$(
        document.querySelector(
          "p[data-testid='shop__bio'], div[class*='styles_shopBio'] p"
        )
      ) ||
      null;

    const avatar =
      profile?.profileImage ||
      profile?.avatar ||
      document
        .querySelector("meta[property='og:image']")
        ?.getAttribute("content") ||
      null;

    const locationText =
      profile?.location ||
      extractRscField(rsc, "location") ||
      text$(document.querySelector("[data-testid*='location']")) ||
      null;

    let followers = toInt(profile?.followers);
    if (followers == null)
      followers = toInt(
        text$(
          document.querySelector(
            "a[href*='/followers/'] span, a[href*='/followers/']"
          )
        )
      );
    if (followers == null) followers = extractRscField(rsc, "followers");

    let following = toInt(profile?.following);
    if (following == null)
      following = toInt(
        text$(
          document.querySelector(
            "a[href*='/following/'] span, a[href*='/following/']"
          )
        )
      );
    if (following == null) following = extractRscField(rsc, "following");

    let rating = toFloat(profile?.rating);
    if (rating == null)
      rating = toFloat(
        text$(document.querySelector("[data-testid*='rating']"))
      );
    if (rating == null) rating = extractRscField(rsc, "reviews_rating");

    let reviews = toInt(profile?.reviewsCount);
    if (reviews == null)
      reviews = toInt(text$(document.querySelector("a[href*='/reviews']")));
    if (reviews == null) reviews = extractRscField(rsc, "reviews_total");

    const listings = parseSearch();

    return {
      username,
      url: `${HOST}/${username}/`,
      displayName,
      bio,
      avatar,
      location: locationText,
      followers,
      following,
      reviews,
      rating,
      listings,
    };
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat shop.js)" --json
```

`data.result` is a single `Shop`:

```json
{
  "username": "depopofficial",
  "url": "https://www.depop.com/depopofficial/",
  "displayName": "Hunter",
  "bio": "Hunter's shop",
  "followers": 0,
  "following": 0,
  "reviews": 0,
  "rating": 0,
  "listings": []
}
```

## 6. Output shape

Each `eval/*.js` file is a single expression that returns a JSON string, kept in lockstep with the
selectors in [`../nodejs/depop.mjs`](../nodejs/depop.mjs):

| Extractor | Returns |
| --- | --- |
| `product.js` | one `Product` |
| `search.js` | list of `SearchResult` |
| `shop.js` | one `Shop` |

`product.js` reads the `application/ld+json` Product tag; `search.js` reads the rendered card grid;
`shop.js` reads `<script id="__NEXT_DATA__">` plus the streaming RSC seller chunk, with DOM
fallbacks. Full field tables are in [`../../DATA_MODEL.md`](../../DATA_MODEL.md); sample payloads
are in [`results/`](results/).
