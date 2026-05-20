// Run YouTube scrape functions live and optionally write results/*.json.
//
// Usage:
//   SCRAPELESS_API_KEY=sk_... node run.mjs
//   SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true node run.mjs

import {
  scrapeChannel,
  scrapeChannelVideos,
  scrapeComments,
  scrapeSearch,
  scrapeShorts,
  scrapeVideo,
} from "./youtube.mjs";
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

const SAMPLE_VIDEO_IDS = ["1Y-XvvWlyzk", "muo6I9XY8K4", "y7FbFJ4jOW8"];
const SAMPLE_COMMENTS_VIDEO = "FgakZw6K1QQ";
const SAMPLE_CHANNEL_HANDLE = "the upstream reference";
const SAMPLE_CHANNEL_VIDEOS = "statquest";
const SAMPLE_SEARCH_QUERY = "python";
const SAMPLE_SEARCH_PARAMS = "EgQIAxAB"; // video-only filter
const SAMPLE_SHORT_IDS = ["rZ2qqtNPSBk"];

console.error("== video ==");
saveOrPrint("video", await scrapeVideo(SAMPLE_VIDEO_IDS));

console.error("== comments ==");
saveOrPrint("comments", await scrapeComments(SAMPLE_COMMENTS_VIDEO, 3));

console.error("== channel ==");
saveOrPrint("channel", await scrapeChannel([SAMPLE_CHANNEL_HANDLE]));

console.error("== channel_videos ==");
saveOrPrint("channel_videos", await scrapeChannelVideos(SAMPLE_CHANNEL_VIDEOS, "Latest", 2));

console.error("== search ==");
saveOrPrint("search", await scrapeSearch(SAMPLE_SEARCH_QUERY, 2, SAMPLE_SEARCH_PARAMS));

console.error("== shorts ==");
saveOrPrint("shorts", await scrapeShorts(SAMPLE_SHORT_IDS));
