// Run the scrape functions live and optionally write results/*.json.
//
// Usage:
//   SCRAPELESS_API_KEY=sk_... node run.mjs
//   SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true node run.mjs

import { scrapeProperties, scrapeSearch } from "./realestatecom.mjs";
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

console.error("running Realestate.com.au scrape");

const properties = await scrapeProperties([
  "https://www.realestate.com.au/property-house-vic-tarneit-143160680",
  "https://www.realestate.com.au/property-house-vic-bundoora-141557712",
  "https://www.realestate.com.au/property-townhouse-vic-glenroy-143556608",
]);
saveOrPrint("properties", properties);

const search = await scrapeSearch(
  "https://www.realestate.com.au/buy/in-melbourne+-+northern+region,+vic/list-1",
  3,
);
saveOrPrint("search", search);
