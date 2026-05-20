// Run the scrape functions live and optionally write results/*.json.
//
// Usage:
//   SCRAPELESS_API_KEY=sk_... node run.mjs
//   SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true node run.mjs

import { scrapeProperties, scrapeSearch } from "./domaincom.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

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

console.error("running Domain.com.au scrape");

const properties = await scrapeProperties([
  "https://www.domain.com.au/610-399-bourke-street-melbourne-vic-3000-2018835548",
  "https://www.domain.com.au/property-profile/308-9-degraves-street-melbourne-vic-3000",
  "https://www.domain.com.au/1518-474-flinders-street-melbourne-vic-3000-17773317",
]);
saveOrPrint("properties", properties);

const search = await scrapeSearch(
  "https://www.domain.com.au/sale/melbourne-vic-3000/",
  1,
);
saveOrPrint("search", search);
