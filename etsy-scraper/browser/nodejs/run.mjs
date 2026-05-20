// Run the scrape functions live and optionally write results/*.json.
//
// Usage:
//   SCRAPELESS_API_KEY=sk_... node run.mjs
//   SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true node run.mjs

import { scrapeProduct, scrapeSearch, scrapeShop } from "./etsy.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SAMPLE_SEARCH_URL =
  process.env.ETSY_SAMPLE_SEARCH_URL ?? "https://www.etsy.com/search?q=wood+laptop+stand";
const SAMPLE_PRODUCT_URLS = (
  process.env.ETSY_SAMPLE_PRODUCT_URLS ??
  "https://www.etsy.com/listing/1552627931,https://www.etsy.com/listing/529765307,https://www.etsy.com/listing/949905096"
).split(",").map((u) => u.trim()).filter(Boolean);
const SAMPLE_SHOP_URLS = (
  process.env.ETSY_SAMPLE_SHOP_URLS ??
  "https://www.etsy.com/shop/FalkelDesign,https://www.etsy.com/shop/JoshuaHouseCrafts,https://www.etsy.com/shop/Oakywood"
).split(",").map((u) => u.trim()).filter(Boolean);

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

console.error(`== search '${SAMPLE_SEARCH_URL}' ==`);
saveOrPrint("search", await scrapeSearch(SAMPLE_SEARCH_URL, 1));

console.error(`== products (${SAMPLE_PRODUCT_URLS.length}) ==`);
saveOrPrint("product", await scrapeProduct(SAMPLE_PRODUCT_URLS));

console.error(`== shops (${SAMPLE_SHOP_URLS.length}) ==`);
saveOrPrint("shop", await scrapeShop(SAMPLE_SHOP_URLS));
