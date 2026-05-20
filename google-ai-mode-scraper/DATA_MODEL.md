# GoogleAiMode data model

Single source of truth for the Python (cerberus) and Node (zod) schemas under [`python/`](python/) and [`nodejs/`](nodejs/).

Google's AI Mode is the AI overview overlay rendered by `https://www.google.com/search?q=<query>&udm=50`. The scraper drives the SERP, waits for the AI panel to stream in, and extracts the answer text + cited links.

## AiResponse — emitted by `scrape_ai_response`

| Field         | Type     | Required | Notes                                                                       |
| ------------- | -------- | -------- | --------------------------------------------------------------------------- |
| query         | string   | yes      | Original prompt sent to Google                                              |
| url           | string   | yes      | Final SERP URL hit (with `udm=50`)                                          |
| response_text | string   | yes      | Plain-text concatenation of the AI panel                                    |
| citations     | object[] | yes      | Source citations rendered alongside the answer                              |
| links         | object[] | yes      | Outbound links surfaced in the panel (deduped)                              |

Each `citations` entry: `{ title: string, url: string, source: string }`.
Each `links` entry: `{ url: string, text: string }`.
