// Run the scrape functions live and optionally write results/*.json.
//
// Usage:
//   SCRAPELESS_API_KEY=sk_... node run.mjs
//   SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true node run.mjs

import { scrapeCompanies, scrapeSearch } from "./wellfound.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROLE = process.env.WELLFOUND_ROLE ?? "engineer";
// Wellfound's `/role/<role>` (no location) returns a 200-but-empty interstitial;
// `/role/l/<role>/<city>` is the supported, fully-rendered search path.
const LOCATION = process.env.WELLFOUND_LOCATION ?? "san-francisco";
const COMPANY_URLS = (process.env.WELLFOUND_COMPANY_URLS ?? "https://wellfound.com/company/openai").split(",");

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

console.error(`== search role='${ROLE}' location='${LOCATION}' ==`);
saveOrPrint("search", await scrapeSearch(ROLE, LOCATION, 1));

console.error(`== companies ${JSON.stringify(COMPANY_URLS)} ==`);
saveOrPrint("companies", await scrapeCompanies(COMPANY_URLS));
