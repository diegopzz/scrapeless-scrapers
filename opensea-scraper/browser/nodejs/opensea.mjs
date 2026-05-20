// OpenSea scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// OpenSea ships its page data inside Next.js + urql hydration blobs of the
// form:
//   (window[Symbol.for("urql_transport")] ??= []).push({"rehydrate": {...}})
// The scraper renders the page in Scrapeless's Scraping Browser, harvests
// every `urql_transport` push, and folds the GraphQL responses into either
// a `Collection` or an `Asset` object.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";

const DEFAULT_PROXY_COUNTRY = "US";
const DEFAULT_SESSION_TTL = 240;

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}

function client() {
  return new Scrapeless({ apiKey: requireKey() });
}

async function fetchRenderedHtml(url, { proxyCountry = DEFAULT_PROXY_COUNTRY, retries = 1, settleMs = 6000 } = {}) {
  let lastError;
  for (let attempt = 0; attempt <= retries; attempt++) {
    const { browserWSEndpoint } = await client().browser.create({
      proxyCountry,
      sessionTTL: DEFAULT_SESSION_TTL,
    });
    let browser;
    try {
      browser = await puppeteer.connect({ browserWSEndpoint });
      const page = await browser.newPage();
      await page.setViewport({ width: 1440, height: 900 });
      await page.goto(url, { waitUntil: "networkidle2", timeout: 60000 });
      await new Promise((r) => setTimeout(r, settleMs));
      const html = await page.content();
      if (html && html.includes('urql_transport')) return html;
      lastError = new Error("no urql_transport blob in HTML");
    } catch (e) {
      lastError = e;
    } finally {
      try { await browser?.close(); } catch (_) {}
    }
    if (attempt < retries) await new Promise((r) => setTimeout(r, 3000));
  }
  throw new Error(`giving up after ${retries + 1} attempts: ${lastError?.message}`);
}

// ---------------- scrape functions ----------------

export async function scrapeCollection(slug) {
  const url = `https://opensea.io/collection/${encodeURIComponent(slug)}`;
  const html = await fetchRenderedHtml(url);
  return parseCollection(html, slug, url);
}

export async function scrapeAsset(chain, contract, tokenId) {
  const url = `https://opensea.io/item/${encodeURIComponent(chain)}/${contract}/${encodeURIComponent(tokenId)}`;
  const html = await fetchRenderedHtml(url);
  return parseAsset(html, chain, contract, tokenId, url);
}

// ---------------- hydration extraction ----------------

export function extractUrqlPayloads(html) {
  // Every payload arrives in a `<script>` body of the form:
  //   (window[Symbol.for("urql_transport")] ??= []).push({...})
  // We scan for the `push(` call, then balance braces to capture the JSON.
  const out = [];
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
      try { out.push(JSON.parse(slice)); } catch (_) {}
    }
    cursor = open + 5;
  }
  return out;
}

function balancedJson(html, startIdx) {
  // Walk forward starting from `{` until braces balance to zero. Respect
  // string boundaries (single and double quotes) and escaped chars.
  let i = startIdx;
  while (i < html.length && html[i] !== "{") i += 1;
  if (i >= html.length) return null;
  let depth = 0;
  let inStr = null;
  for (; i < html.length; i += 1) {
    const ch = html[i];
    if (inStr) {
      if (ch === "\\") { i += 1; continue; }
      if (ch === inStr) inStr = null;
      continue;
    }
    if (ch === '"' || ch === "'") { inStr = ch; continue; }
    if (ch === "{") depth += 1;
    else if (ch === "}") {
      depth -= 1;
      if (depth === 0) return html.slice(startIdx, i + 1);
    }
  }
  return null;
}

function* walkValues(obj) {
  if (obj === null || typeof obj !== "object") return;
  yield obj;
  for (const v of Object.values(obj)) yield* walkValues(v);
}

function findFirst(obj, predicate) {
  for (const node of walkValues(obj)) {
    if (predicate(node)) return node;
  }
  return null;
}

function findAll(obj, predicate) {
  const out = [];
  for (const node of walkValues(obj)) {
    if (predicate(node)) out.push(node);
  }
  return out;
}

// ---------------- parsers ----------------

export function parseCollection(html, slug, url) {
  const payloads = extractUrqlPayloads(html);

  // Best-quality node carries the floor price + overview modules.
  let collectionNode = null;
  for (const p of payloads) {
    const candidate = findFirst(p, (n) => n && n.__typename === "Collection" && n.slug === slug);
    if (candidate) {
      // Pick the most fields-laden hit.
      if (!collectionNode || Object.keys(candidate).length > Object.keys(collectionNode).length) {
        collectionNode = candidate;
      }
    }
  }
  // Merge all Collection nodes that match the slug, preferring richer fields.
  const merged = {};
  for (const p of payloads) {
    for (const node of findAll(p, (n) => n && n.__typename === "Collection" && n.slug === slug)) {
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

  const chain = merged.chain?.identifier
    || merged.contracts?.[0]?.chain?.identifier
    || "";

  // All-time volume sometimes lives on `statsV2` / `volume` nested nodes.
  let volumeNative = null;
  let volumeUsd = null;
  for (const p of payloads) {
    const volNode = findFirst(p, (n) => n && n.volume && (typeof n.volume.native === "object" || typeof n.volume.unit === "number" || typeof n.volume.usd === "number"));
    if (volNode) {
      volumeNative = volNode.volume?.native?.unit ?? volNode.volume?.unit ?? volumeNative;
      volumeUsd = volNode.volume?.usd ?? volumeUsd;
      if (volumeNative !== null) break;
    }
  }

  // Total supply lives on the collection node, but it's often only emitted
  // inside a nested `rarity` payload. Pick the largest plausible value.
  let totalSupply = merged.totalSupply ?? null;
  if (totalSupply === null) {
    let best = 0;
    for (const p of payloads) {
      for (const node of walkValues(p)) {
        if (node && typeof node.totalSupply === "number" && node.totalSupply > best) {
          best = node.totalSupply;
        }
      }
    }
    if (best > 1) totalSupply = best;
  }

  const overview = merged.overview;
  const name = overview?.modules?.find?.((m) => m?.title)?.title || merged.name || slug;
  const description = overview?.modules?.find?.((m) => m?.description)?.description?.trim?.() || merged.description || "";
  const image = overview?.modules?.find?.((m) => Array.isArray(m?.media) && m.media[0]?.imageUrl)?.media?.[0]?.imageUrl
    || merged.imageUrl
    || "";

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
}

export function parseAsset(html, chain, contract, tokenId, url) {
  const payloads = extractUrqlPayloads(html);

  let item = null;
  for (const p of payloads) {
    const node = findFirst(p, (n) => n && n.__typename === "Item" && (n.tokenId === String(tokenId) || n.tokenId === tokenId));
    if (node) {
      if (!item || Object.keys(node).length > Object.keys(item).length) item = node;
    }
  }
  if (!item) {
    // Fallback: any Item node (page only ever has one).
    for (const p of payloads) {
      const node = findFirst(p, (n) => n && n.__typename === "Item");
      if (node) { item = node; break; }
    }
  }
  if (!item) {
    // Empty-shell return rather than throw; callers can decide.
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
}

function numOrNull(v) {
  if (v === null || v === undefined) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}
