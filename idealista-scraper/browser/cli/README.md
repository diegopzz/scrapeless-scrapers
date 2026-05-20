# Idealista — CLI surface

Scrape Idealista property, search, and province pages from the command line with the
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
in-page extractor. Start with a property detail page.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name idealista-cli --ttl 300 --proxy-country ES --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate, then wait for the property title to render
scrapeless-scraping-browser --session-id "$SID" open "https://www.idealista.com/en/inmueble/111070021/"
scrapeless-scraping-browser --session-id "$SID" wait "h1 .main-info__title-main"

# run the in-page extractor — its JSON comes back in data.result
# save the properties extractor (a single expression returning a JSON string)
cat > properties.js <<'JS'
// In-page extractor for an Idealista property detail page.
// Returns a JSON string — a single PropertyResult (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const txt = (sel) =>
      (document.querySelector(sel)?.textContent ?? "").trim();
    const absoluteUrl = (rel) => {
      try {
        return new URL(rel, location.href).toString();
      } catch (e) {
        return rel;
      }
    };

    const currency = txt(".info-data-price");
    const priceRaw = txt(".info-data-price span").replace(/,/g, "");
    const price = parseInt(priceRaw, 10) || 0;

    const descriptionParts = [];
    document.querySelectorAll("div.comment *").forEach((el) => {
      el.childNodes.forEach((n) => {
        if (n.nodeType === 3 && n.nodeValue) descriptionParts.push(n.nodeValue);
      });
    });

    const updatedEl = Array.from(
      document.querySelectorAll("p.stats-text")
    ).find((el) => el.textContent.includes("updated on"));
    const updatedText = updatedEl ? updatedEl.textContent : "";
    const updated = updatedText.includes(" on ")
      ? updatedText.split(" on ").pop()
      : "";

    const features = {};
    document.querySelectorAll(".details-property-h2").forEach((el) => {
      const label = el.textContent;
      const items = [];
      const block = el.nextElementSibling;
      if (block) {
        block.querySelectorAll("li").forEach((li) =>
          items.push(li.textContent.trim())
        );
      }
      features[label] = items;
    });

    const images = {};
    const plans = [];
    const html = document.documentElement.outerHTML;
    const m = /fullScreenGalleryPics\s*:\s*(\[.+?\]),/s.exec(html);
    if (m) {
      try {
        const normalised = m[1].replace(/(\w+?):([^/])/g, '"$1":$2');
        const arr = JSON.parse(normalised);
        for (const img of arr) {
          const full = absoluteUrl(img.imageUrl || "");
          if (img.isPlan) plans.push(full);
          else {
            const tag = img.tag || "";
            (images[tag] = images[tag] || []).push(full);
          }
        }
      } catch (e) {}
    }

    return {
      url: location.href,
      title: txt("h1 .main-info__title-main"),
      location: txt(".main-info__title-minor"),
      currency,
      price,
      description: descriptionParts.join("").trim(),
      updated,
      features,
      images,
      plans,
    };
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat properties.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a `PropertyResult` object:

```json
{
  "url": "https://www.idealista.com/en/inmueble/111070021/",
  "title": "Semi-detached house for sale in Cecilia Bohl De Faber",
  "location": "Lomas de Marbella Club, Marbella",
  "price": 1975000,
  "currency": "€",
  "description": "Exclusive Spacious House Walking Distance to Puente Romano ...",
  "features": { "...": ["..."] },
  "images": { "...": ["..."] },
  "plans": ["..."]
}
```

## 4. Scrape a search page

