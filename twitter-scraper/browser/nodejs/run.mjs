// Run the Twitter scrape functions live and optionally write results/*.json.
//
// Usage:
//   SCRAPELESS_API_KEY=sk_... node run.mjs
//   SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true node run.mjs

import { scrapeProfile, scrapeTweet } from "./twitter.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SAMPLE_TWEET = process.env.TWITTER_SAMPLE_TWEET ?? "https://x.com/robinhanson/status/1872047986873885082";
const SAMPLE_PROFILE = process.env.TWITTER_SAMPLE_PROFILE ?? "https://x.com/robinhanson/";
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

console.error(`== tweet ${SAMPLE_TWEET} ==`);
saveOrPrint("tweet", await scrapeTweet(SAMPLE_TWEET));

console.error(`== profile ${SAMPLE_PROFILE} ==`);
saveOrPrint("profile", await scrapeProfile(SAMPLE_PROFILE));
