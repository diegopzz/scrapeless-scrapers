# Xbox — CLI surface

Scrape Xbox store product pages and the games discovery hub from the command line with the
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

## 3. Scrape a product page

Every scrape is the same four moves: open a session, navigate, wait for a stable marker, run an
in-page extractor. Xbox store pages ship a single `application/ld+json` script wrapping every node
under `@graph`; the `Product` entry carries the structured payload. Start there.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name xbox-cli --ttl 300 --proxy-country US --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate, then wait for the ld+json script to render
scrapeless-scraping-browser --session-id "$SID" open "https://www.xbox.com/en-us/games/store/marvel-rivals/9N8PMW7QMD3D"
scrapeless-scraping-browser --session-id "$SID" wait "script[type='application/ld+json']"

# run the in-page extractor — its JSON comes back in data.result
# save the product extractor (a single expression returning a JSON string)
cat > product.js <<'JS'
// In-page extractor for an Xbox /games/store product page.
// Returns a JSON string — a single Product (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const ORIGIN = "https://www.xbox.com";
    const graph = [];
    document
      .querySelectorAll('script[type="application/ld+json"]')
      .forEach((el) => {
        const txt = el.textContent;
        if (!txt) return;
        try {
          const obj = JSON.parse(txt);
          if (Array.isArray(obj["@graph"])) graph.push(...obj["@graph"]);
          else graph.push(obj);
        } catch (e) {}
      });

    let prod = null;
    for (const n of graph) {
      const t = n && n["@type"];
      if (t === "Product" || (Array.isArray(t) && t.includes("Product"))) {
        prod = n;
        break;
      }
    }
    if (!prod) throw new Error("could not find Product node in ld+json @graph");

    const url = location.href;
    const idMatch = url.match(/\/games\/store\/[^/]+\/([A-Za-z0-9]+)/);
    const id = idMatch ? idMatch[1] : "";

    const offersRaw = Array.isArray(prod.offers)
      ? prod.offers
      : prod.offers
      ? [prod.offers]
      : [];
    const firstOffer = offersRaw[0] ?? {};

    const images = Array.isArray(prod.image)
      ? prod.image
      : prod.image
      ? [prod.image]
      : [];
    const videosRaw = Array.isArray(prod.video)
      ? prod.video
      : prod.video
      ? [prod.video]
      : [];
    const videos = videosRaw.map((v) => ({
      name: v?.name ?? null,
      thumbnailUrl: v?.thumbnailUrl ?? null,
      contentUrl: v?.contentUrl ?? null,
    }));

    const rating = prod.aggregateRating ?? {};

    return {
      id,
      name: prod.name ?? "",
      description: prod.description ?? null,
      url: prod.url ?? url,
      image: images[0] ?? null,
      publisher: prod.publisher?.name ?? null,
      developer: prod.creator?.name ?? null,
      brand: prod.brand?.name ?? null,
      genre: Array.isArray(prod.genre)
        ? prod.genre
        : prod.genre
        ? [prod.genre]
        : [],
      platforms: Array.isArray(prod.gamePlatform)
        ? prod.gamePlatform
        : prod.gamePlatform
        ? [prod.gamePlatform]
        : [],
      contentRating: prod.contentRating ?? null,
      releaseDate: prod.datePublished ?? null,
      ratingValue: rating.ratingValue != null ? Number(rating.ratingValue) : null,
      ratingCount: rating.ratingCount != null ? Number(rating.ratingCount) : null,
      price: firstOffer.price != null ? String(firstOffer.price) : null,
      priceCurrency: firstOffer.priceCurrency ?? null,
      availability: firstOffer.availability ?? null,
      isFree: prod.isAccessibleForFree ?? null,
      featureList: prod.featureList ?? null,
      videos,
    };
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat product.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a `Product` object, lifted from the `@graph` Product node:

