# Grok — CLI surface

Scrape public Grok shared conversations from the command line with the
[`scrapeless-scraping-browser`](https://www.npmjs.com/package/scrapeless-scraping-browser)
CLI. One Scrapeless cloud session drives a real browser; the conversation is extracted
in-browser with the CLI's `eval` subcommand. Output matches the `nodejs/` and `python/`
surfaces — see [`../../DATA_MODEL.md`](../../DATA_MODEL.md).

## 1. Install

```bash
npm install -g scrapeless-scraping-browser
```

`node` is also required for URL-encoding.

## 2. Set your API key

```bash
export SCRAPELESS_API_KEY=sk_...      # sign up at https://app.scrapeless.com
```

## 3. Scrape a shared conversation

Grok shared conversations at `grok.com/share/<id>` are publicly readable.
The `open` command resolves Cloudflare and renders the page; the CLI's default
`load` wait-until is sufficient — do **not** add an additional `wait` call, as
Grok's Cloudflare challenge may terminate the session if the browser sits idle.

```bash
# open a cloud browser session
scrapeless-scraping-browser new-session --name grok-cli --ttl 300 --proxy-country US --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# open the shared conversation (no extra wait needed)
scrapeless-scraping-browser --session-id "$SID" open \
  "https://grok.com/share/bGVnYWN5_d6991719-5568-4608-b613-609cbd3f2842"

# run the in-page extractor
scrapeless-scraping-browser --session-id "$SID" eval "$(cat share.js)" --json

# release the session
scrapeless-scraping-browser --session-id "$SID" close
```

Save the extractor as `share.js`:

```js
// In-page extractor for a Grok shared-conversation page (grok.com/share/<id>).
// Returns a JSON string — one SharedConversation (see ../../../DATA_MODEL.md).
// Mirrors parseShare() in ../nodejs/grok.mjs.
JSON.stringify(
  (function () {
    // Strip the ?rid=... redirect token Grok appends.
    var url = location.href.replace(/\?rid=[^&]+(&|$)/, "").replace(/\?$/, "");

    var title = document.title;

    var messages = [];
    document
      .querySelectorAll(
        "[data-testid='user-message'], [data-testid='assistant-message']"
      )
      .forEach(function (el) {
        var testid = el.getAttribute("data-testid") || "";
        var text = (el.textContent || "").replace(/\s+/g, " ").trim();
        if (!text) return;
        messages.push({
          role: testid === "user-message" ? "user" : "assistant",
          content: text,
        });
      });

    return { url: url, title: title, messages: messages };
  })()
);
```

`data.result` is one `SharedConversation`:

```json
{
  "url": "https://grok.com/share/bGVnYWN5_d6991719-5568-4608-b613-609cbd3f2842",
  "title": "2025 NZ Rugby Collective Agreement Analysis | Shared Grok Conversation",
  "messages": [
    { "role": "user", "content": "Please analyse this file and list anything you think is noteworthy" },
    { "role": "assistant", "content": "The document is a comprehensive Collective Agreement..." }
  ]
}
```

## 4. Output shape

`share.js` returns a single `SharedConversation` in lockstep with `parseShare()` in
[`../nodejs/grok.mjs`](../nodejs/grok.mjs):

| Extractor  | Returns |
| ---------- | ------- |
| `share.js` | one `SharedConversation` |

Full field tables are in [`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in
[`results/`](results/).
