# Google — CLI surface

Scrape Google SERP results and keyword suggestions from the command line with the
[`scrapeless-scraping-browser`](https://www.npmjs.com/package/scrapeless-scraping-browser)
CLI. One Scrapeless cloud session drives a real browser; each SERP is extracted in-browser with the
CLI's `eval` subcommand. Output matches the `nodejs/` and `python/` surfaces — see
[`../../DATA_MODEL.md`](../../DATA_MODEL.md).

`nodejs/google.mjs` reads SERP results and keyword suggestions from Scrapeless's Deep SerpApi actor
(`scraper.google.search`). The CLI surface instead opens the rendered Google SERP and extracts the
same organic results, related searches, and "people also ask" blocks straight from the DOM — the
`SerpResult` and `Keywords` shapes are kept identical. The Maps `scrape_google_map_places` function
is not part of the CLI surface (no fixture in `results/`).

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
in-page extractor. Start with a SERP and the organic-results extractor.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name google-cli --ttl 300 --proxy-country US --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate to a SERP, then wait for the main result column
scrapeless-scraping-browser --session-id "$SID" open "https://www.google.com/search?q=the%20upstream%20reference%20blog%20web%20scraping&hl=en"
scrapeless-scraping-browser --session-id "$SID" wait "#search"

# run the in-page extractor — its JSON comes back in data.result
# save the serp extractor (a single expression returning a JSON string)
cat > serp.js <<'JS'
// In-page extractor for a Google SERP
// (https://www.google.com/search?q=<query>&hl=en).
// Returns a JSON string — a list of SerpResult (see ../../../DATA_MODEL.md).
//
// nodejs/google.mjs reads organic results from Scrapeless's Deep SerpApi
// actor; the CLI surface instead extracts the same rows straight from the
// rendered SERP DOM to keep the SerpResult shape identical.
JSON.stringify(
  (function () {
    const normalise = (s) => String(s || "").replace(/\s+/g, " ").trim();
    const domainOf = (url) => {
      try {
        let host = new URL(url).hostname || "";
        if (host.startsWith("www.")) host = host.slice(4);
        return host;
      } catch (e) {
        return "";
      }
    };

    const seen = new Set();
    const out = [];
    let position = 0;

    // Organic results render as a heading anchor (`h3` inside an `<a>`) within
    // the main result column. Skip anything inside ad / sitelink / "people
    // also ask" blocks.
    document.querySelectorAll("#search a:has(h3), #rso a:has(h3)").forEach((a) => {
      const h3 = a.querySelector("h3");
      const href = a.getAttribute("href") || "";
      if (!h3 || !href || !/^https?:/.test(href)) return;
      if (href.includes("google.com/")) return;
      if (a.closest("[data-text-ad], .commercial-unit-desktop-top, .related-question-pair"))
        return;
      if (seen.has(href)) return;
      seen.add(href);

      // The result container holds the cite block + snippet.
      const block =
        a.closest("div.g, div.MjjYud, div.tF2Cxc, div.kvH3mc") || a.parentElement;
      const cite = block ? block.querySelector("cite") : null;
      const origin = cite ? normalise(cite.textContent.split(" › ")[0]) : "";

      let description = "";
      let date = "";
      if (block) {
        const snip = block.querySelector(
          "div[data-sncf], div.VwiC3b, div.IsZvec, div.lEBKkf"
        );
        if (snip) {
          const full = normalise(snip.textContent);
          // A leading "Mon DD, YYYY — " / "N days ago — " date is split off.
          const m = full.match(/^([A-Z][a-z]{2,8} \d{1,2}, \d{4}|\d+ \w+ ago)\s+[—-]\s+/);
          if (m) {
            date = m[1];
            description = full.slice(m[0].length);
          } else {
            description = full;
          }
        }
      }

      position += 1;
      out.push({
        position,
        title: normalise(h3.textContent),
        url: href,
        origin,
        domain: domainOf(href),
        description,
        date,
      });
    });

    return out;
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat serp.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a list of `SerpResult`:

```json
[
  {
    "position": 1,
    "title": "2022 Echo Dot 5th Gen Smart Speaker | Charcoal",
    "url": "https://www.amazon.com/Amazon-vibrant-helpful-routines-Charcoal/dp/B09B8V1LZ3",
    "origin": "Amazon.com",
    "domain": "amazon.com",
    "description": "Enhance your smart home hub experience with the Charcoal colored 2022 Echo Dot ...",
    "date": ""
  }
]
```

## 4. Scrape the keyword blocks

Reuse the same session — just `open` another SERP and wait for the same `#search` marker, then run
the keywords extractor. It lifts the "Searches related to …" grid and the "People also ask" rows.

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://www.google.com/search?q=web%20scraping%20emails&hl=en"
scrapeless-scraping-browser --session-id "$SID" wait "#search"
# save the keywords extractor (a single expression returning a JSON string)
cat > keywords.js <<'JS'
// In-page extractor for the keyword blocks on a Google SERP
// (https://www.google.com/search?q=<query>&hl=en).
// Returns a JSON string — a single Keywords dict (see ../../../DATA_MODEL.md).
//
// nodejs/google.mjs reads related searches + "people also ask" from
// Scrapeless's Deep SerpApi actor; the CLI surface instead extracts the same
// blocks straight from the rendered SERP DOM to keep the Keywords shape
// identical.
JSON.stringify(
  (function () {
    const normalise = (s) => String(s || "").replace(/\s+/g, " ").trim();

    // Related searches: the "Related searches" / "Searches related to …"
    // block renders a grid of anchors back into /search.
    const related_search = [];
    const seenRel = new Set();
    document
      .querySelectorAll(
        "a[href^='/search'][data-ved] .s75CSd, " +
          "div.AJLUJb a, div.k8XOCe, div.y6Uyqe a, div.b2Rnsc"
      )
      .forEach((el) => {
        const t = normalise(el.textContent);
        if (!t || seenRel.has(t.toLowerCase())) return;
        seenRel.add(t.toLowerCase());
        related_search.push(t);
      });

    // "People also ask" — each question is a collapsible row carrying the
    // text in a data attribute or as the visible row label.
    const people_ask_for = [];
    const seenPaa = new Set();
    document
      .querySelectorAll(
        "div[data-q], div.related-question-pair span, div.JlqpRe span, " +
          "div.iDjcJe, div.cbphWd"
      )
      .forEach((el) => {
        const q = normalise(el.getAttribute("data-q") || el.textContent);
        if (!q || q.length < 8 || seenPaa.has(q.toLowerCase())) return;
        seenPaa.add(q.toLowerCase());
        people_ask_for.push(q);
      });

    return { related_search, people_ask_for };
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat keywords.js)" --json
```

`data.result` is a single `Keywords` dict:

```json
{
  "related_search": [
    "Echo Dot 5th Generation",
    "Echo Dot 3rd Gen",
    "Echo Dot price"
  ],
  "people_ask_for": []
}
```

## 5. Output shape

Each `eval/*.js` file is a single expression that returns a JSON string, matching the field shapes
in [`../nodejs/google.mjs`](../nodejs/google.mjs):

| Extractor | Returns |
| --- | --- |
| `serp.js` | list of `SerpResult` |
| `keywords.js` | one `Keywords` dict |

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in
[`results/`](results/).
