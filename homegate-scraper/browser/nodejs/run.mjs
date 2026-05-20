// Run Homegate scrape functions live and optionally write results/*.json.

import { scrapeProperties, scrapeSearch } from "./homegate.mjs";
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

const SAMPLE_PROPERTIES = [
  "https://www.homegate.ch/rent/4002086534",
  "https://www.homegate.ch/rent/4002879785",
  "https://www.homegate.ch/rent/4002086532",
];
const SAMPLE_SEARCH = "https://www.homegate.ch/rent/real-estate/city-bern/matching-list";

console.error("== search ==");
try {
  saveOrPrint("search", await scrapeSearch(SAMPLE_SEARCH, false, 2));
} catch (e) {
  console.error("search failed:", e.message);
}

console.error("== properties ==");
try {
  saveOrPrint("properties", await scrapeProperties(SAMPLE_PROPERTIES));
} catch (e) {
  console.error("properties failed (sample listings may have expired):", e.message);
}
