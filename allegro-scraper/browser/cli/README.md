# Allegro — CLI surface

Scrape Allegro listing and product pages from the command line with the
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
in-page extractor. Start with a listing (search) page.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name allegro-cli --ttl 300 --proxy-country PL --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate, then wait for the result articles to render
scrapeless-scraping-browser --session-id "$SID" open "https://allegro.pl/listing?string=iphone&p=1"
scrapeless-scraping-browser --session-id "$SID" wait "article"

# run the in-page extractor — its JSON comes back in data.result
# save the search extractor (a single expression returning a JSON string)
cat > search.js <<'JS'
// In-page extractor for an Allegro listing (search results) page.
// Returns a JSON string — a SearchPage (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    // Extract a balanced JSON object starting at index `start` (must point at '{').
    function readJsonObject(text, start) {
      let depth = 0;
      let inStr = false;
      let esc = false;
      for (let i = start; i < text.length; i++) {
        const ch = text[i];
        if (inStr) {
          if (esc) {
            esc = false;
            continue;
          }
          if (ch === "\\") {
            esc = true;
            continue;
          }
          if (ch === '"') inStr = false;
          continue;
        }
        if (ch === '"') {
          inStr = true;
          continue;
        }
        if (ch === "{") depth++;
        else if (ch === "}") {
          depth--;
          if (depth === 0) return text.slice(start, i + 1);
        }
      }
      return null;
    }

    function listingState() {
      let found = null;
      const scripts = Array.from(document.querySelectorAll("script"));
      for (const el of scripts) {
        const text = el.textContent || "";
        const idx = text.indexOf('"__listing_StoreState"');
        if (idx === -1) continue;
        let cursor = text.indexOf(":", idx) + 1;
        while (cursor < text.length && /\s/.test(text[cursor])) cursor++;
        if (text[cursor] !== "{") continue;
        const obj = readJsonObject(text, cursor);
        if (!obj) continue;
        try {
          found = JSON.parse(obj);
          break;
        } catch (e) {}
      }
      return found;
    }

    function searchMeta() {
      let found = null;
      const boxes = Array.from(
        document.querySelectorAll("script[data-serialize-box-id]")
      );
      for (const el of boxes) {
        const text = el.textContent || "";
        if (!text.includes("searchMeta")) continue;
        try {
          const data = JSON.parse(text);
          const meta = data?.props?.searchMeta ?? data?.searchMeta;
          if (meta && typeof meta === "object") {
            found = meta;
            break;
          }
        } catch (e) {}
      }
      if (found) return found;
      const scripts = Array.from(document.querySelectorAll("script"));
      for (const el of scripts) {
        const text = el.textContent || "";
        const idx = text.indexOf('"searchMeta"');
        if (idx === -1) continue;
        let cursor = text.indexOf(":", idx) + 1;
        while (cursor < text.length && /\s/.test(text[cursor])) cursor++;
        if (text[cursor] !== "{") continue;
        const obj = readJsonObject(text, cursor);
        if (!obj) continue;
        try {
          found = JSON.parse(obj);
          break;
        } catch (e) {}
      }
      return found;
    }

    function normaliseTitle(title) {
      if (typeof title === "string") return title;
      if (title && typeof title === "object") return title.text ?? "";
      return "";
    }

    function normalisePrice(price) {
      if (!price || typeof price !== "object") return null;
      const main = price.mainPrice ?? price;
      if (!main || typeof main !== "object") return null;
      const amount = main.amount ?? null;
      const currency = main.currency ?? null;
      if (amount == null && currency == null) return null;
      return { amount, currency };
    }

    function firstPhoto(photos) {
      if (!Array.isArray(photos) || !photos.length) return null;
      const p = photos[0];
      if (!p) return null;
      if (typeof p === "string") return p;
      return p.url ?? p.medium ?? p.original ?? p.small ?? null;
    }

    function decanonicaliseOfferUrl(url) {
      if (typeof url !== "string" || !url) return url ?? "";
      try {
        const u = new URL(url);
        if (u.pathname.startsWith("/events/clicks")) {
          const redirect = u.searchParams.get("redirect");
          if (redirect) return decodeURIComponent(redirect);
        }
      } catch (e) {}
      return url;
    }

    const state = listingState() ?? {};
    const elements = Array.isArray(state?.items?.elements)
      ? state.items.elements
      : [];
    const products = [];
    for (const el of elements) {
      if (!el || typeof el !== "object") continue;
      const price = normalisePrice(el.price);
      products.push({
        product_id: el.productId ?? el.product_id ?? el.id ?? "",
        offer_id: el.offerId ?? el.offer_id ?? "",
        title: normaliseTitle(el.title),
        price,
        currency: price?.currency ?? null,
        url: decanonicaliseOfferUrl(el.url ?? ""),
        image: firstPhoto(el.photos),
        seller: el.seller ?? null,
        delivery_info: el.deliveryInfo ?? el.delivery ?? null,
      });
    }
    const meta = searchMeta() ?? state?.searchMeta ?? {};
    return {
      products,
      products_count: products.length,
      total_pages: meta.lastAvailablePage ?? null,
      total_count: meta.totalCount ?? null,
    };
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat search.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a `SearchPage` — `{ products, scraped_pages, products_count, total_pages, total_count }`:

```json
{
  "products": [
    {
      "product_id": "bf6d4ad1-0195-4455-93a2-f80d5d648b54",
      "offer_id": "17854601441",
      "title": "Szkło hartowane Bizon do Apple iPhone 17 2 szt.",
      "price": { "amount": "46.55", "currency": "PLN" },
      "currency": "PLN",
      "url": "https://allegro.pl/oferta/szklo-hartowane-do-iphone-17-...",
      "image": "https://a.allegroimg.com/s360/...",
      "seller": { "title": "Oficjalny sklep", "superSeller": true },
      "delivery_info": { "text": "darmowa dostawa" }
    }
  ],
  "products_count": 60
}
```

