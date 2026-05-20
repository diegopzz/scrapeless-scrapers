# Google News — CLI surface

Scrape Google News article cards from the command line with the
[`scrapeless-scraping-browser`](https://www.npmjs.com/package/scrapeless-scraping-browser)
CLI. One Scrapeless cloud session drives a real browser; the news SPA is extracted in-browser with
the CLI's `eval` subcommand. Output matches the `nodejs/` and `python/` surfaces — see
[`../../DATA_MODEL.md`](../../DATA_MODEL.md).

The CLI surface covers `scrape_news`. `scrape_topic` from `nodejs/` hits the same card layout on a
`/topics/<id>` URL — open a topic URL by hand with the same `articles.js` extractor.

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
in-page extractor. Google News is a client-side SPA, so the run waits for the headline anchors
(`a.JtKRv`) to mount before extracting.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name google-news-cli --ttl 300 --proxy-country US --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate to a news search page, then wait for the headline anchors
scrapeless-scraping-browser --session-id "$SID" open "https://news.google.com/search?q=adidas&hl=en-US&gl=US&ceid=US:en"
scrapeless-scraping-browser --session-id "$SID" wait "a.JtKRv"

# run the in-page extractor — its JSON comes back in data.result
# save the articles extractor (a single expression returning a JSON string)
cat > articles.js <<'JS'
// In-page extractor for a Google News search/topic page
// (https://news.google.com/search?q=<query>).
// Returns a JSON string — a list of Article (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const normalise = (s) => String(s || "").replace(/\s+/g, " ").trim();

    // aria-label format: "<title> - <source> - <time> - By <author>"
    // Returns ["", source, time].
    const splitAriaLabel = (aria, title) => {
      if (!aria) return ["", "", ""];
      let rest = aria;
      if (aria.startsWith(title)) {
        rest = aria.slice(title.length);
      } else {
        const idx = aria.indexOf(" - ");
        if (idx >= 0) rest = aria.slice(idx);
      }
      rest = rest.replace(/^ -\s*/, "");
      const parts = rest.split(" - ");
      return ["", normalise(parts[0] || ""), normalise(parts[1] || "")];
    };

    const seen = new Set();
    const out = [];
    let position = 0;

    // Each `a.JtKRv` is rendered once per card and carries an `aria-label`
    // of the form "<title> - <source> - <time> - By <author>".
    document.querySelectorAll("a.JtKRv").forEach((a) => {
      const href = a.getAttribute("href") || "";
      const titleText = normalise(a.textContent);
      if (!href || !titleText) return;
      const absUrl = href.startsWith("./")
        ? "https://news.google.com" + href.slice(1)
        : href;
      if (seen.has(absUrl)) return;
      seen.add(absUrl);

      const aria = a.getAttribute("aria-label") || "";
      const [, source, time] = splitAriaLabel(aria, titleText);

      // Walk up to the card container to pick up the thumbnail.
      let thumbnail = "";
      const card = a.closest("div.m5k28, article, div.IBr9hb, div.XlKvRb");
      if (card) {
        for (const img of card.querySelectorAll("img")) {
          const src = img.getAttribute("src") || img.getAttribute("data-src") || "";
          if (/^https?:/.test(src)) {
            thumbnail = src;
            break;
          }
        }
      }

      position += 1;
      out.push({
        position,
        title: titleText,
        url: absUrl,
        source,
        time,
        thumbnail,
      });
    });

    return out;
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat articles.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a list of `Article`:

```json
[
  {
    "position": 1,
    "title": "adidas Is Upgrading the Samba for Summertime",
    "url": "https://news.google.com/read/CBMiiwF...?hl=en-US&gl=US&ceid=US%3Aen",
    "source": "hypebae.com",
    "time": "22 hours ago",
    "thumbnail": "https://encrypted-tbn0.gstatic.com/faviconV2?url=https://hypebae.com&..."
  }
]
```

## 4. Output shape

The single `eval/*.js` file is a one-line expression that returns a JSON string, kept in lockstep
with the selectors in [`../nodejs/google-news.mjs`](../nodejs/google-news.mjs):

| Extractor | Returns |
| --- | --- |
| `articles.js` | list of `Article` |

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in
[`results/`](results/).
