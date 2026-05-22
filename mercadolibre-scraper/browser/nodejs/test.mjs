// Live tests for MercadoLibre scraper. Skipped if SCRAPELESS_API_KEY is unset.

import assert from "node:assert/strict";
import { test } from "node:test";
import { parseProduct, parseSearch, scrapeProduct, scrapeSearch } from "./mercadolibre.mjs";

const HAS_KEY = !!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY);

test("parseProduct extracts required fields from ld+json", async () => {
  const html = `<html><head>
    <script type="application/ld+json">{"@type":"Product","sku":"MLM4493249540","name":"Tenis adidas","brand":"adidas","offers":{"@type":"Offer","price":735,"priceCurrency":"MXN","availability":"https://schema.org/InStock"},"aggregateRating":{"@type":"AggregateRating","ratingValue":4.9,"reviewCount":121},"image":"https://http2.mlstatic.com/img.webp","url":"https://articulo.mercadolibre.com.mx/MLM-4493249540"}</script>
    <script type="application/ld+json">{"@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":1,"name":"Calzado","item":"https://listado.mercadolibre.com.mx/calzado"}]}</script>
  </head><body></body></html>`;
  const prod = parseProduct(html, "https://articulo.mercadolibre.com.mx/MLM-4493249540");
  assert.equal(prod.id, "MLM4493249540");
  assert.equal(prod.name, "Tenis adidas");
  assert.equal(prod.price, 735);
  assert.equal(prod.priceCurrency, "MXN");
  assert.equal(prod.breadcrumb.length, 1);
});

test("parseSearch extracts cards from listing HTML", async () => {
  const html = `<html><body>
    <ul>
      <li class="ui-search-layout__item">
        <h2 class="poly-component__title">Tenis Nike</h2>
        <a href="https://articulo.mercadolibre.com.mx/MLM-123456-tenis-nike-_JM?tracking=1">link</a>
        <img src="https://http2.mlstatic.com/img.jpg" />
        <span class="andes-money-amount__fraction">1,299</span>
      </li>
    </ul>
  </body></html>`;
  const results = parseSearch(html);
  assert.equal(results.results.length, 1);
  assert.equal(results.results[0].name, "Tenis Nike");
  assert.ok(results.results[0].url.includes("MLM-123456"));
  assert.equal(results.results[0].price, 1299);
});

if (HAS_KEY) {
  test("scrapeProduct returns real data (live)", { timeout: 120000 }, async () => {
    const prod = await scrapeProduct(
      "https://articulo.mercadolibre.com.mx/MLM-4493249540-tenis-adidas-casual-run-60s-40-hombre-negro-jr6622-_JM"
    );
    assert.ok(prod.id, "id must be non-empty");
    assert.ok(prod.name, "name must be non-empty");
    assert.ok(prod.price != null, "price must be present");
  });

  test("scrapeSearch returns results (live)", { timeout: 120000 }, async () => {
    const results = await scrapeSearch("https://listado.mercadolibre.com.mx/tenis");
    assert.ok(Array.isArray(results), "must return array");
    assert.ok(results.length > 0, "must have results");
    assert.ok(results[0].name, "first result must have name");
  });
}
