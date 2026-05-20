# Worten — CLI surface

Scrape Worten product and category pages from the command line with the
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
scrapeless-scraping-browser new-session --name worten-cli --ttl 300 --proxy-country PT --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate, then wait for the schema.org ld+json blob to render
scrapeless-scraping-browser --session-id "$SID" open "https://www.worten.pt/produtos/iphone-15-pro-max-apple-6-7-256-gb-titanio-branco-7851167"
scrapeless-scraping-browser --session-id "$SID" wait "script[type='application/ld+json']"

# run the in-page extractor — its JSON comes back in data.result
# save the product extractor (a single expression returning a JSON string)
cat > product.js <<'JS'
// In-page extractor for a Worten product (/produtos/<slug>-<id>) page.
// Returns a JSON string — a single Product (see ../../../DATA_MODEL.md).
// Mirrors extractLdJsonBlocks() + parseProduct() in ../nodejs/worten.mjs:
// reads the schema.org Product ld+json blob plus the BreadcrumbList ld+json.
JSON.stringify(
  (function () {
    const ORIGIN = "https://www.worten.pt";
    const url = location.href;

    const blocks = [];
    document
      .querySelectorAll('script[type="application/ld+json"]')
      .forEach((el) => {
        const txt = el.textContent;
        if (!txt) return;
        try {
          blocks.push(JSON.parse(txt));
        } catch (e) {}
      });

    let prod = null;
    for (const b of blocks) {
      const t = String((b && b["@type"]) ?? "").toLowerCase();
      if (t === "product") {
        prod = b;
        break;
      }
    }
    if (!prod) throw new Error("could not find Product ld+json on page");

    let breadcrumbLd = null;
    for (const b of blocks) {
      if (b && b["@type"] === "BreadcrumbList") {
        breadcrumbLd = b;
        break;
      }
    }
    const breadcrumb = ((breadcrumbLd && breadcrumbLd.itemListElement) ?? []).map(
      (b) => ({
        name: (b && b.name) ?? null,
        url: (b && b.item) ?? null,
        position: (b && b.position) ?? null,
      })
    );

    const absUrl = (u) => {
      if (!u) return null;
      if (u.startsWith("//")) return `https:${u}`;
      if (u.startsWith("/")) return `${ORIGIN}${u}`;
      return u;
    };

    const offer = Array.isArray(prod.offers) ? prod.offers[0] : prod.offers;
    const rating = prod.aggregateRating;

    return {
      sku: String(prod.sku ?? ""),
      name: prod.name ?? "",
      brand: (prod.brand && prod.brand.name) ?? null,
      description: prod.description ?? null,
      image: absUrl(
        typeof prod.image === "string" ? prod.image : prod.image && prod.image[0]
      ),
      price: offer && offer.price != null ? String(offer.price) : null,
      priceCurrency: (offer && offer.priceCurrency) ?? null,
      availability: (offer && offer.availability) ?? null,
      ratingValue:
        rating && rating.ratingValue != null ? Number(rating.ratingValue) : null,
      reviewCount:
        rating && rating.reviewCount != null ? Number(rating.reviewCount) : null,
      url: absUrl(prod.url) ?? url,
      breadcrumb,
    };
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat product.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a `Product` object, parsed from the schema.org Product + BreadcrumbList `ld+json`
blobs:

```json
{
  "sku": "7851167",
  "name": "iPhone 15 Pro Max APPLE (6.7'' - 256 GB - Titânio Branco)",
  "brand": "APPLE",
  "priceCurrency": "EUR",
  "url": "https://www.worten.pt/produtos/iphone-15-pro-max-apple-6-7-256-gb-titanio-branco-7851167",
  "breadcrumb": [{ "name": "...", "url": "...", "position": 1 }]
}
```

## 4. Scrape a category page

Reuse the same session — just `open` a category URL and wait for the heading.

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://www.worten.pt/promocoes/pequenos-eletrodomesticos"
scrapeless-scraping-browser --session-id "$SID" wait "h1"
# save the category extractor (a single expression returning a JSON string)
cat > category.js <<'JS'
// In-page extractor for a Worten category landing page.
// Returns a JSON string — a single Category (see ../../../DATA_MODEL.md).
// Mirrors extractLdJsonBlocks() + parseCategory() in ../nodejs/worten.mjs:
// category result tiles render client-side behind a Turnstile gate, so only
// the breadcrumb / heading / meta served in the SSR HTML are captured.
JSON.stringify(
  (function () {
    const url = location.href;

    const blocks = [];
    document
      .querySelectorAll('script[type="application/ld+json"]')
      .forEach((el) => {
        const txt = el.textContent;
        if (!txt) return;
        try {
          blocks.push(JSON.parse(txt));
        } catch (e) {}
      });

    let breadcrumbLd = null;
    for (const b of blocks) {
      if (b && b["@type"] === "BreadcrumbList") {
        breadcrumbLd = b;
        break;
      }
    }
    const breadcrumb = ((breadcrumbLd && breadcrumbLd.itemListElement) ?? []).map(
      (b) => ({
        name: (b && b.name) ?? null,
        url: (b && b.item) ?? null,
        position: (b && b.position) ?? null,
      })
    );

    return {
      name: (document.querySelector("h1")?.textContent ?? "").trim(),
      title: (document.querySelector("title")?.textContent ?? "").trim() || null,
      description:
        document
          .querySelector("meta[name='description']")
          ?.getAttribute("content") ?? null,
      url,
      breadcrumb,
    };
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat category.js)" --json
```

`data.result` is a `Category` object. Category result tiles render client-side behind a Turnstile
gate, so only the breadcrumb / heading / meta served in the SSR HTML are captured:

```json
{
  "name": "Promoções em Pequenos Eletrodomésticos",
  "title": "Promoções em Pequenos Eletrodomésticos | Worten.pt",
  "description": "Aproveita os melhores descontos em Eletrodomésticos: ...",
  "url": "https://www.worten.pt/promocoes/pequenos-eletrodomesticos",
  "breadcrumb": [{ "name": "Promoções e Destaques", "url": "https://www.worten.pt/promocoes", "position": 1 }]
}
```

## 5. Output shape

Each `eval/*.js` file is a single expression that returns a JSON string, kept in lockstep with the
selectors in [`../nodejs/worten.mjs`](../nodejs/worten.mjs):

| Extractor | Returns |
| --- | --- |
| `product.js` | one `Product` |
| `category.js` | one `Category` |

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in
[`results/`](results/).
