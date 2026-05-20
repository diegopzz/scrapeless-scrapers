// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import {
  Region,
  Url,
  findCompanies,
  scrapeJobs,
  scrapeReviews,
  scrapeSalaries,
} from "./glassdoor.mjs";

const SAMPLE_EMPLOYER = process.env.GLASSDOOR_SAMPLE_EMPLOYER ?? "eBay";
const SAMPLE_EMPLOYER_ID = process.env.GLASSDOOR_SAMPLE_EMPLOYER_ID ?? "7853";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const JobSchema = z.object({
  jobTitle: z.string().nullable(),
  jobLink: z.string().nullable(),
  job_location: z.string().nullable(),
  jobSalary: z.string().nullable(),
  jobDate: z.string().nullable(),
}).passthrough();

const ReviewSchema = z.object({
  reviewId: z.number(),
  ratingOverall: z.number().int().min(1).max(5),
  reviewDateTime: z.string(),
}).passthrough();

const SalaryItemSchema = z.object({
  jobTitle: z.object({ text: z.string() }).passthrough(),
  salaryCount: z.number().int(),
  basePayStatistics: z.object({ percentiles: z.array(z.any()) }).passthrough(),
}).passthrough();

const SalarySchema = z.object({
  results: z.array(SalaryItemSchema),
  numPages: z.number().int(),
  salaryCount: z.number().int(),
  jobTitleCount: z.number().int(),
}).passthrough();

const CompanySchema = z.object({
  name: z.string().min(1),
  id: z.number().int(),
  shortName: z.string(),
  logoURL: z.string().nullable(),
  websiteURL: z.string(),
}).passthrough();

test("jobs schema", async () => {
  const url = Url.jobs(SAMPLE_EMPLOYER, SAMPLE_EMPLOYER_ID, Region.UNITED_STATES);
  const jobs = await scrapeJobs(url, 1);
  assert.ok(jobs.length >= 1, `expected >=1 jobs, got ${jobs.length}`);
  for (const j of jobs) JobSchema.parse(j);
});

test("reviews schema", async () => {
  const url = Url.reviews(SAMPLE_EMPLOYER, SAMPLE_EMPLOYER_ID);
  const reviews = await scrapeReviews(url, 1);
  assert.ok(reviews.length >= 1, `expected >=1 reviews, got ${reviews.length}`);
  for (const r of reviews) ReviewSchema.parse(r);
});

test("salaries schema", async () => {
  const url = Url.salaries(SAMPLE_EMPLOYER, SAMPLE_EMPLOYER_ID);
  const salaries = await scrapeSalaries(url, 1);
  SalarySchema.parse(salaries);
});

test("findCompanies schema", async () => {
  const companies = await findCompanies(SAMPLE_EMPLOYER);
  assert.ok(companies.length >= 1, `expected >=1 companies, got ${companies.length}`);
  for (const c of companies) CompanySchema.parse(c);
});
