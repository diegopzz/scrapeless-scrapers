// Run the scrape functions live and optionally write results/*.json.

import { scrapeProperties, scrapeSearch } from "./zoopla.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const DEFAULT_PROPERTY_URLS = [
  "https://www.zoopla.co.uk/new-homes/details/70337559/",
  "https://www.zoopla.co.uk/new-homes/details/71411815/",
  "https://www.zoopla.co.uk/new-homes/details/71669525/",
];
const DEFAULT_LOCATION_SLUG = "london/islington";
const DEFAULT_QUERY_TYPE = "to-rent";

const PROPERTY_URLS = process.env.ZOOPLA_PROPERTY_URLS?.split(",") ?? DEFAULT_PROPERTY_URLS;
const LOCATION_SLUG = process.env.ZOOPLA_LOCATION_SLUG ?? DEFAULT_LOCATION_SLUG;
const QUERY_TYPE = process.env.ZOOPLA_QUERY_TYPE ?? DEFAULT_QUERY_TYPE;

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

console.error(`== search ${QUERY_TYPE}/${LOCATION_SLUG} ==`);
saveOrPrint("search", await scrapeSearch(false, LOCATION_SLUG, 2, QUERY_TYPE));
