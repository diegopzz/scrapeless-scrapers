// Run the Instagram scrape functions live and optionally write results/*.json.
//
// Usage:
//   SCRAPELESS_API_KEY=sk_... node run.mjs
//   SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true node run.mjs

import { scrapePost, scrapePostComments, scrapeUser, scrapeUserPosts } from "./instagram.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SAMPLE_USERNAME = process.env.INSTAGRAM_SAMPLE_USERNAME ?? "google";
const SAMPLE_POST = process.env.INSTAGRAM_SAMPLE_POST ?? "https://www.instagram.com/p/Cs9iEotsiGY/";
const SAMPLE_MULTI = process.env.INSTAGRAM_SAMPLE_MULTI_IMAGE_POST ?? "https://www.instagram.com/p/Csthn7EO99u/";

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

console.error(`== user ${SAMPLE_USERNAME} ==`);
const user = await scrapeUser(SAMPLE_USERNAME);
saveOrPrint("user", user);

console.error(`== video-post ${SAMPLE_POST} ==`);
const postVideo = await scrapePost(SAMPLE_POST);
saveOrPrint("video-post", postVideo);

console.error(`== multi-image-post ${SAMPLE_MULTI} ==`);
const postMulti = await scrapePost(SAMPLE_MULTI);
saveOrPrint("multi-image-post", postMulti);

console.error(`== all-user-posts (${SAMPLE_USERNAME}) ==`);
const allPosts = [];
for await (const p of scrapeUserPosts(SAMPLE_USERNAME, 12, 3)) allPosts.push(p);
saveOrPrint("all-user-posts", allPosts);

console.error("== post-comments ==");
const comments = await scrapePostComments(postVideo.id, 100);
saveOrPrint("post-comments", comments);
