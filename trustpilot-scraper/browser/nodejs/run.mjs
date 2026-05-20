// Run the Trustpilot scrape functions live and optionally write results/*.json.
//
// Usage:
//   SCRAPELESS_API_KEY=sk_... node run.mjs
//   SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true node run.mjs

import { scrapeCompany, scrapeReviews, scrapeSearch } from "./trustpilot.mjs";
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

console.error("== Trustpilot search ==");
saveOrPrint("search", await scrapeSearch("https://www.trustpilot.com/categories/electronics_technology", 3));

console.error("== Trustpilot company pages ==");
saveOrPrint(
  "companies",
  await scrapeCompany([
    "https://www.trustpilot.com/review/www.flashbay.com",
    "https://www.trustpilot.com/review/iggm.com",
    "https://www.trustpilot.com/review/www.bhphotovideo.com",
  ]),
);

console.error("== Trustpilot reviews ==");
saveOrPrint("reviews", await scrapeReviews("https://www.trustpilot.com/review/www.bhphotovideo.com", 3));
