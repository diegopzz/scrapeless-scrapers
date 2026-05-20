# AliExpress — CLI surface

Scrape AliExpress search, product, and review pages from the command line with the
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
scrapeless-scraping-browser new-session --name aliexpress-cli --ttl 300 --proxy-country US --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate, then wait for the product title to render
scrapeless-scraping-browser --session-id "$SID" open "https://www.aliexpress.com/item/3256807619226115.html"
scrapeless-scraping-browser --session-id "$SID" wait "h1[data-pl]"

# run the in-page extractor — its JSON comes back in data.result
# save the product extractor (a single expression returning a JSON string)
cat > product.js <<'JS'
// In-page extractor for an AliExpress product detail page.
// Returns a JSON string — a single Product wrapper with
// info / pricing / specifications / delivery / faqs (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const url = location.href;

    const txt = (node) => (node?.textContent || "").trim();

    function parseCount(text) {
      if (!text) return 0;
      let t = text
        .replace(" sold", "")
        .replace(" available", "")
        .replace(/,/g, "")
        .replace(/\+/g, "")
        .trim();
      t = t ? t.split(/\s+/)[0] : "";
      if (!t) return 0;
      const n = parseFloat(t);
      return Number.isFinite(n) ? Math.round(n) : 0;
    }

    const reviewsText =
      txt(document.querySelector("a[class*='reviewer--reviews']")) || null;
    const rateNodes = document.querySelectorAll(
      "div[class*='rating--wrap'] > div"
    ).length;
    const soldText =
      Array.from(
        document.querySelectorAll(
          "a[class*='reviewer--sliderItem'] span"
        )
      ).find((e) => (e.textContent || "").includes("sold"))?.textContent ||
      null;
    const availableText =
      txt(
        document.querySelector("div[class*='quantity--info'] div span")
      ) || null;

    const productIdStr = url.includes("item/")
      ? url.split("item/").pop().split(".")[0]
      : "";
    const productIdInt = parseInt(productIdStr, 10);
    const productId = Number.isFinite(productIdInt)
      ? productIdInt
      : productIdStr;

    const info = {
      name: txt(document.querySelector("h1[data-pl]")) || null,
      productId,
      link: url,
      media: Array.from(
        document.querySelectorAll("div[class*='slider--img'] img")
      )
        .map((e) => e.getAttribute("src"))
        .filter(Boolean),
      rate: rateNodes || null,
      reviews: reviewsText
        ? parseInt(reviewsText.replace(" Reviews", ""), 10)
        : null,
      soldCount: parseCount(soldText),
      availableCount: parseCount(availableText),
    };

    const price =
      txt(document.querySelector("span[class*='price-default--current']")) ||
      null;
    const originalPrice =
      txt(
        document.querySelector("span[class*='price-default--original']")
      ) || null;
    const discount =
      txt(document.querySelector("span[class*='price--discount']")) || null;
    const pricing = {
      priceCurrency: "USD $",
      price: price ? parseFloat(price.split("$").pop()) : null,
      originalPrice: originalPrice
        ? parseFloat(originalPrice.split("$").pop())
        : "No discount",
      discount: discount ?? "No discount",
    };

    const deliveryNodes = document.querySelectorAll(
      ".dynamic-shipping strong"
    );
    const delivery = deliveryNodes[1]
      ? txt(deliveryNodes[1]) || null
      : null;

    const specifications = Array.from(
      document.querySelectorAll("div[class*='specification--prop']")
    ).map((el) => ({
      name:
        txt(
          el.querySelector(
            "div[class*='specification--title'] span"
          )
        ) || null,
      value:
        txt(
          el.querySelector("div[class*='specification--desc'] span")
        ) || null,
    }));

    const faqs = Array.from(
      document.querySelectorAll("div.ask-list ul li")
    ).map((el) => ({
      question: txt(el.querySelector("p.ask-content span")) || null,
      answer: txt(el.querySelector("ul.answer-box li p")) || null,
    }));

    return { info, pricing, specifications, delivery, faqs };
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat product.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a `Product` wrapper with `info / pricing / specifications / delivery / faqs`:

