# Reddit — CLI surface

Scrape Reddit subreddit, post, and user pages from the command line with the
[`scrapeless-scraping-browser`](https://www.npmjs.com/package/scrapeless-scraping-browser)
CLI. One Scrapeless cloud session drives a real browser; each page is extracted in-browser with the
CLI's `eval` subcommand. Output matches the `nodejs/` and `python/` surfaces — see
[`../../DATA_MODEL.md`](../../DATA_MODEL.md).

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
in-page extractor. Reddit aggressively challenges fresh sessions, so warm up the homepage first —
that lets Reddit drop a session cookie before you navigate anywhere else. Start with a subreddit.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name reddit-cli --ttl 300 --proxy-country US --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# warm-up: load the homepage so Reddit drops a session cookie
scrapeless-scraping-browser --session-id "$SID" open "https://www.reddit.com/"
scrapeless-scraping-browser --session-id "$SID" wait "body"

# navigate to the subreddit, then wait for the post cards to render
scrapeless-scraping-browser --session-id "$SID" open "https://www.reddit.com/r/wallstreetbets/"
scrapeless-scraping-browser --session-id "$SID" wait "shreddit-post"

# run the in-page extractor — its JSON comes back in data.result
# save the subreddit extractor (a single expression returning a JSON string)
cat > subreddit.js <<'JS'
// In-page extractor for a Reddit subreddit page (www.reddit.com).
// Returns a JSON string — { info, posts } (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const url = location.href;
    const info = {};
    const parts = url.split("/r");
    info.id = parts[parts.length - 1].replaceAll("/", "");

    const header = document.querySelector("shreddit-subreddit-header");
    info.description = header?.getAttribute("description") ?? null;

    let membersText = null;
    document.querySelectorAll("faceplate-number").forEach((el) => {
      if (membersText) return;
      const sib = el.nextSibling;
      if (sib && sib.nodeType === 3 && sib.textContent && sib.textContent.includes("members")) {
        membersText = el.getAttribute("number");
      }
    });
    const weeklyActive = header?.getAttribute("weekly-active-users");
    const rank = (document.querySelector("strong#position")?.textContent ?? "").trim();
    info.rank = rank || null;
    info.members = membersText
      ? parseInt(membersText, 10)
      : (weeklyActive ? parseInt(weeklyActive, 10) : null);

    info.bookmarks = {};
    document.querySelectorAll("div faceplate-tracker[source='community_menu']").forEach((el) => {
      const a = el.querySelector("a");
      if (!a) return;
      const name = a.querySelector("span span span")?.textContent || null;
      const link = a.getAttribute("href") || null;
      if (name && link) info.bookmarks[name] = link;
    });
    info.url = url;

    const posts = [];
    document.querySelectorAll("article[data-post-id]").forEach((el) => {
      const sp = el.querySelector("shreddit-post");
      const link = el.querySelector("a")?.getAttribute("href");
      const author = sp?.getAttribute("author");
      const postLabel = (el.querySelector("span.bg-tone-4 div")?.textContent ?? "").trim() || null;
      const upvotes = sp?.getAttribute("score");
      const commentCount = sp?.getAttribute("comment-count");
      const attachmentType = sp?.getAttribute("post-type");
      let attachmentLink = null;
      if (attachmentType === "image" || attachmentType === "gallery") {
        attachmentLink = el.querySelector("img.media-lightbox-img")?.getAttribute("src") ?? null;
      } else if (attachmentType === "video") {
        attachmentLink = el.querySelector("shreddit-player")?.getAttribute("preview") ?? null;
      }
      if (!attachmentLink) attachmentLink = sp?.getAttribute("content-href") ?? null;
      posts.push({
        authorProfile: author ? `https://www.reddit.com/user/${author}` : null,
        authorId: sp?.getAttribute("author-id") ?? null,
        title: el.getAttribute("aria-label") ?? null,
        link: link ? `https://www.reddit.com${link}` : null,
        publishingDate: sp?.getAttribute("created-timestamp") ?? null,
        postId: sp?.getAttribute("id") ?? null,
        postLabel,
        postUpvotes: upvotes ? parseInt(upvotes, 10) : null,
        commentCount: commentCount ? parseInt(commentCount, 10) : null,
        attachmentType: attachmentType ?? null,
        attachmentLink,
      });
    });

    return { info, posts };
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat subreddit.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a `{ info, posts }` object — `SubredditInfo` plus a list of `SubredditPost`:

```json
{
  "info": {
    "id": "wallstreetbets",
    "description": "Like 4chan found a Bloomberg Terminal.",
    "members": 3229029,
    "bookmarks": { "Wiki": "/r/wallstreetbets/wiki/index/", "Discord": "https://discord.gg/wsbverse" },
    "url": "https://www.reddit.com/r/wallstreetbets/"
  },
  "posts": [
    { "title": "...", "link": "...", "postId": "t3_...", "postUpvotes": 331, "commentCount": 8311 }
  ]
}
```

## 4. Scrape a post

`post` is a two-page kind: the post metadata comes off `www.reddit.com`, the comment thread off the
`old.reddit.com` bulk view — the extractor merges the two into one `{ info, comments }` payload. Reuse
the same session.

```bash
# step 1 — post metadata off www.reddit.com
scrapeless-scraping-browser --session-id "$SID" open "https://www.reddit.com/r/wallstreetbets/comments/1c4vwlp/what_are_your_moves_tomorrow_april_16_2024/"
scrapeless-scraping-browser --session-id "$SID" wait "shreddit-post"
# save the post_info extractor (a single expression returning a JSON string)
cat > post_info.js <<'JS'
// In-page extractor for a Reddit post page (www.reddit.com).
// Returns a JSON string — the PostInfo block (see ../../../DATA_MODEL.md).
// Combined with post_comments.js by run.sh into the `post` { info, comments } shape.
JSON.stringify(
  (function () {
    const sp = document.querySelector("shreddit-post");
    if (!sp) return null;
    const comments = sp.getAttribute("comment-count");
    const upvotes = sp.getAttribute("score");
    const author = sp.getAttribute("author");
    return {
      authorId: sp.getAttribute("author-id") ?? null,
      author: author ?? null,
      authorProfile: author ? `https://www.reddit.com/user/${author}` : null,
      subreddit: (sp.getAttribute("subreddit-prefixed-name") ?? "").replace("r/", ""),
      postId: sp.getAttribute("id") ?? null,
      postLabel:
        (document.querySelector("faceplate-tracker[source='post'] a span div")?.textContent ?? "").trim() || null,
      publishingDate: sp.getAttribute("created-timestamp") ?? null,
      postTitle: sp.getAttribute("post-title") ?? null,
      postLink: document.querySelector("shreddit-canonical-url-updater")?.getAttribute("value") ?? null,
      commentCount: comments ? parseInt(comments, 10) : null,
      upvoteCount: upvotes ? parseInt(upvotes, 10) : null,
      attachmentType: sp.getAttribute("post-type") ?? null,
      attachmentLink: sp.getAttribute("content-href") ?? null,
    };
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat post_info.js)" --json

