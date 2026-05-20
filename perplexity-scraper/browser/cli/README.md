# Perplexity — CLI surface

Scrape Perplexity answer pages from the command line with the
[`scrapeless-scraping-browser`](https://www.npmjs.com/package/scrapeless-scraping-browser)
CLI. One Scrapeless cloud session drives a real browser; the answer page is extracted in-browser
with the CLI's `eval` subcommand. Output matches the `nodejs/` and `python/` surfaces — see
[`../../DATA_MODEL.md`](../../DATA_MODEL.md).

## 1. Install

```bash
npm install -g scrapeless-scraping-browser
```

`node` is also required — the steps below use it to pull values out of the CLI's JSON envelope and
to URL-encode the prompt (`jq` works too, if preferred).

## 2. Set your API key

```bash
export SCRAPELESS_API_KEY=sk_...      # sign up at https://app.scrapeless.com
```

## 3. Scrape an answer page

Every scrape is the same four moves: open a session, navigate, wait for a stable marker, run an
in-page extractor. The `nodejs/` surface types the prompt into Perplexity's Lexical contenteditable
and presses Enter; the CLI surface exposes only `open` / `wait` / `eval`, so it instead opens
`https://www.perplexity.ai/search/new?q=<prompt>` directly and lets Perplexity render the answer
page.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name perplexity-cli --ttl 360 --proxy-country US --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# URL-encode the prompt and open the answer page
PROMPT="top 3 smartphones in 2025, compare pricing across US marketplaces"
ENCODED=$(node -e 'process.stdout.write(encodeURIComponent(process.argv[1]))' "$PROMPT")
scrapeless-scraping-browser --session-id "$SID" open "https://www.perplexity.ai/search/new?q=$ENCODED"

# wait for the answer prose to render
scrapeless-scraping-browser --session-id "$SID" wait "div[class*='prose']"

# run the in-page extractor — its JSON comes back in data.result
# save the search extractor (a single expression returning a JSON string)
cat > search.js <<'JS'
// In-page extractor for a Perplexity answer page (`/search/...`).
// Returns a JSON string — one Search (see ../../../DATA_MODEL.md).
// Mirrors `parseSearch` in ../nodejs/perplexity.mjs. The nodejs/ surface types
// the prompt into the Lexical contenteditable; the CLI surface instead opens
// `/search/new?q=<prompt>` directly, so the question is read from the page's
// `h1.group/query` heading.
JSON.stringify(
  (function () {
    const domainOf = (url) => {
      try {
        let host = new URL(url).hostname || "";
        if (host.startsWith("www.")) host = host.slice(4);
        return host;
      } catch (e) {
        return "";
      }
    };

    // Question — rendered inside the first `h1` whose class contains
    // `group/query`. Fall back to the `q` query param the URL was opened with.
    let queryText = (
      document.querySelector("h1[class*='group/query']")?.textContent ?? ""
    )
      .replace(/\s+/g, " ")
      .trim();
    if (!queryText) {
      try {
        queryText = new URL(location.href).searchParams.get("q") || "";
      } catch (e) {}
    }
    queryText = queryText.replace(/\s+/g, " ").trim();

    // Answer — the first `<div class="prose ...">` block holds the response.
    const proseNode = document.querySelector("div[class*='prose']");
    const answerText = (proseNode?.textContent ?? "")
      .replace(/\s+/g, " ")
      .trim();

    // Citations — every external `<a href="http...">` that isn't a
    // perplexity-internal link or layout chrome. Deduped on href.
    const seen = new Set();
    const citations = [];
    document.querySelectorAll("a[href^='http']").forEach((el) => {
      const href = el.getAttribute("href") || "";
      if (!href || seen.has(href)) return;
      if (/perplexity\.ai/.test(href)) return;
      if (/\.perplexity\.ai\//.test(href)) return;
      if (/cloudflare\.com|gstatic\.com|twitter\.com\/PerplexityAI/.test(href))
        return;
      seen.add(href);
      const title = (el.textContent ?? "").replace(/\s+/g, " ").trim();
      citations.push({
        url: href,
        domain: domainOf(href),
        title,
      });
    });

    return {
      query: queryText,
      url: location.href,
      answer_text: answerText,
      citations,
    };
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat search.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is one `Search` — the question is read from the `h1.group/query` heading (falling
back to the `q` query param):

```json
{
  "query": "top 3 smartphones in 2025, compare pricing across US marketplaces",
  "url": "https://www.perplexity.ai/search/739a1d03-06a0-4976-87f0-b58be3ce35b3",
  "answer_text": "Here are three of the strongest smartphones in 2025: ...",
  "citations": [
    { "url": "https://www.businessinsider.com/...", "domain": "businessinsider.com", "title": "..." }
  ]
}
```

If the answer hasn't finished streaming when `eval` runs, the extractor still returns the `Search`
shape with empty `answer_text` / `citations` — rerun if you need a fully settled answer.

## 4. Output shape

`search.js` is a single expression that returns a JSON string, kept in lockstep with
`parseSearch` in [`../nodejs/perplexity.mjs`](../nodejs/perplexity.mjs):

| Extractor | Returns |
| --- | --- |
| `search.js` | one `Search` |

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in
[`results/`](results/).
