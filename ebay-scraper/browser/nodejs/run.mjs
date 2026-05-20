// Run the scrape functions live and optionally write results/*.json.

import { scrapeProduct, scrapeSearch } from "./ebay.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const DEFAULT_SEARCH_URL = "https://www.ebay.com/sch/i.html?_nkw=iphone+12&_ipg=60";
const DEFAULT_PRODUCT_URL = "https://www.ebay.com/itm/177439887865";

const SAMPLE_SEARCH_URL = process.env.EBAY_SAMPLE_SEARCH_URL ?? DEFAULT_SEARCH_URL;
const SAMPLE_PRODUCT_URL = process.env.EBAY_SAMPLE_PRODUCT_URL ?? DEFAULT_PRODUCT_URL;

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

console.error(`== search ${SAMPLE_SEARCH_URL} ==`);
saveOrPrint("search", await scrapeSearch(SAMPLE_SEARCH_URL, 2));

console.error(`== product ${SAMPLE_PRODUCT_URL} ==`);
saveOrPrint("product", await scrapeProduct(SAMPLE_PRODUCT_URL));
