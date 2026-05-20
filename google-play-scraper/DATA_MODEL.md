# GooglePlay data model

Single source of truth for the Python (cerberus) and Node (zod) schemas under [`python/`](python/) and [`nodejs/`](nodejs/).

The scraper drives `https://play.google.com/store/apps/details?id=<package>` through Scrapeless's [Scraping Browser](https://www.scrapeless.com/en/scraping-browser) and parses the embedded `application/ld+json` `SoftwareApplication` blob plus a small number of DOM helpers.

## App — emitted by `scrape_app`

| Field         | Type     | Required | Notes                                                                            |
| ------------- | -------- | -------- | -------------------------------------------------------------------------------- |
| id            | string   | yes      | App package id (e.g. `"com.spotify.music"`)                                     |
| name          | string   | yes      | App title from the SoftwareApplication JSON-LD                                   |
| developer     | string   | no       | Author name from JSON-LD                                                         |
| rating        | float    | no       | Average rating (1.0 – 5.0)                                                       |
| rating_count  | int      | no       | Number of ratings used to compute the average                                    |
| price         | string   | no       | Display price string (`"Free"` or `"$X.YZ"`)                                     |
| installs      | string   | no       | Install band label (e.g. `"500,000,000+ downloads"`)                              |
| description   | string   | no       | Long-form description from JSON-LD                                               |
| categories    | string[] | no       | Categories listed under "About this app" / JSON-LD `applicationCategory`         |
| latest_update | string   | no       | "Updated on" date string                                                         |
| screenshots   | string[] | no       | Screenshot image URLs                                                            |
| icon          | string   | no       | App icon URL                                                                     |
| url           | string   | yes      | Canonical listing URL                                                            |
