// Run Booking.com scrape functions live and optionally write results/*.json.
//
// Usage:
//   SCRAPELESS_API_KEY=sk_... node run.mjs
//   SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true node run.mjs

import { scrapeHotel, scrapeHotelReviews, scrapeSearch } from "./bookingcom.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const RESULTS_DIR = path.resolve(HERE, "results");

function saveOrPrint(name, payload) {
  const text = JSON.stringify(payload, null, 2);
  if ((process.env.SAVE_TEST_RESULTS ?? "").toLowerCase() === "true") {
    fs.mkdirSync(RESULTS_DIR, { recursive: true });
    const out = path.join(RESULTS_DIR, `${name}.json`);
    fs.writeFileSync(out, text, "utf-8");
    console.error(`wrote ${out}`);
  } else {
    console.log(text);
  }
}

const today = new Date();
const fmt = (d) => d.toISOString().slice(0, 10);
const SAMPLE_QUERY = "Malta";
const SAMPLE_CHECKIN = fmt(new Date(today.getTime() + 7 * 86400000));
const SAMPLE_CHECKOUT = fmt(new Date(today.getTime() + 14 * 86400000));
const SAMPLE_HOTEL_URL = "https://www.booking.com/hotel/gb/gardencourthotel.en-gb.html";

// Scrape hotel detail first — search-results is the most heavily defended of
// the three endpoints, so we try the easiest target before stressing the
// session.
console.error(`== hotel ${SAMPLE_HOTEL_URL} ==`);
saveOrPrint("hotel", await scrapeHotel(SAMPLE_HOTEL_URL, SAMPLE_CHECKIN, 7, { proxyCountry: "GB" }));

console.error(`== hotel_review ${SAMPLE_HOTEL_URL} ==`);
saveOrPrint("hotel_review", await scrapeHotelReviews(SAMPLE_HOTEL_URL, 3, { proxyCountry: "GB" }));

console.error(`== search '${SAMPLE_QUERY}' ${SAMPLE_CHECKIN}->${SAMPLE_CHECKOUT} ==`);
saveOrPrint("search", await scrapeSearch(SAMPLE_QUERY, SAMPLE_CHECKIN, SAMPLE_CHECKOUT, 1, 2, { proxyCountry: "MT" }));