```json
{
  "id": "9N8PMW7QMD3D",
  "name": "Marvel Rivals",
  "url": "https://www.xbox.com/en-us/games/store/marvel-rivals/9N8PMW7QMD3D",
  "publisher": "NetEase Games",
  "genre": ["Action & adventure", "Shooter"],
  "platforms": ["PC", "Xbox Series X|S"],
  "contentRating": "Teen",
  "ratingValue": 4.5,
  "price": "0",
  "priceCurrency": "USD",
  "isFree": true,
  "videos": [{ "name": "Trailer", "thumbnailUrl": "...", "contentUrl": "..." }]
}
```

## 4. Scrape the games hub

Reuse the same session — `open` the `/en-us/games/all-games` discovery hub and wait for the game
tiles. Xbox.com has no true search SERP, so this hub is the discovery surface; the extractor lifts
every `<a href="/games/store/<slug>/<storeId>">` tile from the SSR HTML.

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://www.xbox.com/en-us/games/all-games"
scrapeless-scraping-browser --session-id "$SID" wait "a[href*='/games/store/']"
# save the search extractor (a single expression returning a JSON string)
cat > search.js <<'JS'
// In-page extractor for an Xbox /games discovery (all-games) page.
// Returns a JSON string — a list of SearchResult (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const ORIGIN = "https://www.xbox.com";
    const TILE_RE = /\/games\/store\/([^/?#]+)\/([A-Za-z0-9]{6,})/i;

    const abs = (u) => {
      if (!u) return null;
      if (u.startsWith("//")) return `https:${u}`;
      if (u.startsWith("/")) return `${ORIGIN}${u}`;
      return u;
    };

    const aria_to_parts = (label) => {
      if (!label) return { name: null, badge: null };
      const cleaned = label
        .replace(/\.\s*Opens in a new tab\s*$/i, "")
        .trim();
      const parts = cleaned.split(". ");
      if (parts.length >= 2 && /^[A-Z0-9 +!&'-]+$/.test(parts[0])) {
        return { badge: parts[0].trim(), name: parts[1].trim() };
      }
      return { badge: null, name: parts[0]?.trim() ?? null };
    };

    const seen = new Set();
    const out = [];
    document.querySelectorAll("a[href*='/games/store/']").forEach((a) => {
      let href = a.getAttribute("href") || "";
      const m = href.match(TILE_RE);
      if (!m) return;
      if (href.includes("?icid=CNav")) return;
      const id = m[2];
      if (seen.has(id)) return;
      seen.add(id);

      if (!href.startsWith("http")) href = abs(href);

      const aria = a.getAttribute("aria-label") || "";
      const innerTitle =
        (a.querySelector("h3, h2, span.c-meta-h3")?.textContent ?? "").trim() ||
        (a.querySelector("[class*='title' i], [class*='Title']")?.textContent ??
          "").trim() ||
        "";

      const { badge, name } = aria_to_parts(aria);
      const finalName = innerTitle || name || m[1].replace(/-/g, " ");
      if (!finalName) return;

      const img =
        a.querySelector("img")?.getAttribute("src") ||
        a.parentElement?.querySelector("img")?.getAttribute("src") ||
        null;

      out.push({
        id,
        slug: m[1],
        name: finalName,
        url: href,
        image: img,
        badge: badge,
      });
    });
    return out;
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat search.js)" --json
```

`data.result` is a list of `SearchResult`:

```json
[
  {
    "id": "9N8PMW7QMD3D",
    "slug": "marvel-rivals",
    "name": "Marvel Rivals",
    "url": "https://www.xbox.com/en-us/games/store/marvel-rivals/9N8PMW7QMD3D",
    "image": "https://store-images.s-microsoft.com/image/...",
    "badge": "GAME PASS"
  }
]
```

## 5. Output shape

Each extractor is a single expression that returns a JSON string, kept in
lockstep with the selectors in [`../nodejs/xbox.mjs`](../nodejs/xbox.mjs):

| Extractor   | Returns |
| ----------- | --- |
| `PRODUCT_JS` | one `Product` |
| `SEARCH_JS`  | list of `SearchResult` |

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in
[`results/`](results/).
