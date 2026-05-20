// Run the scrape functions live and optionally write results/*.json.
//
// Usage:
//   SCRAPELESS_API_KEY=sk_... node run.mjs
//   SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true node run.mjs

import { scrapeProduct, scrapeSearch } from "./shein.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SAMPLE_PRODUCT_URL =
  process.env.SHEIN_SAMPLE_PRODUCT_URL ??
  "https://us.shein.com/Solid-Pattern-Crop-Tank-Top-p-12042156.html";
const SAMPLE_QUERY = process.env.SHEIN_SAMPLE_QUERY ?? "summer dress";

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

const productResult = await safeRun(`product ${SAMPLE_PRODUCT_URL}`, () => scrapeProduct(SAMPLE_PRODUCT_URL), null);
// Only commit a fixture when we actually parsed a product — `{}` would fail schema validation.
if (productResult) saveOrPrint("product", productResult);
saveOrPrint("search", await safeRun(`search '${SAMPLE_QUERY}'`, () => scrapeSearch(SAMPLE_QUERY, 1), []));
