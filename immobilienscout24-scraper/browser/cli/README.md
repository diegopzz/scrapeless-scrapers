# ImmobilienScout24 (DE) — CLI surface

Scrape ImmobilienScout24 property (expose) pages from the command line with the
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
in-page extractor. ImmobilienScout24 has one page type — the property expose page.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name immobilienscout24-cli --ttl 300 --proxy-country DE --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate, then wait for the expose title to render
scrapeless-scraping-browser --session-id "$SID" open "https://www.immobilienscout24.de/expose/160519246"
scrapeless-scraping-browser --session-id "$SID" wait "h1#expose-title"

# run the in-page extractor — its JSON comes back in data.result
# save the properties extractor (a single expression returning a JSON string)
cat > properties.js <<'JS'
// In-page extractor for an Immobilienscout24 property detail (expose) page.
// Returns a JSON string — a single PropertyResult (see ../../../DATA_MODEL.md).
// Field names (including the upstream typos propertyLlink / propertySepcs /
// priceWithoutHeadting / finalEnergyRrequirement) are verbatim.
JSON.stringify(
  (function () {
    const textOrNull = (sel) => {
      const t = (document.querySelector(sel)?.textContent ?? "").trim();
      return t || null;
    };

    const canonical =
      document.querySelector("link[rel='canonical']")?.getAttribute("href") ||
      location.href;
    const idMatch = /\/expose\/(\d+)/.exec(canonical);
    const id = idMatch ? idMatch[1] : "";

    const priceText = (
      document.querySelector("dd.is24qa-kaltmiete, dd[class*='kaltmiete']")
        ?.textContent ?? ""
    ).trim();
    const currencyMatch = /([€$£])/.exec(priceText);
    const priceCurrency = currencyMatch ? currencyMatch[1] : null;

    const propertyImages = [];
    document.querySelectorAll(".sp-slides .sp-slide img").forEach((el) => {
      const src = el.getAttribute("data-src");
      if (src) propertyImages.push(src);
    });
    const videoAvailable =
      document.querySelectorAll(".sp-slides .sp-video").length > 0;

    const internetText = (
      document.querySelector("a[class*='mediaavailcheck']")?.textContent ?? ""
    ).toLowerCase();
    const additionalSpecs = [];
    document.querySelectorAll("div[class*='criteriagroup'] dd").forEach((el) => {
      const t = el.textContent.trim();
      if (t) additionalSpecs.push(t);
    });

    return {
      id,
      title: (
        document.querySelector("h1#expose-title")?.textContent ?? ""
      ).trim(),
      description:
        document
          .querySelector("meta[name='description']")
          ?.getAttribute("content") || null,
      address: textOrNull(".address-block > div > span:nth-child(2)"),
      propertyLlink: canonical,
      propertySepcs: {
        floorsNumber: textOrNull("dd[class*='etage']"),
        livingSpace: textOrNull("dd[class*='wohnflaeche']"),
        livingSpaceUnit: textOrNull("dd[class*='wohnflaeche'] span"),
        vacantFrom: textOrNull("dd[class*='bezugsfrei']"),
        numberOfRooms: textOrNull("dd[class*='zimmer']"),
        "Garage/parking space": textOrNull("dd[class*='garage-stellplatz']"),
        additionalSpecs,
        internetAvailable:
          internetText.includes("verfügbar") ||
          internetText.includes("available"),
      },
      price: {
        priceWithoutHeadting: priceText || null,
        priceperMeter: textOrNull("dd[class*='preism2']"),
        additionalCosts: textOrNull("dd[class*='nebenkosten']"),
        heatingCosts: textOrNull("dd[class*='heizkosten']"),
        totalRent: textOrNull("dd[class*='gesamtmiete']"),
        basisRent: textOrNull("dd[class*='baseprice']"),
        deposit: textOrNull("dd[class*='kaution']"),
        "garage/parkingRent": textOrNull("dd[class*='stellplatzmiete']"),
        priceCurrency,
      },
      building: {
        constructionYear: textOrNull("dd[class*='baujahr']"),
        energySources: textOrNull("dd[class*='energietraeger']"),
        energyCertificate: textOrNull("dd[class*='energieausweis']"),
        energyCertificateType: textOrNull("dd[class*='energieausweistyp']"),
        energyCertificateDate: textOrNull(
          "dd[class*='energieausweis-gueltig']"
        ),
        finalEnergyRrequirement: textOrNull("dd[class*='endenergiebedarf']"),
      },
      attachments: {
        propertyImages,
        videoAvailable,
      },
      agencyName: textOrNull("span[data-qa='companyName']"),
      agencyAddress: textOrNull("div[data-qa='companyAddress']"),
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
  "id": "160519246",
  "title": "Doppelzimmer im CAMPO NOVO Business München ...",
  "address": "Augustenstraße, 80335 München",
  "propertyLlink": "https://www.immobilienscout24.de/expose/160519246",
  "propertySepcs": { "livingSpace": "25  m²", "numberOfRooms": "1", "vacantFrom": "04.09.2025" },
  "price": { "...": "..." },
  "building": { "...": "..." },
  "attachments": { "propertyImages": ["..."], "videoAvailable": false }
}
```

The typo'd keys (`propertyLlink`, `propertySepcs`, `priceWithoutHeadting`, `finalEnergyRrequirement`)
are verbatim from the upstream reference — see [`../../DATA_MODEL.md`](../../DATA_MODEL.md).

## 4. Output shape

`properties.js` is a single expression that returns a JSON string, kept in lockstep with the
selectors in [`../nodejs/immobilienscout24.mjs`](../nodejs/immobilienscout24.mjs):

| Extractor | Returns |
| --- | --- |
| `properties.js` | one `PropertyResult` |

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in
[`results/`](results/).
