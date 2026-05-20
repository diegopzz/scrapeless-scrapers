# eBay — CLI surface

Scrape eBay search and product pages from the command line with the
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

Every scrape is the same set of moves: open a session, warm up at the homepage so Akamai issues a
session cookie, navigate, wait for a stable marker, run an in-page extractor. Start with a search
page.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name ebay-cli --ttl 300 --proxy-country US --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# warm up at the homepage so Akamai issues a session cookie
scrapeless-scraping-browser --session-id "$SID" open "https://www.ebay.com/"

# navigate to the search page, then wait for the result list
scrapeless-scraping-browser --session-id "$SID" open "https://www.ebay.com/sch/i.html?_nkw=iphone+12&_ipg=60"
scrapeless-scraping-browser --session-id "$SID" wait "ul.srp-results"

# run the in-page extractor — its JSON comes back in data.result
# save the search extractor (a single expression returning a JSON string)
cat > search.js <<'JS'
// In-page extractor for an eBay search results page.
// Returns a JSON string — a list of SearchResult (see ../../../DATA_MODEL.md).
JSON.stringify(
  Array.from(document.querySelectorAll("ul.srp-results li"))
    .map((el) => {
      const css = (sel) => {
        const n = el.querySelector(sel);
        return n ? n.textContent.trim() || null : null;
      };
      const attr = (sel, a) => el.querySelector(sel)?.getAttribute(a) ?? null;
      const findText = (needle) =>
        Array.from(el.querySelectorAll("*")).find((e) =>
          e.textContent.includes(needle)
        )?.textContent ?? null;

      const location = findText("Located");
      const price = css(".s-card__price") || css(".s-item__price");
      const url =
        attr("a.s-card__link", "href") ?? attr("a.su-link", "href");
      const ratingText =
        Array.from(el.querySelectorAll("span")).find((e) =>
          e.textContent.includes("positive")
        )?.textContent ?? "";

      if (!price) return null;

      let rating_count = null;
      if (ratingText) {
        const m = ratingText.match(/\(([\d.]+)K?\)/);
        if (m) {
          rating_count = m[0].includes("K)")
            ? Math.round(parseFloat(m[1]) * 1000)
            : parseInt(m[1], 10);
        }
      }

      return {
        url: url ? url.split("?")[0] : null,
        title: css(".s-card__title span"),
        price,
        shipping: findText("delivery"),
        location: location ? location.split("Located in ")[1] ?? null : null,
        subtitles: css(".s-card__subtitle span"),
        photo: attr("img", "data-src") ?? attr("img", "src"),
        rating: ratingText ? (ratingText.match(/[\d.]+%/) ?? [null])[0] : null,
        rating_count,
      };
    })
    .filter(Boolean)
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
    "url": "https://www.ebay.com/itm/116370846040",
    "title": "Apple iPhone 12 Unlocked Verizon, T-Mobile, AT&T all Carriers",
    "price": "$189.94",
    "photo": "https://i.ebayimg.com/images/g/qHAAAOSwOrBnHAtQ/s-l500.webp",
    "rating": "99.6%",
    "rating_count": 64900
  }
]
```

## 4. Scrape a product page

Reuse the same warmed-up session — `open` a product URL and wait for the title.

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://www.ebay.com/itm/177439887865"
scrapeless-scraping-browser --session-id "$SID" wait "h1"
# save the product extractor (a single expression returning a JSON string)
cat > product.js <<'JS'
// In-page extractor for an eBay product detail page.
// Returns a JSON string — a single Product with a `variants` list
// (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const txt = (sel) => {
      const n = document.querySelector(sel);
      return n ? n.textContent.trim() || null : null;
    };

    // ---- product ----
    const item = {};
    item.url =
      document.querySelector('link[rel="canonical"]')?.getAttribute("href") ?? "";
    try {
      item.id = item.url.split("/itm/")[1].split("?")[0];
    } catch (e) {
      item.id = "";
    }
    item.price_original = txt(".x-price-primary > span");
    item.price_converted = txt(".x-price-approx__price");
    item.name = Array.from(document.querySelectorAll("h1 span"))
      .map((e) => e.textContent)
      .join("")
      .trim();
    item.seller_name =
      document.querySelector("div[class*='info__about-seller'] a span")
        ?.textContent || null;
    const sellerHref =
      document
        .querySelector("div[class*='info__about-seller'] a")
        ?.getAttribute("href") || "";
    item.seller_url = sellerHref ? sellerHref.split("?")[0] : null;
    item.photos = Array.from(
      document.querySelectorAll(".ux-image-filmstrip-carousel-item.image img")
    ).map((e) => e.getAttribute("src"));
    item.photos.push(
      ...Array.from(
        document.querySelectorAll(".ux-image-carousel-item.image img")
      ).map((e) => e.getAttribute("src"))
    );
    item.description_url =
      document.querySelector("iframe#desc_ifr")?.getAttribute("src") || null;

    const features = {};
    document
      .querySelectorAll("div.ux-layout-section--features dl.ux-labels-values")
      .forEach((fea) => {
        const label = Array.from(
          fea.querySelectorAll(
            ".ux-labels-values__labels-content > div > span"
          )
        )
          .map((e) => e.textContent)
          .join("")
          .replace(/[:\n ]+$/, "")
          .trim();
        const value = Array.from(
          fea.querySelectorAll(
            ".ux-labels-values__values-content > div > span"
          )
        )
          .map((e) => e.textContent)
          .join("")
          .replace(/[:\n ]+$/, "")
          .trim();
        if (label) features[label] = value;
      });
    item.features = features;

    // ---- variants (parse the MSKU JS blob) ----
    function* findJsonObjects(text) {
      let pos = 0;
      while (pos < text.length) {
        const start = text.indexOf("{", pos);
        if (start === -1) return;
        let depth = 0;
        let end = -1;
        let inStr = false;
        let strCh = "";
        let esc = false;
        for (let i = start; i < text.length; i++) {
          const ch = text[i];
          if (inStr) {
            if (esc) { esc = false; continue; }
            if (ch === "\\") { esc = true; continue; }
            if (ch === strCh) { inStr = false; }
            continue;
          }
          if (ch === '"' || ch === "'") { inStr = true; strCh = ch; continue; }
          if (ch === "{") depth++;
          else if (ch === "}") {
            depth--;
            if (depth === 0) { end = i + 1; break; }
          }
        }
        if (end === -1) return;
        try {
          yield JSON.parse(text.slice(start, end));
          pos = end;
        } catch (e) {
          pos = start + 1;
        }
      }
    }

    function nestedLookup(key, doc) {
      const out = [];
      const walk = (d) => {
        if (d && typeof d === "object") {
          if (Array.isArray(d)) {
            d.forEach(walk);
          } else {
            for (const [k, v] of Object.entries(d)) {
              if (k === key) out.push(v);
              walk(v);
            }
          }
        }
      };
      walk(doc);
      return out;
    }

    function parseVariants() {
      let script = null;
      document.querySelectorAll("script").forEach((el) => {
        const t = el.textContent || "";
        if (t.includes("MSKU") && !script) script = t;
      });
      if (!script) return [];
      const allData = [...findJsonObjects(script)];
      const mskuData = nestedLookup("MSKU", allData);
      if (mskuData.length === 0) return [];
      const data = mskuData[0];

      const selectionNames = {};
      for (const menu of data.selectMenus ?? []) {
        for (const id_ of menu.menuItemValueIds ?? []) {
          selectionNames[id_] = menu.displayLabel;
        }
      }
      const selections = [];
      for (const v of Object.values(data.menuItemMap ?? {})) {
        selections.push({
          name: v.valueName,
          variants: v.matchingVariationIds ?? [],
          label: selectionNames[v.valueId],
        });
      }
      const variantDataLookup = nestedLookup("variationsMap", data);
      if (variantDataLookup.length === 0) return [];
      const variantData = variantDataLookup[0];

      const results = [];
      for (const [id_, variant] of Object.entries(variantData)) {
        const v = { id: id_ };
        for (const sel of selections) {
          if (sel.variants.includes(parseInt(id_, 10))) {
            v[sel.label] = sel.name;
          }
        }
        const priceVal = variant?.binModel?.price?.value ?? {};
        v.price_original = priceVal.convertedFromValue ?? priceVal.value ?? null;
        v.price_original_currency =
          priceVal.convertedFromCurrency ?? priceVal.currency ?? null;
        v.price_converted = priceVal.value ?? null;
        v.price_converted_currency = priceVal.currency ?? null;
        v.out_of_stock = variant?.quantity?.outOfStock ?? null;
        results.push(v);
      }
      return results;
    }

    item.variants = parseVariants();
    return item;
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat product.js)" --json
```

`data.result` is a single `Product` (with a `variants` list):

```json
{
  "url": "https://www.ebay.com/itm/177439887865",
  "id": "177439887865",
  "price_original": "US $2,199.00",
  "name": "Apple IPhone 17 Pro Max 5G (Unlocked) 512GB Dual SIM 6.9in 48MP OLED Display",
  "seller_name": "ThreePigs",
  "seller_url": "https://www.ebay.com/str/3wpigs",
  "photos": ["https://i.ebayimg.com/images/g/3QMAAeSwqdxo1XOt/s-l500.webp"],
  "features": {},
  "variants": []
}
```

## 5. Output shape

Each `eval/*.js` file is a single expression that returns a JSON string, kept in lockstep with the
selectors in [`../nodejs/ebay.mjs`](../nodejs/ebay.mjs):

| Extractor | Returns |
| --- | --- |
| `search.js` | list of `SearchResult` |
| `product.js` | one `Product` (with `variants`) |

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in [`results/`](results/).
