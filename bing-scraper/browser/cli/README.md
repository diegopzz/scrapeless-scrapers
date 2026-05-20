# Bing — CLI surface

Scrape Bing search results and keyword suggestions from the command line with the
[`scrapeless-scraping-browser`](https://www.npmjs.com/package/scrapeless-scraping-browser)
CLI. Each page is driven by its own Scrapeless cloud browser session and extracted in-browser with
the CLI's `eval` subcommand. Output matches the `nodejs/` and `python/` surfaces — see
[`../../DATA_MODEL.md`](../../DATA_MODEL.md).

Like the [`nodejs/`](../nodejs/bing.mjs) surface, every session uses a **US residential proxy**
(`--proxy-country US`). Anti-bot is intermittent: **if an extractor returns an empty list, the page
didn't render — close the session and re-run.** Use one fresh session per page (sessions terminate
when their connection drops).

## 1. Install

```bash
npm install -g scrapeless-scraping-browser
```

`node` is also required — the steps below use it to pull values out of the CLI's JSON envelope
(`jq` works too, if preferred).

## 2. Set your API key

```bash
export SCRAPELESS_API_KEY=sk_...      # the only env var this CLI reads — sign up at https://app.scrapeless.com
```

## 3. Scrape a search-results page

Open a fresh US-proxied session, navigate (the query is URL-encoded — spaces become `+`), and wait
for the organic result cards (`li.b_algo`).

```bash
SID=$(scrapeless-scraping-browser new-session --name bing-search --ttl 300 --proxy-country US --json \
  | node -pe 'JSON.parse(require("fs").readFileSync(0)).data.taskId')

scrapeless-scraping-browser --session-id "$SID" open "https://www.bing.com/search?q=web+scraping+emails&first=1"
scrapeless-scraping-browser --session-id "$SID" wait "li.b_algo"

# save the in-page extractor (a single expression returning a JSON string — a list of SearchResult)
cat > search.js <<'JS'
// In-page extractor for a Bing search results page.
// Returns a JSON string — a list of SearchResult (see ../../DATA_MODEL.md).
// `position` is 1-indexed within the page.
JSON.stringify(
  (function () {
    function domainOf(url) {
      try {
        let host = new URL(url).hostname || "";
        if (host.startsWith("www.")) host = host.slice(4);
        return host;
      } catch (e) {
        return "";
      }
    }

    const out = [];
    let position = 0;
    document.querySelectorAll("li.b_algo").forEach((card) => {
      const anchor = card.querySelector("h2 a");
      const url = anchor?.getAttribute("href") ?? "";
      const title = (anchor?.textContent || "").trim();
      const origin = (
        card.querySelector("cite")?.textContent || ""
      ).trim();
      let description = (
        card.querySelector(".b_caption p")?.textContent || ""
      ).trim();
      let date = "";
      const m = description.match(/^(.*?)\s+[·—\-]\s+(.*)$/);
      if (m && m[1].length <= 40) {
        date = m[1].trim();
        description = m[2].trim();
      }
      position += 1;
      out.push({
        position,
        title,
        url,
        origin,
        domain: domainOf(url),
        description,
        date,
      });
    });
    return out;
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat search.js)" --json
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a list of `SearchResult`:

```json
[
  {
    "position": 2,
    "title": "World Wide Web - Wikipedia",
    "url": "https://www.bing.com/ck/a?...",
    "origin": "https://en.wikipedia.org › wiki › World_Wide_Web",
    "domain": "bing.com",
    "description": "Servers and resources on the World Wide Web are identified ...",
    "date": ""
  }
]
```

## 4. Scrape keyword suggestions

The keyword suggestions come from Bing's `/AS/Suggestions` autosuggest endpoint, whose
escaped-HTML body renders into a `<pre>` block. Open the suggestions URL in its own session, then
wait for `pre`. (`cp` is the query length.)

```bash
SID=$(scrapeless-scraping-browser new-session --name bing-keywords --ttl 300 --proxy-country US --json \
  | node -pe 'JSON.parse(require("fs").readFileSync(0)).data.taskId')

scrapeless-scraping-browser --session-id "$SID" open "https://www.bing.com/AS/Suggestions?qry=web+scraping+emails&cvid=test&cp=19&msbqf=false&cc=us&FORM=BESBTB"
scrapeless-scraping-browser --session-id "$SID" wait "pre"

# save the keywords extractor (returns a JSON string — a list of related keyword strings)
cat > keywords.js <<'JS'
// In-page extractor for Bing's autosuggest endpoint.
// Open the /AS/Suggestions?qry=... URL first — its body is escaped HTML rendered
// inside a <pre> block. Returns a JSON string — a list of related keyword
// strings (see ../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const seen = [];

    // Classic SERP related-searches block, when present.
    document
      .querySelectorAll("li.b_ans > div > ul > li")
      .forEach((el) => {
        const v = (el.textContent || "").trim();
        if (v && !seen.includes(v)) seen.push(v);
      });

    if (seen.length === 0) {
      const pre =
        document.querySelector("pre")?.textContent ||
        document.body?.textContent ||
        "";
      if (pre) {
        const unescaped = pre
          .replace(/&lt;/g, "<")
          .replace(/&gt;/g, ">")
          .replace(/&quot;/g, '"')
          .replace(/&amp;/g, "&");
        const doc = new DOMParser().parseFromString(unescaped, "text/html");
        doc.querySelectorAll("li[query]").forEach((el) => {
          const q = el.getAttribute("query");
          if (q && !seen.includes(q)) seen.push(q);
        });
      }
    }

    return seen;
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat keywords.js)" --json
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a list of related keyword strings:

```json
[
  "web scraping emails python",
  "web scraping emails using python",
  "web scraping emails github",
  "web scraping emails tutorial"
]
```

## 5. Output shape

Each extractor above is a single expression that returns a JSON string, kept in lockstep with the
selectors in [`../nodejs/bing.mjs`](../nodejs/bing.mjs):

| Extractor | Returns |
| --- | --- |
| `search.js` | list of `SearchResult` |
| `keywords.js` | list of related keyword strings |

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in
[`results/`](results/).

## Notes

- Bing's classic `b_ans` related-searches block was replaced by Copilot in 2024 — keyword
  suggestions now come from the `/AS/Suggestions` autosuggest endpoint, whose body is escaped HTML.
