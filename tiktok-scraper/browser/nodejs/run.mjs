// Run the TikTok scrape functions live and optionally write results/*.json.
//
// Usage:
//   SCRAPELESS_API_KEY=sk_... node run.mjs
//   SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true node run.mjs

import {
  scrapeChannel,
  scrapeComments,
  scrapePosts,
  scrapeProfiles,
  scrapeSearch,
} from "./tiktok.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SAMPLE_POST = process.env.TIKTOK_SAMPLE_POST ?? "https://www.tiktok.com/@oddanimalspecimens/video/7198206283571285294";
const SAMPLE_PROFILE = process.env.TIKTOK_SAMPLE_PROFILE ?? "https://www.tiktok.com/@oddanimalspecimens";
const SAMPLE_QUERY = process.env.TIKTOK_SAMPLE_QUERY ?? "whales";

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

console.error("== posts ==");
saveOrPrint("posts", await scrapePosts([SAMPLE_POST]));

console.error("== comments ==");
saveOrPrint("comments", await scrapeComments(SAMPLE_POST));

console.error("== profiles ==");
saveOrPrint("profiles", await scrapeProfiles([SAMPLE_PROFILE]));

console.error(`== search '${SAMPLE_QUERY}' ==`);
saveOrPrint("search", await scrapeSearch(SAMPLE_QUERY));

console.error(`== channel ${SAMPLE_PROFILE} ==`);
saveOrPrint("channel", await scrapeChannel(SAMPLE_PROFILE));
