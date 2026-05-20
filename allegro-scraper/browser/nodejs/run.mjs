// Run the scrape functions live and optionally write results/*.json.
//
// Usage:
//   SCRAPELESS_API_KEY=sk_... node run.mjs
//   SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true node run.mjs

import { scrapeProduct, scrapeSearch } from "./allegro.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const QUERY = process.env.ALLEGRO_QUERY ?? "iphone";
const PRODUCT_URLS = (process.env.ALLEGRO_PRODUCT_URLS
  ?? "https://allegro.pl/produkt/telefon-apple-iphone-17-8-256gb-5g-czarny-ffd22d9a-7e19-4bc3-98ce-d968b0669f01").split(",");

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

console.error(`== search query='${QUERY}' ==`);
saveOrPrint("search", await scrapeSearch(QUERY, 1));

console.error(`== product ${JSON.stringify(PRODUCT_URLS)} ==`);
saveOrPrint("product", await scrapeProduct(PRODUCT_URLS));
