// Run the scrape functions live and optionally write results/*.json.

import { scrapeFeed, scrapeProperty, scrapeSearch } from "./realtorcom.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const DEFAULT_PROPERTY_URL =
  "https://www.realtor.com/realestateandhomes-detail/12355-Attlee-Dr_Houston_TX_77077_M70330-35605";
const DEFAULT_STATE = "CA";
const DEFAULT_CITY = "San-Francisco";
const DEFAULT_FEED_URL = "https://cdn.realtor.ca/sitemap/realtorsitemap/sitemap.xml";

const PROPERTY_URL = process.env.REALTORCOM_PROPERTY_URL ?? DEFAULT_PROPERTY_URL;
const STATE = process.env.REALTORCOM_STATE ?? DEFAULT_STATE;
const CITY = process.env.REALTORCOM_CITY ?? DEFAULT_CITY;
const FEED_URL = process.env.REALTORCOM_FEED_URL ?? DEFAULT_FEED_URL;

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

console.error(`== feed ${FEED_URL} ==`);
try { saveOrPrint("feed", await scrapeFeed(FEED_URL)); }
catch (e) { console.error("feed failed:", e.message); }

console.error(`== search ${CITY},${STATE} ==`);
try { saveOrPrint("search", await scrapeSearch(STATE, CITY, 2)); }
catch (e) { console.error("search failed:", e.message); }

console.error(`== property ${PROPERTY_URL} ==`);
try { saveOrPrint("property", await scrapeProperty(PROPERTY_URL)); }
catch (e) { console.error("property failed:", e.message); }
