# ChatGPT data model

ChatGPT is scraped against the **anonymous** entry point (`chatgpt.com/?prompt=...`). The browser navigates with the seeded prompt, the send button is clicked, and the SSE stream from `/backend-anon/f/conversation` is captured + parsed. For follow-ups, in-page `fetch()` POSTs to `/backend-anon/conversation` keep the cookies and Cloudflare anti-bot context alive.

## ChatResponse

Returned by `scrape_conversation(prompt)` — a single string with the assistant's reply (joined across all assistant message parts in the SSE stream).

| Field    | Type   | Required | Notes                                                                 |
| -------- | ------ | -------- | --------------------------------------------------------------------- |
| (return) | string | yes      | Plain-text assistant reply, mirrors the upstream reference's `format="markdown"`    |

## ChatgptMessage

Sub-object inside `ChatgptConversation.messages`.

| Field   | Type   | Required | Notes                                                  |
| ------- | ------ | -------- | ------------------------------------------------------ |
| role    | string | yes      | `"user"`, `"assistant"`, or `"system"` (from SSE)      |
| content | string | yes      | Message body (parts[0] for user, full text for asst.)  |

## ChatgptConversation

Returned by `scrape_conversations(prompts)` — one element per anonymous conversation. The list is keyed by the order conversations are spawned (typically one per call).

| Field            | Type                   | Required | Notes                                                |
| ---------------- | ---------------------- | -------- | ---------------------------------------------------- |
| conversation_id  | string                 | yes      | UUID returned by ChatGPT in the SSE preamble         |
| messages         | array of ChatgptMessage | yes     | Accumulated user + assistant messages across turns   |
