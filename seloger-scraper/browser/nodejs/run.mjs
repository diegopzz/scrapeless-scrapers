// Run SeLoger scrape functions live and optionally write results/*.json.

import { scrapeProperty, scrapeSearch } from "./seloger.mjs";
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

const SAMPLE_SEARCH = "https://www.seloger.com/classified-search?distributionTypes=Buy&estateTypes=Apartment&locations=AD08FR13100";
const SAMPLE_PROPERTIES = [
  "https://www.seloger.com/annonces/achat/appartement/bordeaux-33/193612259.htm",
  "https://www.seloger.com/annonces/achat/appartement/bordeaux-33/255197845.htm",
];

console.error("== search ==");
saveOrPrint("search", await scrapeSearch(SAMPLE_SEARCH, 2));

console.error("== property ==");
saveOrPrint("property", await scrapeProperty(SAMPLE_PROPERTIES));
