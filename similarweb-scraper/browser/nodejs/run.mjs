// Run the scrape functions live and optionally write results/*.json.

import {
  scrapeSitemaps,
  scrapeTrendings,
  scrapeWebsite,
  scrapeWebsiteCompare,
} from "./similarweb.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const RESULTS_DIR = path.resolve(HERE, "results");

const SAMPLE_DOMAINS = ["google.com", "twitter.com", "youtube.com", "instagram.com"];
const SAMPLE_COMPARE = ["google.com", "youtube.com"];
const SAMPLE_SITEMAP = "https://www.similarweb.com/sitemaps/top-websites/top-websites-001.xml.gz";
const SAMPLE_TRENDING_URLS = [
  "https://www.similarweb.com/top-websites/computers-electronics-and-technology/programming-and-developer-software/",
  "https://www.similarweb.com/top-websites/computers-electronics-and-technology/social-networks-and-online-communities/",
  "https://www.similarweb.com/top-websites/finance/investing/",
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

console.error(`== website (${SAMPLE_DOMAINS.length} domains) ==`);
saveOrPrint("website", await scrapeWebsite(SAMPLE_DOMAINS));

console.error(`== website_compare ${SAMPLE_COMPARE.join(' vs ')} ==`);
saveOrPrint("website_compare", await scrapeWebsiteCompare(...SAMPLE_COMPARE));

console.error(`== sitemaps ${SAMPLE_SITEMAP} ==`);
saveOrPrint("sitemaps", await scrapeSitemaps(SAMPLE_SITEMAP));

console.error(`== trendings (${SAMPLE_TRENDING_URLS.length} urls) ==`);
saveOrPrint("trendings", await scrapeTrendings(SAMPLE_TRENDING_URLS));