## 4. Scrape a product page

Reuse the same session — just `open` a product URL and wait for the `h1` title.

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://allegro.pl/produkt/telefon-apple-iphone-17-8-256gb-5g-czarny-ffd22d9a-7e19-4bc3-98ce-d968b0669f01"
scrapeless-scraping-browser --session-id "$SID" wait "h1"
# save the product extractor (a single expression returning a JSON string)
cat > product.js <<'JS'
// In-page extractor for an Allegro product (offer / produkt) page.
// Returns a JSON string — a single Product (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    function boxPayload(needle) {
      let found = null;
      const boxes = Array.from(
        document.querySelectorAll("script[data-serialize-box-id]")
      );
      for (const el of boxes) {
        const text = el.textContent || "";
        if (!text.includes(needle)) continue;
        try {
          found = JSON.parse(text);
          break;
        } catch (e) {}
      }
      return found;
    }

    const txt = (node) => (node?.textContent || "").trim();

    const priceBox = boxPayload("formattedPrice") ?? {};
    // The price box wraps the actual price subtree under `.price`; emit just that.
    const price =
      priceBox &&
      typeof priceBox === "object" &&
      priceBox.price &&
      typeof priceBox.price === "object"
        ? priceBox.price
        : priceBox;
    const galleryBox =
      boxPayload("galleryItems") ?? boxPayload("gallery") ?? {};
    const seller = boxPayload("sellerName") ?? {};

    const galleryItems = Array.isArray(galleryBox.galleryItems)
      ? galleryBox.galleryItems
      : Array.isArray(galleryBox.images)
      ? galleryBox.images
      : [];
    const images = [];
    for (const img of galleryItems) {
      if (!img) continue;
      if (typeof img === "string") {
        images.push(img);
        continue;
      }
      const url = img.original ?? img.embeded ?? img.url ?? img.thumbnail ?? null;
      if (url) images.push(url);
    }

    // Rating lives in the aggregateRating box (`{value, label, count}`), and in a
    // JSON-LD `aggregateRating.ratingValue` block for older flows.
    let rating = null;
    const ratingBox = boxPayload("aggregateRating");
    if (
      ratingBox &&
      ratingBox.aggregateRating &&
      ratingBox.aggregateRating.value != null
    ) {
      rating = String(ratingBox.aggregateRating.value);
    }
    if (!rating) {
      const scripts = Array.from(document.querySelectorAll("script"));
      for (const el of scripts) {
        const text = el.textContent || "";
        if (!text.includes("aggregateRating")) continue;
        try {
          const data = JSON.parse(text);
          const agg = data?.aggregateRating;
          if (agg && agg.ratingValue !== undefined && agg.ratingValue !== null) {
            rating = String(agg.ratingValue);
            break;
          }
        } catch (e) {}
      }
    }

    const title = txt(document.querySelector("h1"));
    const specifications = [];
    document
      .querySelectorAll(
        '[data-role="product-parameters"] li, .product-parameters li'
      )
      .forEach((row) => {
        const spans = row.querySelectorAll("span");
        const name = txt(spans[0]);
        const value = txt(spans[1]);
        if (name) specifications.push({ name, value });
      });
    if (!specifications.length) {
      const paramsBox =
        boxPayload("productParameters") ?? boxPayload("parameters");
      const groups = paramsBox?.groups ?? paramsBox?.parameters ?? [];
      if (Array.isArray(groups)) {
        for (const group of groups) {
          const items = Array.isArray(group?.parameters)
            ? group.parameters
            : Array.isArray(group?.items)
            ? group.items
            : [];
          for (const it of items) {
            const name = it?.name ?? it?.label ?? null;
            const value =
              it?.value ??
              (Array.isArray(it?.values) ? it.values.join(", ") : null);
            if (name)
              specifications.push({
                name: String(name),
                value: value == null ? "" : String(value),
              });
          }
        }
      }
    }

    const shipping_info =
      boxPayload("deliveryOptions") ?? boxPayload("shipping") ?? null;
    const allegro_smart_badge =
      document.querySelectorAll(
        '[data-role="smart-badge"], [aria-label*="Smart"]'
      ).length > 0 ||
      /allegro smart!/i.test(document.documentElement.outerHTML);

    return {
      title,
      price,
      images,
      shipping_info,
      rating,
      specifications,
      seller,
      reviews: [],
      allegro_smart_badge,
    };
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat product.js)" --json
```

`data.result` is a `Product` object:

```json
{
  "title": "Telefon Apple iPhone 17 8 GB / 256 GB 5G Czarny",
  "price": { "formattedPrice": "3520,00 zł", "currency": "PLN" },
  "images": ["https://a.allegroimg.com/..."],
  "specifications": [{ "name": "...", "value": "..." }],
  "allegro_smart_badge": true
}
```

## 5. Output shape

Each `eval/*.js` file is a single expression that returns a JSON string, kept in lockstep with the
selectors in [`../nodejs/allegro.mjs`](../nodejs/allegro.mjs). Allegro embeds listing/product state
inside `<script data-serialize-box-id>` blobs and a `__listing_StoreState` inline object, so the
extractors balance braces themselves to lift those JSON subtrees.

| Extractor | Returns |
| --- | --- |
| `search.js` | one `SearchPage` |
| `product.js` | one `Product` |

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in
[`results/`](results/).

## Notes

- Set `proxyCountry` to `PL` at session creation — Allegro gates listing/product state behind a
  Polish residential check, and Polish characters in titles/sellers are preserved verbatim.
