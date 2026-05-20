// Run the Reddit scrape functions live and optionally write results/*.json.
//
// Usage:
//   SCRAPELESS_API_KEY=sk_... node run.mjs
//   SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true node run.mjs

import { scrapePost, scrapeSubreddit, scrapeUserComments, scrapeUserPosts } from "./reddit.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SAMPLE_SUBREDDIT = process.env.REDDIT_SAMPLE_SUBREDDIT ?? "wallstreetbets";
const SAMPLE_POST_URL = process.env.REDDIT_SAMPLE_POST_URL ?? "https://www.reddit.com/r/wallstreetbets/comments/1c4vwlp/what_are_your_moves_tomorrow_april_16_2024/";
const SAMPLE_USERNAME = process.env.REDDIT_SAMPLE_USERNAME ?? "spez";

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

console.error(`== subreddit r/${SAMPLE_SUBREDDIT} ==`);
saveOrPrint("subreddit", await scrapeSubreddit(SAMPLE_SUBREDDIT, 3));

console.error(`== post ${SAMPLE_POST_URL} ==`);
saveOrPrint("post", await scrapePost(SAMPLE_POST_URL, "top"));

console.error(`== user_posts ${SAMPLE_USERNAME} ==`);
saveOrPrint("user_posts", await scrapeUserPosts(SAMPLE_USERNAME, "new", 3));

console.error(`== user_comments ${SAMPLE_USERNAME} ==`);
saveOrPrint("user_comments", await scrapeUserComments(SAMPLE_USERNAME, "new", 3));
