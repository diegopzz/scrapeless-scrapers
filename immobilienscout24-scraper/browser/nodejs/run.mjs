// Run Immobilienscout24 scrape functions live and optionally write results/*.json.

import { scrapeProperties, scrapeSearch } from "./immobilienscout24.mjs";
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
  "https://www.immobilienscout24.de/expose/160519246",
  "https://www.immobilienscout24.de/expose/162617109",
  "https://www.immobilienscout24.de/expose/161168703",
];
const SAMPLE_SEARCH = "https://www.immobilienscout24.de/Suche/de/bayern/muenchen/wohnung-mieten";

console.error("== properties ==");
saveOrPrint("properties", await scrapeProperties(SAMPLE_PROPERTIES));

console.error("== search ==");
saveOrPrint("search", await scrapeSearch(SAMPLE_SEARCH, false, 2));
