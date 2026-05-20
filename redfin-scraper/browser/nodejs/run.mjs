// Run the scrape functions live and optionally write results/*.json.

import {
  scrapePropertyForRent,
  scrapePropertyForSale,
  scrapeSearch,
} from "./redfin.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const DEFAULT_SEARCH_URL =
  "https://www.redfin.com/stingray/api/gis?al=1&include_nearby_homes=true" +
  "&market=seattle&num_homes=350&ord=redfin-recommended-asc&page_number=1" +
  "&poly=-122.54472%2047.44109%2C-122.11144%2047.44109%2C-122.11144%2047.78363" +
  "%2C-122.54472%2047.78363%2C-122.54472%2047.44109&sf=1,2,3,5,6,7&start=0" +
  "&status=1&uipt=1,2,3,4,5,6,7,8&v=8&zoomLevel=11";
const DEFAULT_SALE_URLS = [
  "https://www.redfin.com/WA/Seattle/506-E-Howell-St-98122/unit-W303/home/46456",
  "https://www.redfin.com/WA/Seattle/1105-Spring-St-98104/unit-405/home/12305595",
  "https://www.redfin.com/WA/Seattle/10116-Myers-Way-S-98168/home/186647",
];
const DEFAULT_RENT_URLS = [
  "https://www.redfin.com/WA/Seattle/Onni-South-Lake-Union/apartment/147020546",
  "https://www.redfin.com/WA/Seattle/The-Ivey-on-Boren/apartment/146904423",
  "https://www.redfin.com/WA/Seattle/Broadstone-Strata/apartment/178439949",
];

const SEARCH_URL = process.env.REDFIN_SEARCH_URL ?? DEFAULT_SEARCH_URL;
const SALE_URLS = process.env.REDFIN_SALE_URLS?.split(",") ?? DEFAULT_SALE_URLS;
const RENT_URLS = process.env.REDFIN_RENT_URLS?.split(",") ?? DEFAULT_RENT_URLS;

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

console.error("== search ==");
saveOrPrint("search", await scrapeSearch(SEARCH_URL));

console.error("== property_for_sale ==");
saveOrPrint("property_for_sale", await scrapePropertyForSale(SALE_URLS));

console.error("== property_for_rent ==");
saveOrPrint("property_for_rent", await scrapePropertyForRent(RENT_URLS));
