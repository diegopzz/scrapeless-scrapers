// Run the scrape functions live and optionally write results/*.json.

import { scrapeProduct, scrapeSearch } from "./adidas.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const DEFAULT_PRODUCT_URLS = [
  "https://www.adidas.com/us/samba-og-shoes/B75806.html",
  "https://www.adidas.com/us/gazelle-shoes/BB5476.html",
];
const DEFAULT_SEARCH_URL = "https://www.adidas.com/us/men-shoes";

const SAMPLE_PRODUCT_URLS = process.env.ADIDAS_SAMPLE_PRODUCT_URLS
  ? process.env.ADIDAS_SAMPLE_PRODUCT_URLS.split(",").map((s) => s.trim())
  : DEFAULT_PRODUCT_URLS;
const SAMPLE_SEARCH_URL = process.env.ADIDAS_SAMPLE_SEARCH_URL ?? DEFAULT_SEARCH_URL;

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

console.error(`== product ${SAMPLE_PRODUCT_URLS.join(", ")} ==`);
saveOrPrint("product", await scrapeProduct(SAMPLE_PRODUCT_URLS));

console.error(`== search ${SAMPLE_SEARCH_URL} ==`);
saveOrPrint("search", await scrapeSearch(SAMPLE_SEARCH_URL, 1));
