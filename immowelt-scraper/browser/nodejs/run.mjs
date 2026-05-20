// Run Immowelt scrape functions live and optionally write results/*.json.

import { scrapeProperties, scrapeSearch } from "./immowelt.mjs";
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

const SAMPLE_SEARCH = "https://www.immowelt.de/classified-search?distributionTypes=Buy&estateTypes=Apartment&locations=AD08DE6345";
const SAMPLE_PROPERTIES = [
  "https://www.immowelt.de/expose/k2ag632",
  "https://www.immowelt.de/expose/k2bw932",
];

console.error("== search ==");
saveOrPrint("search", await scrapeSearch(SAMPLE_SEARCH, 3));

console.error("== properties ==");
saveOrPrint("properties", await scrapeProperties(SAMPLE_PROPERTIES));
