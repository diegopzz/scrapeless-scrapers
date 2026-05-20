// Run the scrape functions live and optionally write results/*.json.

import { findLocations, scrapeProperties, scrapeSearch } from "./rightmove.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const DEFAULT_PROPERTY_URLS = [
  "https://www.rightmove.co.uk/properties/149360984#/",
  "https://www.rightmove.co.uk/properties/136408088#/",
  "https://www.rightmove.co.uk/properties/148922639#/",
];
const DEFAULT_LOCATION_QUERY = "cornwall";
const DEFAULT_LOCATION_NAME = "Cornwall";

const PROPERTY_URLS = process.env.RIGHTMOVE_PROPERTY_URLS?.split(",") ?? DEFAULT_PROPERTY_URLS;
const LOCATION_QUERY = process.env.RIGHTMOVE_LOCATION_QUERY ?? DEFAULT_LOCATION_QUERY;
const LOCATION_NAME = process.env.RIGHTMOVE_LOCATION_NAME ?? DEFAULT_LOCATION_NAME;

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

console.error("== properties ==");
saveOrPrint("properties", await scrapeProperties(PROPERTY_URLS));

console.error(`== find_locations '${LOCATION_QUERY}' ==`);
const locations = await findLocations(LOCATION_QUERY);
saveOrPrint("locations", locations);

if (locations.length) {
  console.error(`== search ${LOCATION_NAME} (${locations[0]}) ==`);
  saveOrPrint("search", await scrapeSearch(LOCATION_NAME, locations[0], false, 50));
}