Reuse the same session — just `open` a search URL and wait for the result cards.

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://www.idealista.com/en/venta-viviendas/marbella-malaga/con-chalets/"
scrapeless-scraping-browser --session-id "$SID" wait "article.item"
# save the search extractor (a single expression returning a JSON string)
cat > search.js <<'JS'
// In-page extractor for an Idealista search results page.
// Returns a JSON string — a list of SearchResult (see ../../../DATA_MODEL.md).
JSON.stringify(
  Array.from(document.querySelectorAll("article.item")).map((card) => {
    const absoluteUrl = (rel) => {
      try {
        return new URL(rel, location.href).toString();
      } catch (e) {
        return rel;
      }
    };
    const link = card.querySelector(".item-link");
    const linkRel = link?.getAttribute("href") || "";
    const title = (
      link?.getAttribute("title") ||
      link?.textContent ||
      ""
    ).trim();

    const priceText = (
      card.querySelector(".item-price")?.textContent ?? ""
    ).trim();
    let price = 0;
    let currency = "";
    const m = /([\d.,]+)\s*([^\d\s]+)/.exec(priceText);
    if (m) {
      price = parseInt(m[1].replace(/[.,]/g, ""), 10) || 0;
      currency = m[2];
    }

    const details = [];
    card
      .querySelectorAll(".item-detail-char .item-detail")
      .forEach((d) => {
        const t = d.textContent.trim();
        if (t) details.push(t);
      });

    const description = (
      card.querySelector(".item-description")?.textContent ?? ""
    ).trim();

    const tags = [];
    const tagsEl = card.querySelector(".item-tags");
    if (tagsEl) {
      Array.from(tagsEl.children).forEach((t) => {
        const v = t.textContent.trim();
        if (v) tags.push(v);
      });
    }

    const listingCompany =
      card.querySelector(".item-branding .logo-branding")?.getAttribute("title") ||
      null;
    const lcUrlRel = card
      .querySelector(".item-branding a")
      ?.getAttribute("href");
    const picture =
      card.querySelector(".item-multimedia img")?.getAttribute("src") || null;

    return {
      title,
      link: absoluteUrl(linkRel),
      picture,
      price,
      currency,
      parking_included:
        /parking/i.test(priceText) ||
        card.querySelectorAll(".item-parking").length > 0,
      details,
      description,
      tags,
      listing_company: listingCompany,
      listing_company_url: lcUrlRel ? absoluteUrl(lcUrlRel) : null,
    };
  })
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat search.js)" --json
```

`data.result` is a list of `SearchResult`:

```json
[
  {
    "title": "Semi-detached house in Cecilia Bohl De Faber, Lomas de Marbella Club, Marbella",
    "link": "https://www.idealista.com/en/inmueble/111070021/",
    "picture": "https://img4.idealista.com/blur/591_420_mq/0/id.pro.es.image.master/d7/83/62/1431403598.jpg",
    "price": 1975000,
    "currency": "€",
    "parking_included": false,
    "details": ["Parking included", "5 bed.", "304 m²"]
  }
]
```

## 5. Scrape a province list

Reuse the same session — `open` a province → municipality page and wait for the location list.

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://www.idealista.com/venta-viviendas/almeria-provincia/municipios"
scrapeless-scraping-browser --session-id "$SID" wait "#location_list"
# save the provinces extractor (a single expression returning a JSON string)
cat > provinces.js <<'JS'
// In-page extractor for an Idealista province → municipality list page.
// Returns a JSON string — a flat list of ProvinceURL strings (see ../../../DATA_MODEL.md).
JSON.stringify(
  Array.from(document.querySelectorAll("#location_list li > a"))
    .map((el) => {
      const href = el.getAttribute("href");
      if (!href) return null;
      try {
        return new URL(href, location.href).toString();
      } catch (e) {
        return href;
      }
    })
    .filter(Boolean)
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat provinces.js)" --json
```

`data.result` is a flat list of municipality search URLs:

```json
[
  "https://www.idealista.com/venta-viviendas/abla-almeria/",
  "https://www.idealista.com/venta-viviendas/abrucena-almeria/",
  "https://www.idealista.com/venta-viviendas/adra-almeria/"
]
```

## 6. Output shape

Each `eval/*.js` file is a single expression that returns a JSON string, kept in lockstep with the
selectors in [`../nodejs/idealista.mjs`](../nodejs/idealista.mjs):

| Extractor | Returns |
| --- | --- |
| `properties.js` | one `PropertyResult` |
| `search.js` | list of `SearchResult` |
| `provinces.js` | flat list of `ProvinceURL` strings |

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in
[`results/`](results/).
