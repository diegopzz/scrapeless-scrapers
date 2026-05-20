# Perplexity data model

Single source of truth for the Python (cerberus) and Node (zod) schemas under [`python/`](python/) and [`nodejs/`](nodejs/).

The scraper navigates to `https://www.perplexity.ai/`, types the prompt into the Lexical contenteditable input, presses Enter, and waits for the answer page (`/search/<uuid>`) to render. Question lives inside `<h1 class="group/query …">`; the answer is inside the first `<div class="prose …">`; citations are deduped outbound `<a href>` elements that aren't Perplexity-internal.

## Search — emitted by `scrape_search`

| Field         | Type     | Required | Notes                                                                  |
| ------------- | -------- | -------- | ---------------------------------------------------------------------- |
| query         | string   | yes      | Original prompt submitted to Perplexity                                |
| url           | string   | yes      | Canonical Perplexity answer URL (`/search/<uuid>`)                     |
| answer_text   | string   | yes      | Plain-text concatenation of the answer prose                           |
| citations     | object[] | yes      | Deduped outbound citations: `{ url, domain, title }`                   |
