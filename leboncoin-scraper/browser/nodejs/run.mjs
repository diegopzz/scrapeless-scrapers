// Run the scrape functions live and optionally write results/*.json.
//
// Usage:
//   SCRAPELESS_API_KEY=sk_... node run.mjs
//   SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true node run.mjs

import { scrapeAd, scrapeSearch } from "./leboncoin.mjs";
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

console.error("running Leboncoin scrape");

const search = await scrapeSearch(
  "https://www.leboncoin.fr/recherche?text=coffe",
  false,
  2,
);
saveOrPrint("search", search);

const adUrls = [
  "https://www.leboncoin.fr/ad/ventes_immobilieres/2919253293",
  "https://www.leboncoin.fr/ad/ventes_immobilieres/2013383512",
  "https://www.leboncoin.fr/ad/ventes_immobilieres/3027789970",
];
const ads = await Promise.all(adUrls.map((u) => scrapeAd(u)));
saveOrPrint("ads", ads);
