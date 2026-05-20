// Run the scrape functions live and optionally write results/*.json.

import { scrapeDestination, scrapeSearch } from "./trivago.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SAMPLE_DESTINATION_URL = process.env.TRIVAGO_SAMPLE_DESTINATION_URL
  ?? "https://www.trivago.com/en-US/odr/hotels-new-york-city-new-york-united-states-of-america?search=200-2755";

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

console.error(`== search ${SAMPLE_DESTINATION_URL} ==`);
saveOrPrint("search", await scrapeSearch(SAMPLE_DESTINATION_URL, 1));

console.error(`== destination ${SAMPLE_DESTINATION_URL} ==`);
saveOrPrint("destination", await scrapeDestination(SAMPLE_DESTINATION_URL));
