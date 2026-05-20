// Run the scrape functions live and optionally write results/*.json.
//
// Usage:
//   SCRAPELESS_API_KEY=sk_... node run.mjs
//   SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true node run.mjs

import {
  scrapeArticles,
  scrapeCompany,
  scrapeJobSearch,
  scrapeJobs,
  scrapeProfile,
} from "./linkedin.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const PROFILE_URLS = (process.env.LINKEDIN_PROFILE_URLS ?? "https://www.linkedin.com/in/williamhgates").split(",");
const COMPANY_URLS = (process.env.LINKEDIN_COMPANY_URLS ?? "https://www.linkedin.com/company/microsoft").split(",");
const JOB_URLS = (process.env.LINKEDIN_JOB_URLS ?? "").split(",").filter(Boolean);
const ARTICLE_URLS = (process.env.LINKEDIN_ARTICLE_URLS ?? "https://www.linkedin.com/pulse/how-i-learnt-stop-worrying-love-rejection-richard-branson").split(",");
const JOB_KEYWORD = process.env.LINKEDIN_JOB_KEYWORD ?? "Python Developer";
const JOB_LOCATION = process.env.LINKEDIN_JOB_LOCATION ?? "United States";

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

console.error("== profile ==");
saveOrPrint("profile", await scrapeProfile(PROFILE_URLS));
console.error("== company ==");
saveOrPrint("company", await scrapeCompany(COMPANY_URLS));
console.error("== job_search ==");
const jobSearchPages = await scrapeJobSearch(JOB_KEYWORD, JOB_LOCATION, 1);
saveOrPrint("job_search", jobSearchPages);
console.error("== jobs ==");
// Default to picking up to 2 job URLs from the search above when the user
// hasn't supplied LINKEDIN_JOB_URLS — LinkedIn job ids are ephemeral, so
// hard-coding one in the fixture would 404 days later.
let jobUrls = JOB_URLS;
if (!jobUrls.length) {
  const fromSearch = (jobSearchPages?.[0]?.data ?? [])
    .map((j) => j.jobUrl)
    .filter((u) => typeof u === "string" && u.includes("/jobs/view/"))
    .slice(0, 2);
  jobUrls = fromSearch;
}
saveOrPrint("jobs", jobUrls.length ? await scrapeJobs(jobUrls) : []);
console.error("== articles ==");
saveOrPrint("articles", await scrapeArticles(ARTICLE_URLS));
