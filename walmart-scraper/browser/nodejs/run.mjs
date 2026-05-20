// Run the scrape functions live and optionally write results/*.json.

import { scrapeProducts, scrapeSearch } from "./walmart.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const DEFAULT_PRODUCT_URLS = [
  "https://www.walmart.com/ip/1736740710",
  "https://www.walmart.com/ip/715596133",
];

const SAMPLE_PRODUCT_URLS = process.env.WALMART_SAMPLE_PRODUCT_URLS
  ? process.env.WALMART_SAMPLE_PRODUCT_URLS.split(",").map((s) => s.trim()).filter(Boolean)
  : DEFAULT_PRODUCT_URLS;
const SAMPLE_QUERY = process.env.WALMART_SAMPLE_QUERY ?? "laptop";

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

console.error(`== products ${SAMPLE_PRODUCT_URLS.join(", ")} ==`);
saveOrPrint("products", await scrapeProducts(SAMPLE_PRODUCT_URLS));

console.error(`== search ${SAMPLE_QUERY} ==`);
saveOrPrint("search", await scrapeSearch(SAMPLE_QUERY, "best_seller", 3));
