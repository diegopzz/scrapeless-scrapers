// Run the scrape functions live and optionally write results/*.json.
//
// Usage:
//   SCRAPELESS_API_KEY=sk_... node run.mjs
//   SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true node run.mjs

import { scrapeGoogleMapPlaces, scrapeKeywords, scrapeSerp } from "./google.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const RESULTS_DIR = path.resolve(HERE, "results");

const SAMPLE_QUERY_SERP = "the upstream reference blog web scraping";
const SAMPLE_QUERY_KEYWORDS = "web scraping emails";
const SAMPLE_PLACES = [
  "https://www.google.com/maps/place/Mus%C3%A9e+d%27Orsay/data=!4m7!3m6!1s0x47e66e2bb630941b:0xd071bd8cb14423d8!8m2!3d48.8599614!4d2.3265614!16zL20vMGYzYjk!19sChIJG5Qwtitu5kcR2CNEsYy9cdA",
  "https://www.google.com/maps/place/The+Centre+Pompidou/data=!4m7!3m6!1s0x47e66e1c09b820a3:0xb7ac6c7e59dc3345!8m2!3d48.860642!4d2.352245!16zL20vMGYzMnA!19sChIJoyC4CRxu5kcRRTPcWX5srLc",
];

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

console.error(`== serp '${SAMPLE_QUERY_SERP}' ==`);
saveOrPrint("serp", await scrapeSerp(SAMPLE_QUERY_SERP, 3));

console.error(`== keywords '${SAMPLE_QUERY_KEYWORDS}' ==`);
saveOrPrint("keywords", await scrapeKeywords(SAMPLE_QUERY_KEYWORDS));

console.error(`== google_map_places (${SAMPLE_PLACES.length} urls) ==`);
saveOrPrint("google_map_places", await scrapeGoogleMapPlaces(SAMPLE_PLACES));
