// Run the scrape functions live and optionally write results/*.json.
//
// Usage:
//   SCRAPELESS_API_KEY=sk_... node run.mjs
//   SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true node run.mjs

import { scrapeProperties, scrapeSearch } from "./zillow.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const DEFAULT_SEARCH_URL =
  "https://www.zillow.com/san-francisco-ca/?searchQueryState=%7B%22usersSearchTerm%22%3A%22Nebraska%22" +
  "%2C%22mapBounds%22%3A%7B%22north%22%3A37.890669225201904%2C%22east%22%3A-122.26750460986328" +
  "%2C%22south%22%3A37.659734343010626%2C%22west%22%3A-122.59915439013672%7D" +
  "%2C%22isMapVisible%22%3Atrue%2C%22filterState%22%3A%7B%22sort%22%3A%7B%22value%22%3A%22days%22%7D" +
  "%2C%22ah%22%3A%7B%22value%22%3Atrue%7D%7D%2C%22isListVisible%22%3Atrue%2C%22mapZoom%22%3A12" +
  "%2C%22regionSelection%22%3A%5B%7B%22regionId%22%3A20330%2C%22regionType%22%3A6%7D%5D" +
  "%2C%22pagination%22%3A%7B%7D%7D";
const DEFAULT_PROPERTY_URL =
  "https://www.zillow.com/homedetails/661-Lakeview-Ave-San-Francisco-CA-94112/15192198_zpid/";

const SEARCH_URL = process.env.ZILLOW_SEARCH_URL ?? DEFAULT_SEARCH_URL;
const PROPERTY_URL = process.env.ZILLOW_PROPERTY_URL ?? DEFAULT_PROPERTY_URL;

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

console.error(`== search ${SEARCH_URL.slice(0, 80)}... ==`);
saveOrPrint("search", await scrapeSearch(SEARCH_URL, 1));

console.error(`== property ${PROPERTY_URL} ==`);
saveOrPrint("property", await scrapeProperties([PROPERTY_URL]));
