# Glassdoor — CLI surface

Scrape Glassdoor jobs and salaries pages from the command line with the
[`scrapeless-scraping-browser`](https://www.npmjs.com/package/scrapeless-scraping-browser)
CLI. One Scrapeless cloud session drives a real browser; each page is extracted in-browser with the
CLI's `eval` subcommand. Output matches the `nodejs/` and `python/` surfaces — see
[`../../DATA_MODEL.md`](../../DATA_MODEL.md).

The CLI surface covers the two DOM-rendered functions — jobs and salaries. The `scrape_reviews` and
`find_companies` functions in `nodejs/` hit Glassdoor's JSON APIs rather than rendered pages, so
they are not exposed here.

## 1. Install

```bash
npm install -g scrapeless-scraping-browser
```

`node` is also required — the steps below use it to pull values out of the CLI's JSON envelope
(`jq` works too, if preferred).

## 2. Set your API key

```bash
export SCRAPELESS_API_KEY=sk_...      # sign up at https://app.scrapeless.com
```

## 3. Scrape your first page

Every scrape is the same four moves: open a session, navigate, wait for a stable marker, run an
in-page extractor. Start with a jobs page.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name glassdoor-cli --ttl 300 --proxy-country US --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate, then wait for the job cards to render
scrapeless-scraping-browser --session-id "$SID" open "https://www.glassdoor.com/Jobs/eBay-Jobs-E7853.htm?filter.countryId=1"
scrapeless-scraping-browser --session-id "$SID" wait "div[class*=jobCard]"

# run the in-page extractor — its JSON comes back in data.result
# save the jobs extractor (a single expression returning a JSON string)
cat > jobs.js <<'JS'
// In-page extractor for a Glassdoor jobs page (/Jobs/...htm).
// Returns a JSON string — a list of Job (see ../../../DATA_MODEL.md).
JSON.stringify(
  Array.from(document.querySelectorAll("div[class*='jobCard']"))
    .filter((el) => /JobCard/.test(el.getAttribute("class") || ""))
    .map((box) => {
      const firstA = box.querySelector("a");
      const jobDate = document.querySelector("div[data-test='job-age']");
      return {
        jobTitle: (firstA?.textContent ?? "").trim() || null,
        jobLink: firstA?.getAttribute("href") ?? null,
        job_location:
          box.querySelector("div[data-test='emp-location']")?.textContent || null,
        jobSalary:
          box.querySelector("div[data-test='detailSalary']")?.textContent || null,
        jobDate: jobDate?.textContent || null,
      };
    })
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat jobs.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a list of `Job`:

```json
[
  {
    "jobTitle": "Warehouse Lead",
    "jobLink": "https://www.glassdoor.com/job-listing/warehouse-lead-ebay-JV_IC1126888_KO0,14_KE15,19.htm?jl=1010128660562",
    "job_location": "Moonachie, NJ",
    "jobSalary": "$40K - $78K (Employer provided)",
    "jobDate": "4d"
  }
]
```

## 4. Scrape a salaries page

Reuse the same session — just `open` a salaries URL and wait for the salary items.

```bash
scrapeless-scraping-browser --session-id "$SID" open "https://www.glassdoor.com/Salary/eBay-Salaries-E7853.htm"
scrapeless-scraping-browser --session-id "$SID" wait "[data-test=salary-item]"
# save the salaries extractor (a single expression returning a JSON string)
cat > salaries.js <<'JS'
// In-page extractor for a Glassdoor salaries page (/Salary/...htm).
// Returns a JSON string — a Salary dict (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const txt = (node) => (node?.textContent ?? "").trim();
    const salaryData = { results: [], numPages: 1, salaryCount: 0, jobTitleCount: 0 };

    document.querySelectorAll("[data-test='salary-item']").forEach((el) => {
      const jobTitle = txt(el.querySelector(".SalaryItem_jobTitle__XWGpT"));
      if (!jobTitle) return;
      const salaryRange = txt(el.querySelector(".SalaryItem_salaryRange__UL9vQ"));
      const salaryCountText = txt(el.querySelector(".SalaryItem_salaryCount__GT665"));
      let salaryCount = 0;
      if (salaryCountText.includes("Salaries submitted")) {
        const n = parseInt(salaryCountText.split(/\s+/)[0] || "0", 10);
        if (!Number.isNaN(n)) salaryCount = n;
      }
      const entry = {
        jobTitle: { text: jobTitle },
        salaryCount,
        basePayStatistics: { percentiles: [] },
      };
      if (salaryRange) {
        const clean = salaryRange.replace(/\$/g, "").replace(/K/g, "000");
        if (clean.includes(" - ")) {
          const [a, b] = clean.split(" - ");
          const minVal = parseFloat(a.replace(/,/g, ""));
          const maxVal = parseFloat(b.replace(/,/g, ""));
          if (!Number.isNaN(minVal) && !Number.isNaN(maxVal)) {
            entry.basePayStatistics.percentiles = [
              { ident: "min", value: minVal },
              { ident: "max", value: maxVal },
            ];
          }
        }
      }
      salaryData.results.push(entry);
    });

    const pageLinks = Array.from(
      document.querySelectorAll(".pagination_PageNumberText__F7427")
    ).map((p) => txt(p));
    if (pageLinks.length) {
      const nums = pageLinks
        .map((p) => parseInt(p, 10))
        .filter((n) => !Number.isNaN(n));
      if (nums.length) salaryData.numPages = Math.max(...nums);
    }

    const countText = txt(document.querySelector(".SortBar_SearchCount__cYwt6"));
    if (countText.includes("job titles")) {
      const n = parseInt(
        (countText.split(/\s+/)[0] || "0").replace(/,/g, ""),
        10
      );
      if (!Number.isNaN(n)) salaryData.jobTitleCount = n;
    }

    salaryData.salaryCount = salaryData.results.length;
    return salaryData;
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat salaries.js)" --json
```

`data.result` is a single `Salary` dict — a `results` list of `SalaryItem` plus pagination counts:

```json
{
  "results": [
    {
      "jobTitle": { "text": "Software Engineer 3" },
      "salaryCount": 921,
      "basePayStatistics": {
        "percentiles": [
          { "ident": "min", "value": 189000 },
          { "ident": "max", "value": 245000 }
        ]
      }
    }
  ],
  "numPages": 1,
  "salaryCount": 0,
  "jobTitleCount": 0
}
```

## 5. Output shape

Each `eval/*.js` file is a single expression that returns a JSON string, kept in lockstep with the
selectors in [`../nodejs/glassdoor.mjs`](../nodejs/glassdoor.mjs):

| Extractor | Returns |
| --- | --- |
| `jobs.js` | list of `Job` |
| `salaries.js` | one `Salary` dict |

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in
[`results/`](results/).
