// Run the scrape functions live and optionally write results/*.json.
//
// Usage:
//   SCRAPELESS_API_KEY=sk_... node run.mjs
//   SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true node run.mjs

import { scrapePages, scrapeSearch } from "./yellowpages.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const QUERY = process.env.YELLOWPAGES_QUERY ?? "Plumber";
const LOCATION = process.env.YELLOWPAGES_LOCATION ?? "San Francisco, CA";
const URLS = (process.env.YELLOWPAGES_URLS
  ?? "https://www.yellowpages.com/san-francisco-ca/mip/atlas-plumbing-561373897").split(",");

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

console.error(`== search query='${QUERY}' location='${LOCATION}' ==`);
saveOrPrint("search", await scrapeSearch(QUERY, LOCATION, 1));

console.error(`== pages ${JSON.stringify(URLS)} ==`);
saveOrPrint("pages", await scrapePages(URLS));
