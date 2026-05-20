// Run the scrape functions live and optionally write results/*.json.

import { scrapeCompany, scrapePerson } from "./crunchbase.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const RESULTS_DIR = path.resolve(HERE, "results");

const SAMPLE_COMPANY_URL = "https://www.crunchbase.com/organization/tesla-motors/people";
const SAMPLE_PERSON_URL = "https://www.crunchbase.com/person/elon-musk";

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

console.error(`== company ${SAMPLE_COMPANY_URL} ==`);
saveOrPrint("company", await scrapeCompany(SAMPLE_COMPANY_URL));

console.error(`== person ${SAMPLE_PERSON_URL} ==`);
saveOrPrint("person", await scrapePerson(SAMPLE_PERSON_URL));
