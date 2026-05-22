// Run the scrape functions live and optionally write results/*.json.

import { scrapeJobs } from "./google_jobs.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const DEFAULT_QUERY = "software engineer jobs austin tx";
const QUERY = process.env.GOOGLE_JOBS_QUERY ?? DEFAULT_QUERY;
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

console.error(`== jobs query=${QUERY} ==`);
saveOrPrint("jobs", await scrapeJobs(QUERY));
