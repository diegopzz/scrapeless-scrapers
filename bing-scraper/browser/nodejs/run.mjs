// Run the scrape functions live and optionally write results/*.json.

import { scrapeKeywords, scrapeSearch } from "./bing.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const RESULTS_DIR = path.resolve(HERE, "results");

const SAMPLE_QUERY = "web scraping emails";

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

console.error(`== search '${SAMPLE_QUERY}' ==`);
saveOrPrint("search", await scrapeSearch(SAMPLE_QUERY, 3));

console.error(`== keywords '${SAMPLE_QUERY}' ==`);
saveOrPrint("keywords", await scrapeKeywords(SAMPLE_QUERY));
