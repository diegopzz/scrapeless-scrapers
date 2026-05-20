# OpenSea — CLI surface

Scrape OpenSea collection and item (asset) pages from the command line with the
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
in-page extractor. Start with a collection page.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name opensea-cli --ttl 300 --proxy-country US --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate, then wait for the document body to render
scrapeless-scraping-browser --session-id "$SID" open "https://opensea.io/collection/boredapeyachtclub"
scrapeless-scraping-browser --session-id "$SID" wait "body"

# run the in-page extractor — its JSON comes back in data.result
# save the collection extractor (a single expression returning a JSON string)
cat > collection.js <<'JS'
// In-page extractor for an OpenSea collection page.
// Returns a JSON string — one Collection (see ../../../DATA_MODEL.md).
// OpenSea ships its data inside Next.js + urql hydration blobs of the form
// `(window[Symbol.for("urql_transport")] ??= []).push({...})`. This mirrors
// `extractUrqlPayloads` + `parseCollection` in ../nodejs/opensea.mjs.
JSON.stringify(
  (function () {
    const html = document.documentElement.outerHTML;

    // balancedJson: walk forward from `{` until braces balance, respecting
    // single/double quoted strings and escapes.
    const balancedJson = (s, startIdx) => {
      let i = startIdx;
      while (i < s.length && s[i] !== "{") i += 1;
      if (i >= s.length) return null;
      let depth = 0;
      let inStr = null;
      for (; i < s.length; i += 1) {
        const ch = s[i];
        if (inStr) {
          if (ch === "\\") {
            i += 1;
            continue;
          }
          if (ch === inStr) inStr = null;
          continue;
        }
        if (ch === '"' || ch === "'") {
          inStr = ch;
          continue;
        }
        if (ch === "{") depth += 1;
        else if (ch === "}") {
          depth -= 1;
          if (depth === 0) return s.slice(startIdx, i + 1);
        }
      }
      return null;
    };

    // extractUrqlPayloads
    const payloads = [];
    const needle = 'Symbol.for("urql_transport")';
    let cursor = 0;
    while (true) {
      const idx = html.indexOf(needle, cursor);
      if (idx === -1) break;
      const open = html.indexOf("push(", idx);
      if (open === -1) break;
      const start = open + "push(".length;
      const slice = balancedJson(html, start);
      if (slice) {
        try {
          payloads.push(JSON.parse(slice));
        } catch (e) {}
      }
      cursor = open + 5;
    }

    function* walkValues(obj) {
      if (obj === null || typeof obj !== "object") return;
      yield obj;
      for (const v of Object.values(obj)) yield* walkValues(v);
    }
    const findFirst = (obj, predicate) => {
      for (const node of walkValues(obj)) if (predicate(node)) return node;
      return null;
    };
    const findAll = (obj, predicate) => {
      const out = [];
      for (const node of walkValues(obj)) if (predicate(node)) out.push(node);
      return out;
    };
    const numOrNull = (v) => {
      if (v === null || v === undefined) return null;
      const n = Number(v);
      return Number.isFinite(n) ? n : null;
    };

    // slug + canonical URL come from the page location: /collection/<slug>
    const url = location.href.split("?")[0];
    const slug = decodeURIComponent(
      (location.pathname.match(/\/collection\/([^/]+)/) || [])[1] || ""
    );

    // Merge all Collection nodes that match the slug, preferring richer fields.
    const merged = {};
    for (const p of payloads) {
      for (const node of findAll(
        p,
        (n) => n && n.__typename === "Collection" && n.slug === slug
      )) {
        for (const [k, v] of Object.entries(node)) {
          if (v !== null && v !== undefined && merged[k] == null) merged[k] = v;
        }
      }
    }

    const floor = merged.floorPrice?.pricePerItem || merged.floorPrice;
    const floorToken = floor?.token || floor?.tokenPrice;
    const floorPrice = floorToken?.unit ?? null;
    const floorCurrency = floorToken?.symbol ?? "";
    const floorPriceUsd = floor?.usd ?? null;

    const chain =
      merged.chain?.identifier ||
      merged.contracts?.[0]?.chain?.identifier ||
      "";

    let volumeNative = null;
    let volumeUsd = null;
    for (const p of payloads) {
      const volNode = findFirst(
        p,
        (n) =>
          n &&
          n.volume &&
          (typeof n.volume.native === "object" ||
            typeof n.volume.unit === "number" ||
            typeof n.volume.usd === "number")
      );
      if (volNode) {
        volumeNative =
          volNode.volume?.native?.unit ?? volNode.volume?.unit ?? volumeNative;
        volumeUsd = volNode.volume?.usd ?? volumeUsd;
        if (volumeNative !== null) break;
      }
    }

    let totalSupply = merged.totalSupply ?? null;
    if (totalSupply === null) {
      let best = 0;
      for (const p of payloads) {
        for (const node of walkValues(p)) {
          if (
            node &&
            typeof node.totalSupply === "number" &&
            node.totalSupply > best
          ) {
            best = node.totalSupply;
          }
        }
      }
      if (best > 1) totalSupply = best;
    }

    const overview = merged.overview;
    const name =
      overview?.modules?.find?.((m) => m?.title)?.title ||
      merged.name ||
      slug;
    const description =
      overview?.modules
        ?.find?.((m) => m?.description)
        ?.description?.trim?.() ||
      merged.description ||
      "";
    const image =
      overview?.modules?.find?.(
        (m) => Array.isArray(m?.media) && m.media[0]?.imageUrl
      )?.media?.[0]?.imageUrl ||
      merged.imageUrl ||
      "";

    return {
      slug,
      name: String(name || "").trim(),
      description: String(description || "").trim(),
      chain: chain || "",
      total_supply: numOrNull(totalSupply),
      floor_price: numOrNull(floorPrice),
      floor_currency: String(floorCurrency || ""),
      floor_price_usd: numOrNull(floorPriceUsd),
      volume_native: numOrNull(volumeNative),
      volume_usd: numOrNull(volumeUsd),
      image: image || "",
      url,
    };
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat collection.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

OpenSea ships its data inside Next.js + urql hydration blobs; the extractor scans the raw HTML for
those payloads. `data.result` is one `Collection`:

```json
{
  "slug": "boredapeyachtclub",
  "name": "Bored Ape Yacht Club",
  "chain": "ethereum",
  "total_supply": 9998,
  "floor_price": 9.67,
  "floor_currency": "ETH",
  "volume_usd": 3740494282.07,
  "url": "https://opensea.io/collection/boredapeyachtclub"
}
```

## 4. Scrape an item (asset) page

Reuse the same session — just `open` an item URL of the form
`https://opensea.io/item/<chain>/<contract>/<tokenId>` and wait for the body again.

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://opensea.io/item/ethereum/0xbc4ca0eda7647a8ab7c2061c2e118a18a936f13d/1"
scrapeless-scraping-browser --session-id "$SID" wait "body"
# save the asset extractor (a single expression returning a JSON string)
cat > asset.js <<'JS'
// In-page extractor for an OpenSea item (asset) page.
// Returns a JSON string — one Asset (see ../../../DATA_MODEL.md).
// OpenSea ships its data inside Next.js + urql hydration blobs of the form
// `(window[Symbol.for("urql_transport")] ??= []).push({...})`. This mirrors
// `extractUrqlPayloads` + `parseAsset` in ../nodejs/opensea.mjs.
JSON.stringify(
  (function () {
    const html = document.documentElement.outerHTML;

    // balancedJson: walk forward from `{` until braces balance, respecting
    // single/double quoted strings and escapes.
    const balancedJson = (s, startIdx) => {
      let i = startIdx;
      while (i < s.length && s[i] !== "{") i += 1;
      if (i >= s.length) return null;
      let depth = 0;
      let inStr = null;
      for (; i < s.length; i += 1) {
        const ch = s[i];
        if (inStr) {
          if (ch === "\\") {
            i += 1;
            continue;
          }
          if (ch === inStr) inStr = null;
          continue;
        }
        if (ch === '"' || ch === "'") {
          inStr = ch;
          continue;
        }
        if (ch === "{") depth += 1;
        else if (ch === "}") {
          depth -= 1;
          if (depth === 0) return s.slice(startIdx, i + 1);
        }
      }
      return null;
    };

    // extractUrqlPayloads
    const payloads = [];
    const needle = 'Symbol.for("urql_transport")';
    let cursor = 0;
    while (true) {
      const idx = html.indexOf(needle, cursor);
      if (idx === -1) break;
      const open = html.indexOf("push(", idx);
      if (open === -1) break;
      const start = open + "push(".length;
      const slice = balancedJson(html, start);
      if (slice) {
        try {
          payloads.push(JSON.parse(slice));
        } catch (e) {}
      }
      cursor = open + 5;
    }

    function* walkValues(obj) {
      if (obj === null || typeof obj !== "object") return;
      yield obj;
      for (const v of Object.values(obj)) yield* walkValues(v);
    }
    const findFirst = (obj, predicate) => {
      for (const node of walkValues(obj)) if (predicate(node)) return node;
      return null;
    };
    const numOrNull = (v) => {
      if (v === null || v === undefined) return null;
      const n = Number(v);
      return Number.isFinite(n) ? n : null;
    };

    // chain / contract / tokenId + canonical URL come from the page location:
    // /item/<chain>/<contract>/<tokenId>
    const url = location.href.split("?")[0];
    const m =
      location.pathname.match(/\/item\/([^/]+)\/([^/]+)\/([^/]+)/) || [];
    const chain = decodeURIComponent(m[1] || "");
    const contract = m[2] || "";
    const tokenId = decodeURIComponent(m[3] || "");

    let item = null;
    for (const p of payloads) {
      const node = findFirst(
        p,
        (n) =>
          n &&
          n.__typename === "Item" &&
          (n.tokenId === String(tokenId) || n.tokenId === tokenId)
      );
      if (node) {
        if (!item || Object.keys(node).length > Object.keys(item).length)
          item = node;
      }
    }
    if (!item) {
      for (const p of payloads) {
        const node = findFirst(p, (n) => n && n.__typename === "Item");
        if (node) {
          item = node;
          break;
        }
      }
    }
    if (!item) {
      return {
        chain,
        contract,
        token_id: String(tokenId),
        name: "",
        url,
      };
    }

    const traits = Array.isArray(item.attributes)
      ? item.attributes.map((a) => ({
          trait_type: String(a?.traitType ?? a?.trait_type ?? "").trim(),
          value: String(a?.value ?? "").trim(),
        }))
      : [];

    const bestOffer = item.bestOffer?.pricePerItem || item.bestOffer;
    const offerToken = bestOffer?.token;

    return {
      chain: item.chain?.identifier || chain,
      contract: contract,
      token_id: String(item.tokenId ?? tokenId),
      name: String(item.name || "").trim(),
      collection_slug: item.collection?.slug || "",
      collection_name: item.collection?.name || "",
      owner: item.owner?.displayName || "",
      owner_address: item.owner?.address || "",
      rarity_rank: numOrNull(item.rarity?.rank),
      image: item.imageUrl || item.originalImageUrl || "",
      traits,
      best_offer: numOrNull(offerToken?.unit),
      best_offer_currency: String(offerToken?.symbol || ""),
      url,
    };
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat asset.js)" --json
```

`data.result` is one `Asset`:

```json
{
  "chain": "ethereum",
  "contract": "0xbc4ca0eda7647a8ab7c2061c2e118a18a936f13d",
  "token_id": "1",
  "name": "#1",
  "owner": "gordongoner",
  "rarity_rank": 2692,
  "traits": [{ "trait_type": "Background", "value": "Orange" }],
  "best_offer": 14.51,
  "best_offer_currency": "WETH",
  "url": "https://opensea.io/item/ethereum/0xbc4ca0eda7647a8ab7c2061c2e118a18a936f13d/1"
}
```

## 5. Output shape

Each `eval/*.js` file is a single expression that returns a JSON string, kept in lockstep with
`extractUrqlPayloads` + `parseCollection` / `parseAsset` in
[`../nodejs/opensea.mjs`](../nodejs/opensea.mjs):

| Extractor | Returns |
| --- | --- |
| `collection.js` | one `Collection` |
| `asset.js` | one `Asset` |

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in
[`results/`](results/).
