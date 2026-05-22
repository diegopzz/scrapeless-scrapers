// Run the scrape functions live and optionally write results/*.json.

import { scrapePlaces, scrapePlace } from "./google_maps.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const DEFAULT_SEARCH_QUERY = "coffee shops in Austin TX";
const DEFAULT_PLACE_URL =
  "https://www.google.com/maps/place/Epoch+Coffee/@30.3186037,-97.7296551,15z" +
  "/data=!4m6!3m5!1s0x8644ca6bc309e81b:0x1f1a903bbb66839!8m2!3d30.3186037!4d-97.7245402!16s%2Fg%2F1v76_180";

const SEARCH_QUERY = process.env.GOOGLE_MAPS_SEARCH_QUERY ?? DEFAULT_SEARCH_QUERY;
const PLACE_URL = process.env.GOOGLE_MAPS_PLACE_URL ?? DEFAULT_PLACE_URL;
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

console.error(`== places query=${SEARCH_QUERY} ==`);
saveOrPrint("places", await scrapePlaces(SEARCH_QUERY));

console.error(`== place ${PLACE_URL} ==`);
saveOrPrint("place", await scrapePlace(PLACE_URL));
