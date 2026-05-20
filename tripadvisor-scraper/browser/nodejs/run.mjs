// Run the TripAdvisor scrape functions live and optionally write results/*.json.
//
// Usage:
//   SCRAPELESS_API_KEY=sk_... node run.mjs
//   SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true node run.mjs

import { scrapeHotel, scrapeLocationData, scrapeSearch } from "./tripadvisor.mjs";
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

console.error("== TripAdvisor location autocomplete ==");
saveOrPrint("location", await scrapeLocationData("Malta"));

console.error("== TripAdvisor search ==");
saveOrPrint(
  "search",
  await scrapeSearch(
    "https://www.tripadvisor.com/Hotels-g60763-oa30-New_York_City_New_York-Hotels.html",
    2,
  ),
);

console.error("== TripAdvisor hotel ==");
saveOrPrint(
  "hotels",
  await scrapeHotel(
    "https://www.tripadvisor.com/Hotel_Review-g190327-d264936-Reviews-1926_Hotel_Spa-Sliema_Island_of_Malta.html",
    3,
  ),
);
