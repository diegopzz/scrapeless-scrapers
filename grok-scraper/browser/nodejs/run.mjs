// Run Grok scrape functions live and optionally write results/*.json.
//
// Usage:
//   SCRAPELESS_API_KEY=sk_... node run.mjs
//   SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true node run.mjs

import { scrapeShare } from "./grok.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const RESULTS_DIR = path.resolve(HERE, "results");

function saveOrPrint(name, payload, ext = "json") {
  const text = ext === "json"
    ? JSON.stringify(payload, null, 2)
    : (typeof payload === "string" ? payload : JSON.stringify(payload));
  if ((process.env.SAVE_TEST_RESULTS ?? "").toLowerCase() === "true") {
    fs.mkdirSync(RESULTS_DIR, { recursive: true });
    const out = path.join(RESULTS_DIR, `${name}.${ext}`);
    fs.writeFileSync(out, text, "utf-8");
    console.error(`wrote ${out}`);
  } else {
    console.log(text);
  }
}

// Live-verified public Grok share URL (rugby collective agreement analysis, 2025).
const SAMPLE_SHARE_URL = "https://grok.com/share/bGVnYWN5_d6991719-5568-4608-b613-609cbd3f2842";

console.error("== share ==");
saveOrPrint("share", await scrapeShare(SAMPLE_SHARE_URL));
