// Run the scrape functions live and optionally write results/*.json.

import { scrapeHotel, scrapeSearch } from "./priceline.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

// Sample IDs picked to be stable real properties with full SSR data:
//   3000020228 — Aberdeen, SD (small mid-size city with consistent listings)
//   97649603   — Fairfield Inn & Suites by Marriott Aberdeen
const SAMPLE_CITY = process.env.PRICELINE_SAMPLE_CITY_ID ?? "3000020228";
const SAMPLE_CHECKIN = process.env.PRICELINE_SAMPLE_CHECKIN ?? "2026-06-15";
const SAMPLE_CHECKOUT = process.env.PRICELINE_SAMPLE_CHECKOUT ?? "2026-06-16";
const SAMPLE_HOTEL = process.env.PRICELINE_SAMPLE_HOTEL_ID ?? "97649603";

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

console.error(`== hotel ${SAMPLE_HOTEL} ==`);
saveOrPrint("hotel", await scrapeHotel(SAMPLE_HOTEL, SAMPLE_CHECKIN, SAMPLE_CHECKOUT));

console.error(`== search city=${SAMPLE_CITY} ==`);
saveOrPrint("search", await scrapeSearch(SAMPLE_CITY, SAMPLE_CHECKIN, SAMPLE_CHECKOUT));
