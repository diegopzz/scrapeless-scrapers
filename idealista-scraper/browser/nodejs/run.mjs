// Run Idealista scrape functions live and optionally write results/*.json.
//
// Usage:
//   SCRAPELESS_API_KEY=sk_... node run.mjs
//   SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true node run.mjs

import { scrapeProperties, scrapeProvinces, scrapeSearch } from "./idealista.mjs";
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

// Live Marbella listings; idealista delists properties once they sell, so we
// expose both as a CSV env var (IDEALISTA_PROPERTIES) for easy rotation.
const SAMPLE_PROPERTIES = (process.env.IDEALISTA_PROPERTIES
  ?? "https://www.idealista.com/en/inmueble/111070021/,https://www.idealista.com/en/inmueble/108649518/").split(",");
const SAMPLE_SEARCH = "https://www.idealista.com/en/venta-viviendas/marbella-malaga/con-chalets/";
const SAMPLE_PROVINCES = ["https://www.idealista.com/venta-viviendas/almeria-provincia/municipios"];

console.error("== properties ==");
saveOrPrint("properties", await scrapeProperties(SAMPLE_PROPERTIES));

console.error("== search ==");
saveOrPrint("search", await scrapeSearch(SAMPLE_SEARCH, 2));

console.error("== provinces ==");
saveOrPrint("provinces", await scrapeProvinces(SAMPLE_PROVINCES));
