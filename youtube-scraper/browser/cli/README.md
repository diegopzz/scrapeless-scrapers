# YouTube — CLI surface

Scrape YouTube watch pages from the command line with the
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

## 3. Scrape a video page

Every scrape is the same four moves: open a session, navigate, wait for a stable marker, run an
in-page extractor. The CLI surface covers the `video` kind — a watch page identified by its video
ID.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name youtube-cli --ttl 300 --proxy-country US --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate, then wait for the watch page shell
scrapeless-scraping-browser --session-id "$SID" open "https://www.youtube.com/watch?v=1Y-XvvWlyzk"
scrapeless-scraping-browser --session-id "$SID" wait "ytd-watch-flexy"

# run the in-page extractor — its JSON comes back in data.result
# save the video extractor (a single expression returning a JSON string)
cat > video.js <<'JS'
// In-page extractor for a YouTube watch page.
// Returns a JSON string — a single Video wrapper { video, channel,
// commentContinuationToken } (see ../../../DATA_MODEL.md).
//
// Mirrors parseVideo() in ../nodejs/youtube.mjs: reads videoDetails out of
// `ytInitialPlayerResponse` and the richer render tree out of `ytInitialData`,
// both embedded in <script> tags. The jsonpath-plus lookups used by the SDK
// surface are re-expressed here as small recursive walkers.
JSON.stringify(
  (function () {
    // Collect all inline <script> text once.
    const scripts = Array.from(document.querySelectorAll("script")).map(
      (s) => s.textContent || ""
    );

    const grab = (re) => {
      for (const t of scripts) {
        const m = re.exec(t);
        if (m) {
          try {
            return JSON.parse(m[1]);
          } catch (e) {}
        }
      }
      return {};
    };

    const playerResponse = grab(
      /ytInitialPlayerResponse\s*=\s*({.*?});/s
    );
    const videoDetails = playerResponse.videoDetails ?? {};
    const contentDetails = grab(/var ytInitialData = ({.*?});/s);

    // --- recursive walkers (jsonpath-plus $..key analogues) ---
    // jpAll: every value found under `key`, anywhere in the tree.
    const jpAll = (root, key) => {
      const out = [];
      const seen = new Set();
      const walk = (node) => {
        if (node == null || typeof node !== "object") return;
        if (seen.has(node)) return;
        seen.add(node);
        if (Array.isArray(node)) {
          for (const v of node) walk(v);
          return;
        }
        for (const k of Object.keys(node)) {
          if (k === key) out.push(node[k]);
          walk(node[k]);
        }
      };
      walk(root);
      return out;
    };
    // jpFirst: first value found under a dotted path of plain keys,
    // searched anywhere in the tree (e.g. "dateText.simpleText").
    const jpFirstPath = (root, dottedPath) => {
      const parts = dottedPath.split(".");
      const head = parts[0];
      const candidates = jpAll(root, head);
      for (const c of candidates) {
        let v = c;
        for (let i = 1; i < parts.length && v != null; i++) {
          v = typeof v === "object" ? v[parts[i]] : undefined;
        }
        if (v != null) return v;
      }
      return null;
    };

    const convertToNumber = (value) => {
      if (value == null) return null;
      const s = String(value).trim().toUpperCase().replace(/,/g, "");
      if (!s) return null;
      const token = s.split(/\s+/)[0];
      if (token.endsWith("K")) {
        const n = parseFloat(token.slice(0, -1));
        return Number.isFinite(n) ? Math.floor(n * 1000) : null;
      }
      if (token.endsWith("M")) {
        const n = parseFloat(token.slice(0, -1));
        return Number.isFinite(n) ? Math.floor(n * 1000000) : null;
      }
      const n = parseFloat(token);
      return Number.isFinite(n) ? Math.floor(n) : null;
    };

    // likes: LIKE buttonViewModel titles.
    const likes = jpAll(contentDetails, "buttonViewModel")
      .filter((i) => i && i.iconName === "LIKE" && typeof i.title === "string")
      .map((i) => i.title);

    // channelId: first channelEndpoint.browseEndpoint.canonicalBaseUrl.
    const channelEndpoints = jpAll(contentDetails, "channelEndpoint");
    let channelId = null;
    for (const ce of channelEndpoints) {
      const c = ce?.browseEndpoint?.canonicalBaseUrl;
      if (c != null) {
        channelId = c;
        break;
      }
    }

    // verified: a videoOwnerRenderer with a Verified metadata badge.
    const owners = jpAll(contentDetails, "videoOwnerRenderer");
    const verified = owners.some((o) => {
      const b = o?.badges?.[0]?.metadataBadgeRenderer;
      return b && b.tooltip === "Verified";
    });

    const thumbnail = videoDetails?.thumbnail?.thumbnails ?? null;

    return {
      video: {
        videoId: videoDetails.videoId ?? null,
        title: videoDetails.title ?? null,
        publishingDate: jpFirstPath(contentDetails, "dateText.simpleText"),
        lengthSeconds: convertToNumber(videoDetails.lengthSeconds),
        keywords: videoDetails.keywords ?? null,
        description: videoDetails.shortDescription ?? null,
        thumbnail,
        stats: {
          viewCount: convertToNumber(videoDetails.viewCount),
          likeCount: likes.length ? convertToNumber(likes[0]) : null,
          commentCount: convertToNumber(
            jpFirstPath(contentDetails, "contextualInfo.runs")?.[0]?.text
          ),
        },
      },
      channel: {
        name: videoDetails.author ?? null,
        identifierId: videoDetails.channelId ?? null,
        id: channelId ? String(channelId).replace(/\//g, "") : null,
        verified,
        channelUrl: channelId
          ? `https://www.youtube.com${channelId}`
          : null,
        subscriberCount: jpFirstPath(
          contentDetails,
          "subscriberCountText.simpleText"
        ),
        thumbnails: (function () {
          const panels = jpAll(
            contentDetails,
            "engagementPanelSectionListRenderer"
          );
          for (const p of panels) {
            const t = jpFirstPath(p, "channelThumbnail.thumbnails");
            if (t != null) return t;
          }
          return null;
        })(),
      },
      commentContinuationToken: (function () {
        const cmds = jpAll(contentDetails, "continuationCommand");
        for (const c of cmds) {
          if (c?.token != null) return c.token;
        }
        return null;
      })(),
    };
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat video.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a `Video` wrapper — `{ video, channel, commentContinuationToken }`, parsed from
the embedded `ytInitialPlayerResponse` (videoDetails) and `ytInitialData` (render tree):

```json
{
  "video": {
    "videoId": "dQw4w9WgXcQ",
    "title": "Rick Astley - Never Gonna Give You Up (Official Video) (4K Remaster)",
    "publishingDate": "Oct 24, 2009",
    "lengthSeconds": 213,
    "keywords": ["rick astley", "Never Gonna Give You Up", "..."],
    "stats": { "viewCount": 1, "likeCount": 1, "commentCount": 1 }
  },
  "channel": { "name": "...", "channelUrl": "...", "subscriberCount": "..." },
  "commentContinuationToken": "..."
}
```

the extractor wraps this object in a one-element list so the saved fixture stays shape-identical with the
`scrape_video` output of the other surfaces.

## 4. Output shape

`video.js` is a single expression that returns a JSON string, kept in lockstep with the
selectors in [`../nodejs/youtube.mjs`](../nodejs/youtube.mjs):

| Extractor | Returns |
| --- | --- |
| `video.js` | one `Video` wrapper (`{ video, channel, commentContinuationToken }`) |

The `comments`, `channel`, `channel_videos`, `search`, and `shorts` kinds are **not** part of this
surface — `comments`, `channel_videos`, and `search` come from YouTube's internal `youtubei/v1`
endpoints (`POST` requests issued from inside the live page so cookies and visitor data are real),
which doesn't fit the CLI's in-page `eval` model. Use the `nodejs/` or `python/` surface for those.

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in
[`results/`](results/).