# step 2 — the comment thread off the old.reddit.com bulk view
scrapeless-scraping-browser --session-id "$SID" open "https://old.reddit.com/r/wallstreetbets/comments/1c4vwlp/what_are_your_moves_tomorrow_april_16_2024/?sort=top&limit=500"
scrapeless-scraping-browser --session-id "$SID" wait "div.sitetable.nestedlisting"
# save the post_comments extractor (a single expression returning a JSON string)
cat > post_comments.js <<'JS'
// In-page extractor for a Reddit post's comment thread (old.reddit.com).
// Returns a JSON string — a recursive list of PostComment (see ../../../DATA_MODEL.md).
// Combined with post_info.js by run.sh into the `post` { info, comments } shape.
JSON.stringify(
  (function () {
    function parseComment(box) {
      const author = box.getAttribute("data-author");
      const link = box.getAttribute("data-permalink");
      const dislikes = box.querySelector("span.dislikes")?.getAttribute("title");
      const upvotes = box.querySelector("span.likes")?.getAttribute("title");
      const downvotes = box.querySelector("span.unvoted")?.getAttribute("title");
      return {
        authorId: box.getAttribute("data-author-fullname") ?? null,
        author: author ?? null,
        authorProfile: author ? `https://www.reddit.com/user/${author}` : null,
        commentId: box.getAttribute("data-fullname") ?? null,
        link: link ? `https://www.reddit.com${link}` : null,
        publishingDate: box.querySelector("time")?.getAttribute("datetime") ?? null,
        commentBody: box.querySelector("div.md > p")?.textContent || null,
        upvotes: upvotes ? parseInt(upvotes, 10) : null,
        dislikes: dislikes ? parseInt(dislikes, 10) : null,
        downvotes: downvotes ? parseInt(downvotes, 10) : null,
      };
    }

    function parseReplies(what) {
      const replies = [];
      what.querySelectorAll("div[data-type='comment']").forEach((el) => {
        const replyComment = parseComment(el);
        const childReplies = parseReplies(el);
        if (childReplies.length) replyComment.replies = childReplies;
        replies.push(replyComment);
      });
      return replies;
    }

    const data = [];
    document
      .querySelectorAll("div.sitetable.nestedlisting > div[data-type='comment']")
      .forEach((el) => {
        const commentData = parseComment(el);
        const replies = parseReplies(el);
        if (replies.length) commentData.replies = replies;
        data.push(commentData);
      });
    return data;
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat post_comments.js)" --json
```

`post_info.js` returns one `PostInfo`; `post_comments.js` returns a recursive list of `PostComment`.
the extractor merges them into `{ info, comments }`:

```json
{
  "info": {
    "author": "wsbapp",
    "subreddit": "wallstreetbets",
    "postId": "t3_1c4vwlp",
    "postTitle": "What Are Your Moves Tomorrow, April 16, 2024",
    "commentCount": 8311,
    "upvoteCount": 331
  },
  "comments": [
    { "author": "Maverick2937474838", "commentId": "t1_kzq97qi", "commentBody": "<image>", "upvotes": 163, "replies": [] }
  ]
}
```

## 5. Scrape a user's posts

Reuse the session — `open` the user's submitted-posts page and wait for the post cards.

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://www.reddit.com/user/spez/submitted/?sort=new"
scrapeless-scraping-browser --session-id "$SID" wait "shreddit-post"
# save the user_posts extractor (a single expression returning a JSON string)
cat > user_posts.js <<'JS'
// In-page extractor for a Reddit user's submitted-posts page (www.reddit.com).
// Returns a JSON string — a list of UserPost (see ../../../DATA_MODEL.md).
JSON.stringify(
  Array.from(document.querySelectorAll("shreddit-post")).map((sp) => {
    const author = sp.getAttribute("author") || null;
    const permalink = sp.getAttribute("permalink") || null;
    const commentCount = sp.getAttribute("comment-count");
    const postScore = sp.getAttribute("score");
    const subreddit = sp.getAttribute("subreddit-prefixed-name") || null;
    const postType = sp.getAttribute("post-type") || null;
    let attachmentLink = sp.getAttribute("content-href") || null;
    if (attachmentLink && attachmentLink.startsWith("/")) {
      attachmentLink = `https://www.reddit.com${attachmentLink}`;
    }
    return {
      authorId: sp.getAttribute("author-id") || null,
      author,
      authorProfile: author ? `https://www.reddit.com/user/${author}` : null,
      postId: sp.getAttribute("id") || null,
      postLink: permalink ? `https://www.reddit.com${permalink}` : null,
      postTitle: sp.getAttribute("post-title") || null,
      postSubreddit: subreddit,
      publishingDate: sp.getAttribute("created-timestamp") || null,
      commentCount: commentCount ? parseInt(commentCount, 10) : null,
      postScore: postScore ? parseInt(postScore, 10) : null,
      attachmentType: postType,
      attachmentLink,
    };
  })
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat user_posts.js)" --json
```

`data.result` is a list of `UserPost`:

```json
[
  {
    "author": "spez",
    "postId": "t3_1t4nr7v",
    "postLink": "https://www.reddit.com/user/spez/comments/1t4nr7v/reddit_looked_old_the_day_it_was_born_i_joined_my/",
    "postTitle": "Reddit looked old the day it was born. ...",
    "postSubreddit": "u_spez",
    "commentCount": 35,
    "postScore": 47
  }
]
```

## 6. Scrape a user's comments

Same session — `open` the user's comments page and wait for the profile-comment elements.

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://www.reddit.com/user/spez/comments/?sort=new"
scrapeless-scraping-browser --session-id "$SID" wait "shreddit-profile-comment"
# save the user_comments extractor (a single expression returning a JSON string)
cat > user_comments.js <<'JS'
// In-page extractor for a Reddit user's comments page (www.reddit.com).
// Returns a JSON string — a list of UserComment (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    // The author isn't on each comment node — it's the profile being viewed.
    const userMatch = location.pathname.match(/\/user\/([^/]+)/);
    const username = userMatch ? userMatch[1] : null;

    return Array.from(document.querySelectorAll("shreddit-profile-comment")).map((c) => {
      const commentId = c.getAttribute("comment-id") || null;
      const href = c.getAttribute("href") || null; // /r/<sub>/comments/<post>/comment/<id>/

      const ariaLabel = (
        c.querySelector("a[aria-label*='comment on']")?.getAttribute("aria-label") || ""
      ).trim();
      let postTitle = null;
      let postAuthor = null;
      const m = /^Thread for ([^']+)'s comment on (.+)$/.exec(ariaLabel);
      if (m) {
        postAuthor = m[1];
        postTitle = m[2];
      }

      let postSubreddit = null;
      if (href) {
        const sm = /^\/r\/([^/]+)\//.exec(href);
        if (sm) postSubreddit = `r/${sm[1]}`;
      }

      const bodyEl = c.querySelector(
        "div[id*='comment'][slot='comment'], div.md, div.text-14, p"
      );
      const commentBody = (bodyEl?.textContent || "").trim();

      const attachedLinks = Array.from(c.querySelectorAll("a[href^='http']"))
        .map((a) => a.getAttribute("href"))
        .filter((u) => u && !u.includes("reddit.com"));

      let parentLink = null;
      if (href) {
        parentLink = `https://www.reddit.com${href.split("/comment/")[0]}/`;
      }

      return {
        authorId: null,
        author: username,
        authorProfile: username ? `https://www.reddit.com/user/${username}` : null,
        commentId,
        commentLink: href ? `https://www.reddit.com${href}` : null,
        commentBody,
        attachedCommentLinks: attachedLinks,
        publishingDate:
          c.querySelector("faceplate-timeago time")?.getAttribute("datetime") ||
          c.querySelector("time")?.getAttribute("datetime") ||
          null,
        dislikes: null,
        upvotes: null,
        downvotes: null,
        replyTo: {
          postTitle,
          postLink: parentLink,
          postAuthor,
          postSubreddit,
        },
      };
    });
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat user_comments.js)" --json
```

`data.result` is a list of `UserComment`:

```json
[
  {
    "author": "spez",
    "commentId": "t1_cszv2lg",
    "commentLink": "https://www.reddit.com/r/IAmA/comments/3cxedn/comment/cszv2lg/?context=3",
    "commentBody": "Absolutely. Shadowbanning is for spammers. ...",
    "publishingDate": "2015-07-11T17:51:48.883Z",
    "replyTo": { "postTitle": "I am Steve Huffman, the new CEO of reddit. AMA.", "postSubreddit": "r/IAmA" }
  }
]
```

## 7. Output shape

Each `eval/*.js` file is a single expression that returns a JSON string, kept in lockstep with the
selectors in [`../nodejs/reddit.mjs`](../nodejs/reddit.mjs):

| Extractor | Returns |
| --- | --- |
| `subreddit.js` | `{ info, posts }` — one `SubredditInfo` + list of `SubredditPost` |
| `post_info.js` | one `PostInfo` (off `www.reddit.com`) |
| `post_comments.js` | recursive list of `PostComment` (off `old.reddit.com`) |
| `user_posts.js` | list of `UserPost` |
| `user_comments.js` | list of `UserComment` |

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in
[`results/`](results/).
