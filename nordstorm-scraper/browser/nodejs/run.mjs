// Run the scrape functions live and optionally write results/*.json.
//
// Usage:
//   SCRAPELESS_API_KEY=sk_... node run.mjs
//   SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true node run.mjs

import { scrapeProducts, scrapeSearch } from "./nordstorm.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

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

console.error("running Nordstrom scrape");

const products = await scrapeProducts([
  "https://www.nordstrom.com/s/nike-air-max-90-sneaker-men/6549520",
  "https://www.nordstrom.com/s/hank-kent-performance-twill-dress-shirt-regular-big/7783670",
  "https://www.nordstrom.com/s/bp-fleece-hoodie/7786657",
]);
saveOrPrint("products", products);

const search = await scrapeSearch(
  "https://www.nordstrom.com/sr?origin=keywordsearch&keyword=indigo",
  2,
);
saveOrPrint("search", search);
