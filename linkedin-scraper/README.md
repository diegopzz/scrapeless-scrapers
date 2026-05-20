# LinkedIn scraper

[linkedin.com](https://linkedin.com/) scraper powered by [Scrapeless](https://www.scrapeless.com/). Every surface drives a Scrapeless cloud [Scraping Browser](https://www.scrapeless.com/en/scraping-browser) and emits identical JSON shapes — see [`DATA_MODEL.md`](DATA_MODEL.md).

## Surfaces

Available surfaces live under [`browser/`](browser/) — pick whichever fits your stack:

| Surface | Path | Built on |
| --- | --- | --- |
| Python | [`browser/python`](browser/python/) | official `scrapeless` SDK + Playwright over CDP |
| Node.js | [`browser/nodejs`](browser/nodejs/) | official `@scrapeless-ai/sdk` + puppeteer-core over CDP |

## Functions

| Python | Node.js |
| --- | --- |
| `scrape_profile` | `scrapeProfile` |
| `scrape_company` | `scrapeCompany` |
| `scrape_job_search` | `scrapeJobSearch` |
| `scrape_jobs` | `scrapeJobs` |
| `scrape_articles` | `scrapeArticles` |

## Run

```bash
export SCRAPELESS_API_KEY=sk_...

# Python
cd browser/python && SAVE_TEST_RESULTS=true python run.py

# Node.js
cd browser/nodejs && SAVE_TEST_RESULTS=true node run.mjs

```

## Fixtures

- [`browser/nodejs/results/articles.json`](browser/nodejs/results/articles.json)
- [`browser/nodejs/results/company.json`](browser/nodejs/results/company.json)
- [`browser/nodejs/results/job_search.json`](browser/nodejs/results/job_search.json)
- [`browser/nodejs/results/jobs.json`](browser/nodejs/results/jobs.json)
- [`browser/nodejs/results/profile.json`](browser/nodejs/results/profile.json)
