// Run the scrape functions live and optionally write results/*.json.
//
// Usage:
//   SCRAPELESS_API_KEY=sk_... node run.mjs
//   SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true node run.mjs

import { scrapeProducts, scrapeSearch } from "./fashionphile.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SAMPLE_PRODUCT_URLS = (
  process.env.FASHIONPHILE_SAMPLE_PRODUCT_URLS ??
  [
    "https://www.fashionphile.com/p/bottega-veneta-nappa-twisted-padded-intrecciato-curve-slide-sandals-36-black-1048096",
    "https://www.fashionphile.com/p/louis-vuitton-ostrich-lizard-majestueux-tote-mm-navy-1247825",
    "https://www.fashionphile.com/p/louis-vuitton-monogram-multicolor-lodge-gm-black-1242632",
  ].join(",")
).split(",").map((u) => u.trim()).filter(Boolean);
const SAMPLE_SEARCH_URL =
  process.env.FASHIONPHILE_SAMPLE_SEARCH_URL ?? "https://www.fashionphile.com/shop/discounted/all";

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

console.error(`== search '${SAMPLE_SEARCH_URL}' ==`);
saveOrPrint("search", await scrapeSearch(SAMPLE_SEARCH_URL, 3));
