# Grok data model

Single source of truth for the Python (cerberus) and Node (zod) schemas under [`python/`](browser/python/) and [`nodejs/`](browser/nodejs/).

Grok conversation sessions require a login. Shared conversations at `grok.com/share/<id>` are publicly readable without authentication. The scraper opens the share URL, waits for the page to render, then reads the DOM anchored on `data-testid="user-message"` and `data-testid="assistant-message"` elements.

## SharedConversation — emitted by `scrape_share`

One document per shared-conversation URL.

| Field    | Type                | Required | Notes                                                                                   |
| -------- | ------------------- | -------- | --------------------------------------------------------------------------------------- |
| url      | string              | yes      | Canonical `grok.com/share/<id>` URL (after redirect `?rid=...` is stripped)            |
| title    | string              | yes      | Page `<title>` — typically `"{topic} | Shared Grok Conversation"`                      |
| messages | array of GrokMessage | yes     | Ordered user + assistant turns extracted from `[data-testid]` elements                 |

## GrokMessage — sub-object inside `SharedConversation.messages`

| Field   | Type   | Required | Notes                                                                         |
| ------- | ------ | -------- | ----------------------------------------------------------------------------- |
| role    | string | yes      | `"user"` or `"assistant"` — derived from `data-testid` attribute value        |
| content | string | yes      | Plain-text content of the message turn (whitespace-normalised)                |
