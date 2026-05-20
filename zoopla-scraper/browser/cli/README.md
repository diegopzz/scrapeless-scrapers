# Zoopla — CLI surface

Scrape Zoopla property detail pages from the command line with the
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

Zoopla is geo-locked + Akamai-protected. The `nodejs/` and `python/` surfaces pin a GB residential
proxy at session creation — create your Scrapeless cloud session in a GB region for parity
(per-call identity flags are ignored server-side).

## 3. Scrape a property page

Every scrape is the same four moves: open a session, navigate, wait for a stable marker, run an
in-page extractor. The CLI surface covers the `properties` kind — a property detail page.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name zoopla-cli --ttl 300 --proxy-country GB --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate, then wait for the local-area section to render
scrapeless-scraping-browser --session-id "$SID" open "https://www.zoopla.co.uk/new-homes/details/70337559/"
scrapeless-scraping-browser --session-id "$SID" wait "section[aria-labelledby='local-area']"

# run the in-page extractor — its JSON comes back in data.result
# save the properties extractor (a single expression returning a JSON string)
cat > properties.js <<'JS'
// In-page extractor for a Zoopla property detail page.
// Returns a JSON string — a single Property (see ../../../DATA_MODEL.md).
//
// Mirrors parseProperty() in ../nodejs/zoopla.mjs. Zoopla's property pages
// don't expose a clean JSON cache, so everything is read from the rendered DOM.
JSON.stringify(
  (function () {
    const txt = (node) => node?.textContent ?? "";

    const intOrNull = (s) => {
      if (!s) return null;
      const n = parseInt(
        String(s).split(" ")[0].replace(/[£,~]/g, ""),
        10
      );
      return Number.isFinite(n) ? n : null;
    };

    // first <p> whose text matches a regex
    const firstP = (re) => {
      for (const p of document.querySelectorAll("p")) {
        if (re.test(txt(p))) return txt(p) || null;
      }
      return null;
    };

    const url =
      document
        .querySelector('meta[property="og:url"]')
        ?.getAttribute("content") ?? null;
    const price = firstP(/£/);
    const receptions = firstP(/reception/);
    const baths = firstP(/bath/);
    const beds = firstP(/bed/);

    const gmapSrcs = Array.from(
      document.querySelectorAll(
        "section[aria-labelledby='local-area'] picture source"
      )
    )
      .map((el) => el.getAttribute("srcset"))
      .filter((s) => s != null);
    const gmapSource = gmapSrcs.length
      ? gmapSrcs[gmapSrcs.length - 1]
      : null;
    const coordinates =
      gmapSource && gmapSource.includes("/static/")
        ? gmapSource.split("/static/")[1].split("/")[0]
        : null;
    const agentPath =
      document
        .querySelector("section[aria-label='Contact agent'] a")
        ?.getAttribute("href") ?? null;

    const info = [];
    document
      .querySelectorAll("section[aria-labelledby='key-info'] li")
      .forEach((li) => {
        const title = txt(li.querySelector("p")) || null;
        const value = txt(li.querySelector("div p")) || null;
        if (value !== null && value !== "") info.push({ title, value });
      });

    const nearby = [];
    document
      .querySelectorAll(
        "div:has(section[aria-label*='Travel']) section:nth-of-type(3) li div"
      )
      .forEach((div) => {
        const ps = div.querySelectorAll("p");
        const distance = ps[1] ? txt(ps[1]) || null : null;
        nearby.push({
          title: ps[0] ? txt(ps[0]) || null : null,
          distance: distance ? parseFloat(distance.split(" ")[0]) : null,
          unit: distance ? distance.split(" ")[1] : null,
        });
      });

    const idFromUrl =
      url && url.includes("details/")
        ? parseInt(url.split("details/").pop().split("/")[0], 10)
        : null;

    const gallerySources = document.querySelectorAll(
      "li[data-key*='gallery'] picture source"
    );
    const lastGallery = gallerySources.length
      ? gallerySources[gallerySources.length - 1]
      : null;
    const gallery = lastGallery
      ? [lastGallery.getAttribute("srcset")].filter(Boolean)
      : [];

    const propertyTags = (function () {
      const ul = document.querySelector("section ul");
      if (!ul) return [];
      return Array.from(ul.querySelectorAll("li p")).map((el) => txt(el));
    })();

    return {
      id: Number.isFinite(idFromUrl) ? idFromUrl : null,
      url,
      title: txt(document.querySelector("title")) || null,
      address: txt(document.querySelector("address")) || null,
      price: {
        amount: price ? parseInt(price.replace(/£|,/g, ""), 10) : null,
        currency: "£",
      },
      gallery,
      epcRating: firstP(/EPC/),
      floorArea: firstP(/ft/),
      numOfReceptions: intOrNull(receptions),
      numOfBathrooms: intOrNull(baths),
      numOfBedrooms: intOrNull(beds),
      propertyTags,
      propertyInfo: info,
      propertyDescription: Array.from(
        document.querySelectorAll(
          "section[aria-labelledby='about'] ul li p span"
        )
      ).map((el) => txt(el)),
      coordinates: {
        googleMapeSource: gmapSource,
        latitude: coordinates
          ? parseFloat(coordinates.split(",")[0])
          : null,
        longitude: coordinates
          ? parseFloat(coordinates.split(",")[1])
          : null,
      },
      nearby,
      agent: {
        name:
          txt(
            document.querySelector(
              "section[aria-label='Contact agent'] p"
            )
          ) || null,
        logo:
          document
            .querySelector("section[aria-label='Contact agent'] img")
            ?.getAttribute("src") ?? null,
        url: agentPath ? "https://www.zoopla.co.uk" + agentPath : null,
      },
    };
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat properties.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a `Property` object — Zoopla's property pages don't expose a clean JSON cache, so
everything is read from the rendered DOM:

```json
{
  "id": 71411815,
  "url": "https://www.zoopla.co.uk/new-homes/details/71411815/",
  "title": "Somerset Road, West Ealing W13, New home, 3 bed maisonette for sale, £725,000 - Zoopla",
  "address": "Somerset Road, West Ealing W13",
  "price": { "amount": 725000, "currency": "£" },
  "numOfBedrooms": 3,
  "numOfBathrooms": 3,
  "propertyInfo": [{ "title": "Tenure", "value": "Leasehold (999 years)" }]
}
```

the extractor wraps this object in a one-element list so the saved fixture stays shape-identical with the
`scrape_properties` output of the other surfaces.

## 4. Output shape

`properties.js` is a single expression that returns a JSON string, kept in lockstep with the
selectors in [`../nodejs/zoopla.mjs`](../nodejs/zoopla.mjs):

| Extractor | Returns |
| --- | --- |
| `properties.js` | one `Property` |

The `search` kind is implemented on the `nodejs/` and `python/` surfaces (`scrape_search`) but has
no committed fixture, so it is not wired into this CLI run. The selectors port cleanly to in-page
`eval` if you need it — mirror `parseSearch` in `../nodejs/zoopla.mjs`.

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in
[`results/`](results/).
