// Run the Glassdoor scrape functions live and optionally write results/*.json.
//
// Usage:
//   SCRAPELESS_API_KEY=sk_... node run.mjs
//   SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true node run.mjs

import {
  Region,
  Url,
  findCompanies,
  scrapeJobs,
  scrapeReviews,
  scrapeSalaries,
} from "./glassdoor.mjs";
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

const EMPLOYER = "eBay";
const EMPLOYER_ID = "7853";

console.error("== Glassdoor jobs ==");
saveOrPrint("jobs", await scrapeJobs(Url.jobs(EMPLOYER, EMPLOYER_ID, Region.UNITED_STATES), 3));

console.error("== Glassdoor salaries ==");
saveOrPrint("salaries", await scrapeSalaries(Url.salaries(EMPLOYER, EMPLOYER_ID), 3));

console.error("== Glassdoor reviews ==");
saveOrPrint("reviews", await scrapeReviews(Url.reviews(EMPLOYER, EMPLOYER_ID), 3));

console.error("== Glassdoor company autocomplete ==");
saveOrPrint("companies", await findCompanies(EMPLOYER));
