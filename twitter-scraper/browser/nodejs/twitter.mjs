// Twitter (X.com) scraper using @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// function names and emitted field names match verbatim, so downstream code
// can //
// Public data only. Tweet detail + public profile pages render unauthenticated;
// replies / search / following lists require login and are out of scope.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";

const DEFAULT_PROXY_COUNTRY = "US";
const DEFAULT_SESSION_TTL = 180;

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}

function client() {
  return new Scrapeless({ apiKey: requireKey() });
}

async function scrapeTwitterApp(url, { waitForSelector, xhrUrlSubstring, retries = 0 } = {}) {
  const { browserWSEndpoint } = await client().browser.create({
    proxyCountry: DEFAULT_PROXY_COUNTRY,
    sessionTTL: DEFAULT_SESSION_TTL,
  });
  const captured = [];
  let html = "";
  const browser = await puppeteer.connect({ browserWSEndpoint });
  try {
    const page = await browser.newPage();
    page.on("response", async (resp) => {
      try {
        if (resp.url().includes(xhrUrlSubstring)) {
          const body = await resp.json();
          captured.push(body);
        }
      } catch (_) {}
    });
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
    if (waitForSelector) {
      try {
        await page.waitForSelector(waitForSelector, { timeout: 15000 });
      } catch (_) {}
    }
    for (let i = 0; i < 5; i++) {
      await page.evaluate(() => window.scrollBy(0, window.innerHeight));
      await new Promise((r) => setTimeout(r, 1000));
    }
    html = await page.content();
  } finally {
    try { await browser.close(); } catch (_) {}
  }
  if (html.includes("Something went wrong, but") && retries < 2) {
    return scrapeTwitterApp(url, { waitForSelector, xhrUrlSubstring, retries: retries + 1 });
  }
  return captured;
}

export function parseTweet(data) {
  const result = {
    created_at: data?.legacy?.created_at,
    attached_urls: (data?.legacy?.entities?.urls ?? []).map((u) => u.expanded_url),
    attached_urls2: (data?.legacy?.entities?.url?.urls ?? []).map((u) => u.expanded_url),
    attached_media: (data?.legacy?.entities?.media ?? []).map((m) => m.media_url_https),
    tagged_users: (data?.legacy?.entities?.user_mentions ?? []).map((u) => u.screen_name),
    tagged_hashtags: (data?.legacy?.entities?.hashtags ?? []).map((h) => h.text),
    favorite_count: data?.legacy?.favorite_count,
    bookmark_count: data?.legacy?.bookmark_count,
    quote_count: data?.legacy?.quote_count,
    reply_count: data?.legacy?.reply_count,
    retweet_count: data?.legacy?.retweet_count,
    text: data?.legacy?.full_text,
    is_quote: data?.legacy?.is_quote_status,
    is_retweet: data?.legacy?.retweeted,
    language: data?.legacy?.lang,
    user_id: data?.legacy?.user_id_str,
    id: data?.legacy?.id_str,
    conversation_id: data?.legacy?.conversation_id_str,
    source: data?.source,
    views: data?.views?.count,
  };
  result.poll = {};
  const pollData = data?.card?.legacy?.binding_values ?? [];
  for (const entry of pollData) {
    const { key, value } = entry;
    if (key.includes("choice")) result.poll[key] = value.string_value;
    else if (key.includes("end_datetime")) result.poll.end = value.string_value;
    else if (key.includes("last_updated_datetime")) result.poll.updated = value.string_value;
    else if (key.includes("counts_are_final")) result.poll.ended = value.boolean_value;
    else if (key.includes("duration_minutes")) result.poll.duration = value.string_value;
  }
  const userData = data?.core?.user_results?.result;
  if (userData) result.user = parseProfile(userData);
  return result;
}

export async function scrapeTweet(url) {
  const bodies = await scrapeTwitterApp(url, {
    waitForSelector: "[data-testid='tweet']",
    xhrUrlSubstring: "TweetResultByRestId",
  });
  for (const body of bodies) {
    try {
      return parseTweet(body.data.tweetResult.result);
    } catch (_) {}
  }
  throw new Error("Failed to scrape tweet — no TweetResultByRestId XHR captured");
}

export function parseProfile(data) {
  return {
    id: data.id,
    rest_id: data.rest_id,
    verified: data.is_blue_verified,
    ...data.legacy,
  };
}

export async function scrapeProfile(url) {
  const bodies = await scrapeTwitterApp(url, {
    waitForSelector: "[data-testid='primaryColumn']",
    xhrUrlSubstring: "UserTweets",
  });
  for (const body of bodies) {
    let instructions;
    try {
      instructions = body.data.user.result.timeline.timeline.instructions;
    } catch (_) {
      continue;
    }
    for (const instruction of instructions) {
      for (const entry of instruction.entries ?? []) {
        const item = entry.content?.itemContent ?? {};
        if (item.__typename !== "TimelineTweet") continue;
        const userResult = item.tweet_results.result.core.user_results.result;
        if (userResult.rest_id) return parseProfile(userResult);
      }
    }
  }
  throw new Error("Failed to scrape user profile - no matching user data background requests");
}
