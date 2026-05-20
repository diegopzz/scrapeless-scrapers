# Reddit — MCP surface

Scrape Reddit subreddit, post, and user pages conversationally from any MCP-capable AI agent or client. No code — the LLM drives a Scrapeless cloud browser through MCP tools
and you ask for the fields described in [`../../DATA_MODEL.md`](../../DATA_MODEL.md).

## 1. Install the scrapeless-mcp-server

Install the [`scrapeless-mcp-server`](https://github.com/scrapeless-ai/scrapeless-mcp-server) and add it from [`mcp.json`](mcp.json) to your MCP client:

```jsonc
{
  "mcpServers": {
    "scrapeless": {
      "command": "npx",
      "args": ["-y", "scrapeless-mcp-server"],
      "env": { "SCRAPELESS_KEY": "sk_..." }
    }
  }
}
```

Any MCP-capable AI agent or client works. Add the block above wherever your client stores its MCP servers. Two transports are available:

- **stdio** (shown above) — the client launches `npx -y scrapeless-mcp-server`.
- **HTTP** — agents that connect to a remote MCP URL can point at `https://api.scrapeless.com/mcp` with the header `x-api-token: sk_...`.

## 2. Set your API key

Use the key from [app.scrapeless.com](https://app.scrapeless.com) as `SCRAPELESS_KEY` in the config
above. Sign up there if you do not have one yet — new accounts include free Scraping Browser
runtime.

## 3. Scrape a subreddit

Once the server is connected, ask in plain language. Reddit challenges fresh sessions, so ask the
model to warm up the homepage first. Start with a subreddit:

```
Using the scrapeless tools, open https://www.reddit.com/ to warm up, then open
https://www.reddit.com/r/wallstreetbets/ and return { info, posts } — info as the
SubredditInfo fields (id, description, rank, members, bookmarks, url) and each
post as the SubredditPost fields from ../../DATA_MODEL.md (title, link, postId,
postUpvotes, commentCount, attachmentType, attachmentLink, ...).
```

## 4. Scrape a post

`post` is a two-page kind — the post metadata comes off `www.reddit.com`, the comment thread off the
`old.reddit.com` bulk view:

```
Open https://www.reddit.com/r/wallstreetbets/comments/1c4vwlp/what_are_your_moves_tomorrow_april_16_2024/
with the scrapeless browser and return the PostInfo fields (author, subreddit,
postId, postTitle, commentCount, upvoteCount). Then open the same thread on
https://old.reddit.com/...?sort=top&limit=500 and return the comment tree as a
recursive list of PostComment { author, commentId, commentBody, upvotes, replies }.
Merge them into { info, comments }.
```

## 5. Scrape a user's posts and comments

```
Open https://www.reddit.com/user/spez/submitted/?sort=new with the scrapeless
browser and return each post as a UserPost { author, postId, postLink, postTitle,
postSubreddit, commentCount, postScore, ... }.
```

```
Open https://www.reddit.com/user/spez/comments/?sort=new and return each comment
as a UserComment { author, commentId, commentLink, commentBody, publishingDate,
replyTo }.
```

## 6. Output shape

The MCP surface emits whatever shape you ask for. To stay aligned with the `cli/`, `nodejs/`, and
`python/` surfaces, ask for the `SubredditInfo`/`SubredditPost`, `PostInfo`/`PostComment`,
`UserPost`, and `UserComment` fields documented in [`../../DATA_MODEL.md`](../../DATA_MODEL.md).
Sample payloads are in [`results/`](results/).

## 7. Notes

- Tool arguments are camelCase (`sessionId`, `proxyCountry`); `browser_close` rejects snake_case.
- Reddit aggressively challenges fresh sessions — warm up on `https://www.reddit.com/` first so
  Reddit drops a session cookie before navigating to a subreddit / user / post page.
- The post comment thread lives on `old.reddit.com` (Listing-of-Things markup), not the
  `shreddit-*` custom elements of `www.reddit.com` — rewrite `www` → `old` and append
  `?sort=top&limit=500` to pull the full tree.
- For repeatable, schema-validated output, use the `cli/`, `nodejs/`, or `python/` surfaces — the
  MCP surface is best for ad-hoc, conversational scraping.
