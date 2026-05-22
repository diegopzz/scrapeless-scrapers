// Live tests for Flipkart scraper. Skipped if SCRAPELESS_API_KEY is unset.

import assert from "node:assert/strict";
import { test } from "node:test";
import { parseProduct, parseSearch, scrapeProduct, scrapeSearch } from "./flipkart.mjs";

const HAS_KEY = !!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY);

test("parseProduct extracts required fields from ld+json array", async () => {
  const html = `<html><head>
    <script type="application/ld+json">[{"@type":"Product","sku":"MOBH4DQF849HCG6G","name":"Apple iPhone 16 (White, 128 GB)","brand":{"name":"APPLE","@type":"Brand"},"description":"Buy Apple iPhone 16 online at best price","image":["https://rukmini1.flixcart.com/image/1500/1500/img.jpeg"],"offers":{"@type":"Offer","price":69900,"priceCurrency":"INR","availability":"https://schema.org/InStock"},"aggregateRating":{"@type":"AggregateRating","ratingValue":4.6,"reviewCount":6805},"@context":"http://schema.org"}]</script>
  </head><body></body></html>`;
  const prod = parseProduct(html, "https://www.flipkart.com/apple-iphone-16-white-128-gb/p/itm7c0281cd247be");
  assert.equal(prod.id, "MOBH4DQF849HCG6G");
  assert.equal(prod.name, "Apple iPhone 16 (White, 128 GB)");
  assert.equal(prod.brand, "APPLE");
  assert.equal(prod.price, 69900);
  assert.equal(prod.priceCurrency, "INR");
  assert.equal(prod.ratingValue, 4.6);
  assert.equal(prod.reviewCount, 6805);
  assert.deepEqual(prod.breadcrumb, []);
});

test("parseSearch extracts cards from search HTML", async () => {
  const html = `<html><body>
    <div data-id="MOBH4DQF849HCG6G">
      <a href="/apple-iphone-16-white-128-gb/p/itm7c0281cd247be?pid=MOBH4DQF849HCG6G">
        <img src="https://rukminim2.flixcart.com/image/312/312/img.jpeg" alt="Apple iPhone 16 (White, 128 GB)" />
        <div class="RG5Slk">Apple iPhone 16 (White, 128 GB)</div>
        <div class="hZ3P6w">₹69,900</div>
        <div class="MKiFS6">4.6</div>
      </a>
    </div>
  </body></html>`;
  const results = parseSearch(html);
  assert.equal(results.results.length, 1);
  assert.equal(results.results[0].id, "MOBH4DQF849HCG6G");
  assert.equal(results.results[0].name, "Apple iPhone 16 (White, 128 GB)");
  assert.equal(results.results[0].price, 69900);
  assert.equal(results.results[0].ratingValue, 4.6);
  assert.ok(results.results[0].url.includes("/p/itm7c0281cd247be"));
});

if (HAS_KEY) {
  test("scrapeProduct returns real data (live)", { timeout: 180000 }, async () => {
    const prod = await scrapeProduct(
      "https://www.flipkart.com/apple-iphone-16-white-128-gb/p/itm7c0281cd247be"
    );
    assert.ok(prod.id, "id must be non-empty");
    assert.ok(prod.name, "name must be non-empty");
    assert.ok(prod.price != null, "price must be present");
  });

  test("scrapeSearch returns results (live)", { timeout: 120000 }, async () => {
    const results = await scrapeSearch(
      "https://www.flipkart.com/search?q=iphone+16&marketplace=FLIPKART"
    );
    assert.ok(Array.isArray(results), "must return array");
    assert.ok(results.length > 0, "must have results");
    assert.ok(results[0].name, "first result must have name");
  });
}
