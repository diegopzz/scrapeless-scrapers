// Run the scrape functions live and optionally write results/*.json.

import { scrapeHotel, scrapeSearch } from "./expedia.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SAMPLE_DESTINATION = process.env.EXPEDIA_SAMPLE_DESTINATION ?? "New York";
const SAMPLE_CHECKIN = process.env.EXPEDIA_SAMPLE_CHECKIN ?? "2026-06-15";
const SAMPLE_CHECKOUT = process.env.EXPEDIA_SAMPLE_CHECKOUT ?? "2026-06-16";

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

console.error(`== search '${SAMPLE_DESTINATION}' ${SAMPLE_CHECKIN}..${SAMPLE_CHECKOUT} ==`);
const search = await scrapeSearch(SAMPLE_DESTINATION, SAMPLE_CHECKIN, SAMPLE_CHECKOUT, 1);
saveOrPrint("search", search);

const hotelUrl = process.env.EXPEDIA_SAMPLE_HOTEL_URL || (search[0] && search[0].url) || "";
if (hotelUrl) {
  console.error(`== hotel ${hotelUrl} ==`);
  saveOrPrint("hotel", await scrapeHotel(hotelUrl));
} else {
  console.error("no hotel URL available, skipping hotel fixture");
}
