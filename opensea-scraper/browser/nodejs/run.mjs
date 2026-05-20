// Run the OpenSea scrape functions live and optionally write results/*.json.
//
// Usage:
//   SCRAPELESS_API_KEY=sk_... node run.mjs
//   SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true node run.mjs

import { scrapeCollection, scrapeAsset } from "./opensea.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SAMPLE_SLUG = process.env.OPENSEA_SAMPLE_SLUG ?? "boredapeyachtclub";
const SAMPLE_CHAIN = process.env.OPENSEA_SAMPLE_CHAIN ?? "ethereum";
const SAMPLE_CONTRACT = process.env.OPENSEA_SAMPLE_CONTRACT ?? "0xbc4ca0eda7647a8ab7c2061c2e118a18a936f13d";
const SAMPLE_TOKEN_ID = process.env.OPENSEA_SAMPLE_TOKEN_ID ?? "1";

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

console.error(`== collection '${SAMPLE_SLUG}' ==`);
saveOrPrint("collection", await scrapeCollection(SAMPLE_SLUG));

console.error(`== asset ${SAMPLE_CHAIN}/${SAMPLE_CONTRACT}/${SAMPLE_TOKEN_ID} ==`);
saveOrPrint("asset", await scrapeAsset(SAMPLE_CHAIN, SAMPLE_CONTRACT, SAMPLE_TOKEN_ID));
