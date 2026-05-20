// Run the Yelp scrape functions live and optionally write results/*.json.
//
// Usage:
//   SCRAPELESS_API_KEY=sk_... node run.mjs
//   SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true node run.mjs

import { scrapePages, scrapeReviews, scrapeSearch } from "./yelp.mjs";
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

console.error("== Yelp business pages ==");
saveOrPrint("business_pages", await scrapePages([
  "https://www.yelp.com/biz/vons-1000-spirits-seattle-4",
  "https://www.yelp.com/biz/ihop-seattle-4",
  "https://www.yelp.com/biz/toulouse-petit-kitchen-and-lounge-seattle",
]));

console.error("== Yelp reviews ==");
saveOrPrint("reviews", await scrapeReviews("https://www.yelp.com/biz/vons-1000-spirits-seattle-4", 28));

console.error("== Yelp search ==");
try {
  saveOrPrint("search", await scrapeSearch("plumbers", "Seattle, WA", 2));
} catch (e) {
  // Yelp's /search surface trips DataDome more aggressively than business
  // pages; emit an empty list rather than poisoning subsequent fixtures.
  console.error(`yelp search blocked: ${e.message}`);
  saveOrPrint("search", []);
}
