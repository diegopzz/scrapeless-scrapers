// Run the scrape functions live and optionally write results/*.json.
//
// Usage:
//   SCRAPELESS_API_KEY=sk_... node run.mjs
//   SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true node run.mjs

import { scrapeJobs, scrapeSearch } from "./indeed.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SAMPLE_URL = process.env.INDEED_SAMPLE_URL ?? "https://www.indeed.com/jobs?q=python&l=Texas";
const SAMPLE_JOB_KEYS = (process.env.INDEED_SAMPLE_JOB_KEYS ?? "")
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean);
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

console.error(`== search '${SAMPLE_URL}' ==`);
const searchResults = await scrapeSearch(SAMPLE_URL, 10);
saveOrPrint("search", searchResults);

// Indeed job keys (`jk`) are ephemeral, so when the user hasn't pinned a
// specific one we sample up to two from the live search above.
let jobKeys = SAMPLE_JOB_KEYS;
if (!jobKeys.length) {
  jobKeys = searchResults
    .map((r) => r?.jobkey)
    .filter((k) => typeof k === "string" && k.length > 0)
    .slice(0, 2);
}
console.error(`== jobs ${JSON.stringify(jobKeys)} ==`);
saveOrPrint("jobs", jobKeys.length ? await scrapeJobs(jobKeys) : []);
