// Run the scrape functions live and optionally write results/*.json.
//
// Usage:
//   SCRAPELESS_API_KEY=sk_... node run.mjs
//   SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true node run.mjs

import { scrapeProduct, scrapeSearch } from "./1688.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SAMPLE_ID = process.env.SCRAPELESS_1688_SAMPLE_ID ?? "611499776800";
// Chinese phrase for "phone case" — 1688 favours zh-CN queries on its search box.
const SAMPLE_QUERY = process.env.SCRAPELESS_1688_SAMPLE_QUERY ?? "手机壳";

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

async function safeRun(label, fn, fallback) {
  console.error(`== ${label} ==`);
  try { return await fn(); }
  catch (e) {
    console.error(`!! ${label} failed: ${e.message}`);
    return fallback;
  }
}

const productResult = await safeRun(`product ${SAMPLE_ID}`, () => scrapeProduct(SAMPLE_ID), null);
// Only commit a fixture when we actually parsed a product — `{}` would fail schema validation.
if (productResult) saveOrPrint("product", productResult);
saveOrPrint("search", await safeRun(`search '${SAMPLE_QUERY}'`, () => scrapeSearch(SAMPLE_QUERY, 1), []));
