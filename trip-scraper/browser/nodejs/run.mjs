// Run the scrape functions live and optionally write results/*.json.

import { scrapeHotel, scrapeSearch } from "./trip.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SAMPLE_CITY = process.env.TRIP_SAMPLE_CITY_ID ?? "53"; // example: 53 (Qiongzhong)
const SAMPLE_CHECKIN = process.env.TRIP_SAMPLE_CHECKIN ?? "2026/06/15";
const SAMPLE_CHECKOUT = process.env.TRIP_SAMPLE_CHECKOUT ?? "2026/06/16";

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

console.error(`== search city=${SAMPLE_CITY} ${SAMPLE_CHECKIN}..${SAMPLE_CHECKOUT} ==`);
const search = await scrapeSearch(SAMPLE_CITY, SAMPLE_CHECKIN, SAMPLE_CHECKOUT, 1);
saveOrPrint("search", search);

const hotelId = process.env.TRIP_SAMPLE_HOTEL_ID || (search[0] && search[0].id) || "";
if (hotelId) {
  console.error(`== hotel ${hotelId} ==`);
  saveOrPrint("hotel", await scrapeHotel(hotelId, SAMPLE_CHECKIN, SAMPLE_CHECKOUT));
} else {
  console.error("no hotel id available, skipping hotel fixture");
}