```json
{
  "info": {
    "name": "Mini Electric Drill USB Wireless Mini Handheld Drill ...",
    "productId": 3256807619226115,
    "link": "https://www.aliexpress.com/item/3256807619226115.html",
    "media": ["https://ae-pic-a1.aliexpress-media.com/kf/...avif"]
  },
  "pricing": { "priceCurrency": "USD $", "price": 11.25, "discount": "..." },
  "specifications": [{ "name": "...", "value": "..." }],
  "faqs": []
}
```

## 4. Scrape a search page

Reuse the same session — just `open` a search URL and wait for the result gallery cards.

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://www.aliexpress.com/w/wholesale-drills.html?catId=0&SearchText=drills"
scrapeless-scraping-browser --session-id "$SID" wait "div[class*=card--gallery]"
# save the search extractor (a single expression returning a JSON string)
cat > search.js <<'JS'
// In-page extractor for an AliExpress search results page.
// Returns a JSON string — a list of search-result items (free-form, from
// _init_data_.data.root.fields.mods.itemList.content — see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    let script = null;
    document.querySelectorAll("script").forEach((el) => {
      const t = el.textContent || "";
      if (t.includes("_init_data_=") && !script) script = t;
    });
    if (!script) return [];
    const match = script.match(/_init_data_\s*=\s*\{\s*data:\s*(\{.+\}) \}/s);
    if (!match) return [];
    try {
      const data = JSON.parse(match[1]);
      const fields = data?.data?.root?.fields ?? {};
      return fields?.mods?.itemList?.content ?? [];
    } catch (e) {
      return [];
    }
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat search.js)" --json
```

`data.result` is a list of search-result items pulled from the embedded `_init_data_` JSON:

```json
[
  {
    "productId": "3256811495988772",
    "title": { "displayTitle": "Post Hole Digger Electric 1500W Digging Drill ..." },
    "image": { "imgUrl": "//ae-pic-a1.aliexpress-media.com/kf/...jpg" },
    "prices": { "salePrice": { "formattedPrice": "US $11.25", "discount": 54 } }
  }
]
```

## 5. Scrape reviews

The reviews come from AliExpress's feedback JSON endpoint, whose body renders into a `<pre>` block.
`open` the `searchEvaluation.do` URL for the product id, then wait for `pre`.

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://feedback.aliexpress.com/pc/searchEvaluation.do?productId=1005006717259012&lang=en_US&country=US&page=1&pageSize=10&filter=all&sort=complex_default"
scrapeless-scraping-browser --session-id "$SID" wait "pre"
# save the reviews extractor (a single expression returning a JSON string)
cat > reviews.js <<'JS'
// In-page extractor for the AliExpress feedback JSON endpoint.
// Open the searchEvaluation.do?productId=... URL first — its body renders into a
// <pre> block. Returns a JSON string — a Reviews wrapper with
// reviews / evaluation_stats (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const raw =
      document.querySelector("pre")?.textContent ||
      document.body?.textContent ||
      "";
    let payload;
    try {
      payload = JSON.parse(raw);
    } catch (e) {
      return { reviews: [], evaluation_stats: {} };
    }
    const data = payload?.data ?? {};
    return {
      reviews: data.evaViewList ?? [],
      evaluation_stats: data.productEvaluationStatistic ?? {},
    };
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat reviews.js)" --json
```

`data.result` is a `Reviews` wrapper with `reviews / evaluation_stats`:

```json
{
  "reviews": [
    {
      "buyerName": "Г***ч",
      "buyerCountry": "RU",
      "buyerEval": 100,
      "buyerFeedback": "Отличный шуруповерт! ..."
    }
  ],
  "evaluation_stats": {}
}
```

## 6. Output shape

Each `eval/*.js` file is a single expression that returns a JSON string, kept in lockstep with the
selectors in [`../nodejs/aliexpress.mjs`](../nodejs/aliexpress.mjs):

| Extractor | Returns |
| --- | --- |
| `search.js` | list of search-result items (from `_init_data_`) |
| `product.js` | one `Product` wrapper (`info / pricing / specifications / delivery / faqs`) |
| `reviews.js` | `Reviews` wrapper (`reviews / evaluation_stats`) |

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in
[`results/`](results/).

## Notes

- Set `proxyCountry` to `US` (or an `aep_usuc_f` cookie) for USD pricing — AliExpress localizes
  price and currency by region.
