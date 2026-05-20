// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import {
  scrapeArticles,
  scrapeCompany,
  scrapeJobSearch,
  scrapeJobs,
  scrapeProfile,
} from "./linkedin.mjs";

const PROFILE_URLS = (process.env.LINKEDIN_PROFILE_URLS ?? "https://www.linkedin.com/in/williamhgates").split(",");
const COMPANY_URLS = (process.env.LINKEDIN_COMPANY_URLS ?? "https://www.linkedin.com/company/microsoft").split(",");
const JOB_URLS = (process.env.LINKEDIN_JOB_URLS ?? "https://www.linkedin.com/jobs/view/3766857648").split(",");
const ARTICLE_URLS = (process.env.LINKEDIN_ARTICLE_URLS ?? "https://www.linkedin.com/pulse/how-i-learnt-stop-worrying-love-rejection-richard-branson").split(",");
const JOB_KEYWORD = process.env.LINKEDIN_JOB_KEYWORD ?? "Python Developer";
const JOB_LOCATION = process.env.LINKEDIN_JOB_LOCATION ?? "United States";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const ProfileSchema = z.object({
  profile: z.record(z.any()),
  posts: z.array(z.any()).optional(),
}).passthrough();

const CompanySchema = z.object({
  name: z.string(),
  url: z.string(),
}).passthrough();

const JobSearchSchema = z.object({
  data: z.array(z.any()),
  total_results: z.number().nullable().optional(),
}).passthrough();

test("profile schema", async () => {
  for (const p of await scrapeProfile(PROFILE_URLS)) ProfileSchema.parse(p);
});

test("company schema", async () => {
  for (const c of await scrapeCompany(COMPANY_URLS)) CompanySchema.parse(c);
});

test("job_search schema", async () => {
  const pages = await scrapeJobSearch(JOB_KEYWORD, JOB_LOCATION, 1);
  assert.ok(pages.length >= 1);
  for (const p of pages) JobSearchSchema.parse(p);
});

test("jobs returns objects", async () => {
  const jobs = await scrapeJobs(JOB_URLS);
  assert.equal(jobs.length, JOB_URLS.length);
  for (const j of jobs) assert.equal(typeof j, "object");
});

test("articles returns objects", async () => {
  const arts = await scrapeArticles(ARTICLE_URLS);
  assert.equal(arts.length, ARTICLE_URLS.length);
  for (const a of arts) assert.equal(typeof a, "object");
});
