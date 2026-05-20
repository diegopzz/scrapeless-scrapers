// Run the scrape functions live and optionally write results/*.json.
//
// Usage:
//   SCRAPELESS_API_KEY=sk_... node run.mjs
//   SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true node run.mjs

import { scrapeProducts, scrapeSearch } from "./goat.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SAMPLE_PRODUCT_URLS = (
  process.env.GOAT_SAMPLE_PRODUCT_URLS ??
  [
    "https://www.goat.com/sneakers/air-jordan-3-retro-white-cement-reimagined-dn3707-100",
    "https://www.goat.com/sneakers/travis-scott-x-air-jordan-1-retro-high-og-cd4487-100",
    "https://www.goat.com/sneakers/travis-scott-x-wmns-air-jordan-1-low-og-olive-dz4137-106",
  ].join(",")
).split(",").map((u) => u.trim()).filter(Boolean);
const SAMPLE_QUERY = process.env.GOAT_SAMPLE_QUERY ?? "pumar dark";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const RESULTS_DIR = path.resolve(HERE, "results");

function saveOrPrint(name, payload) {
  const json = JSON.stringify(payload, null, 2);
  if ((process.env.SAVE_TEST_RESULTS ?? "").toLowerCase() === "true") {
    fs.mkdirSync(RESULTS_DIR, { recursive: true });
    const out = path.join(RESULTS_DIR, `${name}.json`);
    fs.writeFileSync(out, json, "utf-8");
    console.error(`wrote ${out}`);
  } else {
    console.log(json);
  }
}

console.error(`== products (${SAMPLE_PRODUCT_URLS.length}) ==`);
saveOrPrint("products", await scrapeProducts(SAMPLE_PRODUCT_URLS));

console.error(`== search '${SAMPLE_QUERY}' ==`);
saveOrPrint("search", await scrapeSearch(SAMPLE_QUERY, 3));
