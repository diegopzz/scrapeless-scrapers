// Reddit scraper using @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// function names and emitted field names match verbatim, so downstream code
// can //
// Reddit serves two HTML surfaces: www.reddit.com (shreddit-* custom elements)
// and old.reddit.com (Listing-of-Things). The scraper hits whichever one the upstream reference
// hits per function.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import * as cheerio from "cheerio";

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

async function fetchResponse(url, { waitForSelector, warmup = true } = {}) {
  const { browserWSEndpoint } = await client().browser.create({
    proxyCountry: DEFAULT_PROXY_COUNTRY,
    sessionTTL: DEFAULT_SESSION_TTL,
  });
  const browser = await puppeteer.connect({ browserWSEndpoint });
  try {
    const page = await browser.newPage();
    // Reddit aggressively challenges fresh sessions, returning either a
    // "blocked by network security" interstitial or a JS challenge. Hitting
    // the homepage first lets Reddit drop a session cookie before navigating
    // to the user / subreddit page.
    if (warmup) {
      try {
        await page.goto("https://www.reddit.com/", { waitUntil: "domcontentloaded", timeout: 45000 });
        await new Promise((r) => setTimeout(r, 4000));
      } catch (_) {}
    }
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
    if (waitForSelector) {
      try { await page.waitForSelector(waitForSelector, { timeout: 15000 }); } catch (_) {}
    }
    const finalUrl = page.url();
    const html = await page.content();
    return { html, url: finalUrl };
  } finally {
    try { await browser.close(); } catch (_) {}
  }
}

export function parseSubreddit(response) {
  const $ = cheerio.load(response.html);
  const url = response.url;
  const info = {};
  info.id = url.split("/r")[url.split("/r").length - 1].replaceAll("/", "");
  info.description = $("shreddit-subreddit-header").attr("description") ?? null;
  const membersText = $("faceplate-number").filter((_, el) => {
    const sib = el.nextSibling;
    return sib && sib.type === "text" && sib.data && sib.data.includes("members");
  }).first().attr("number");
  const weeklyActive = $("shreddit-subreddit-header").attr("weekly-active-users");
  const rank = $("strong#position").text().trim();
  info.rank = rank || null;
  info.members = membersText ? parseInt(membersText, 10) : (weeklyActive ? parseInt(weeklyActive, 10) : null);
  info.bookmarks = {};
  $("div").find("faceplate-tracker[source='community_menu']").each((_, el) => {
    const a = $(el).find("a");
    const name = a.find("span span span").first().text() || null;
    const link = a.attr("href") || null;
    if (name && link) info.bookmarks[name] = link;
  });
  info.url = url;
  const postData = [];
  $("article[data-post-id]").each((_, el) => {
    const $box = $(el);
    const sp = $box.find("shreddit-post").first();
    const link = $box.find("a").first().attr("href");
    const author = sp.attr("author");
    const postLabel = $box.find("span.bg-tone-4 div").first().text().trim() || null;
    const upvotes = sp.attr("score");
    const commentCount = sp.attr("comment-count");
    const attachmentType = sp.attr("post-type");
    let attachmentLink = null;
    if (attachmentType === "image" || attachmentType === "gallery") {
      attachmentLink = $box.find("img.media-lightbox-img").attr("src") ?? null;
    } else if (attachmentType === "video") {
      attachmentLink = $box.find("shreddit-player").attr("preview") ?? null;
    }
    if (!attachmentLink) attachmentLink = sp.attr("content-href") ?? null;
    postData.push({
      authorProfile: author ? `https://www.reddit.com/user/${author}` : null,
      authorId: sp.attr("author-id") ?? null,
      title: $box.attr("aria-label") ?? null,
      link: link ? `https://www.reddit.com${link}` : null,
      publishingDate: sp.attr("created-timestamp") ?? null,
      postId: sp.attr("id") ?? null,
      postLabel,
      postUpvotes: upvotes ? parseInt(upvotes, 10) : null,
      commentCount: commentCount ? parseInt(commentCount, 10) : null,
      attachmentType: attachmentType ?? null,
      attachmentLink,
    });
  });
  const cursor = $("shreddit-post").attr("more-posts-cursor") ?? null;
  return { post_data: postData, info, cursor };
}

export async function scrapeSubreddit(subredditId, maxPages = null) {
  const baseUrl = `https://www.reddit.com/r/${subredditId}/`;
  let response = await fetchResponse(baseUrl, { waitForSelector: "shreddit-post" });
  const subredditData = {};
  let data = parseSubreddit(response);
  subredditData.info = data.info;
  subredditData.posts = data.post_data;
  let cursor = data.cursor;
  const makePaginationUrl = (cursorId) =>
    `https://www.reddit.com/svc/shreddit/community-more-posts/hot/?after=${cursorId}%3D%3D&t=DAY&name=${subredditId}&feedLength=3`;
  while (cursor && (maxPages === null || maxPages > 0)) {
    response = await fetchResponse(makePaginationUrl(cursor));
    data = parseSubreddit(response);
    cursor = data.cursor;
    subredditData.posts.push(...data.post_data);
    if (maxPages !== null) maxPages -= 1;
  }
  return subredditData;
}

export function parsePostInfo(response) {
  const $ = cheerio.load(response.html);
  const sp = $("shreddit-post").first();
  const comments = sp.attr("comment-count");
  const upvotes = sp.attr("score");
  const author = sp.attr("author");
  return {
    authorId: sp.attr("author-id") ?? null,
    author: author ?? null,
    authorProfile: author ? `https://www.reddit.com/user/${author}` : null,
    subreddit: (sp.attr("subreddit-prefixed-name") ?? "").replace("r/", ""),
    postId: sp.attr("id") ?? null,
    postLabel: $("faceplate-tracker[source='post'] a span div").first().text().trim() || null,
    publishingDate: sp.attr("created-timestamp") ?? null,
    postTitle: sp.attr("post-title") ?? null,
    postLink: $("shreddit-canonical-url-updater").attr("value") ?? null,
    commentCount: comments ? parseInt(comments, 10) : null,
    upvoteCount: upvotes ? parseInt(upvotes, 10) : null,
    attachmentType: sp.attr("post-type") ?? null,
    attachmentLink: sp.attr("content-href") ?? null,
  };
}

export function parsePostComments(response) {
  const $ = cheerio.load(response.html);

  function parseComment($box) {
    const author = $box.attr("data-author");
    const link = $box.attr("data-permalink");
    const dislikes = $box.find("span.dislikes").attr("title");
    const upvotes = $box.find("span.likes").attr("title");
    const downvotes = $box.find("span.unvoted").attr("title");
    return {
      authorId: $box.attr("data-author-fullname") ?? null,
      author: author ?? null,
      authorProfile: author ? `https://www.reddit.com/user/${author}` : null,
      commentId: $box.attr("data-fullname") ?? null,
      link: link ? `https://www.reddit.com${link}` : null,
      publishingDate: $box.find("time").attr("datetime") ?? null,
      commentBody: $box.find("div.md > p").first().text() || null,
      upvotes: upvotes ? parseInt(upvotes, 10) : null,
      dislikes: dislikes ? parseInt(dislikes, 10) : null,
      downvotes: downvotes ? parseInt(downvotes, 10) : null,
    };
  }

  function parseReplies($what) {
    const replies = [];
    $what.find("div[data-type='comment']").each((_, el) => {
      const $reply = $(el);
      const replyComment = parseComment($reply);
      const childReplies = parseReplies($reply);
      if (childReplies.length) replyComment.replies = childReplies;
      replies.push(replyComment);
    });
    return replies;
  }

  const data = [];
  $("div.sitetable.nestedlisting > div[data-type='comment']").each((_, el) => {
    const $box = $(el);
    const commentData = parseComment($box);
    const replies = parseReplies($box);
    if (replies.length) commentData.replies = replies;
    data.push(commentData);
  });
  return data;
}

export async function scrapePost(url, sort) {
  let response = await fetchResponse(url, { waitForSelector: "shreddit-post" });
  const postData = {};
  postData.info = parsePostInfo(response);
  const postLink = postData.info.postLink || postData.info.attachmentLink;
  const bulkUrl = postLink.replace("www", "old") + `?sort=${sort}&limit=500`;
  response = await fetchResponse(bulkUrl);
  postData.comments = parsePostComments(response);
  return postData;
}

export function parseUserPosts(response) {
  const $ = cheerio.load(response.html);
  const data = [];
  // Modern Reddit (www.reddit.com) uses `<shreddit-post>` custom elements for
  // posts on user profiles. Each carries the post metadata as attributes.
  $("shreddit-post").each((_, el) => {
    const sp = $(el);
    const author = sp.attr("author") || null;
    const permalink = sp.attr("permalink") || null;
    const commentCount = sp.attr("comment-count");
    const postScore = sp.attr("score");
    const subreddit = sp.attr("subreddit-prefixed-name") || null;
    const postType = sp.attr("post-type") || null;
    let attachmentLink = sp.attr("content-href") || null;
    if (attachmentLink && attachmentLink.startsWith("/")) {
      attachmentLink = `https://www.reddit.com${attachmentLink}`;
    }
    data.push({
      authorId: sp.attr("author-id") || null,
      author,
      authorProfile: author ? `https://www.reddit.com/user/${author}` : null,
      postId: sp.attr("id") || null,
      postLink: permalink ? `https://www.reddit.com${permalink}` : null,
      postTitle: sp.attr("post-title") || null,
      postSubreddit: subreddit,
      publishingDate: sp.attr("created-timestamp") || null,
      commentCount: commentCount ? parseInt(commentCount, 10) : null,
      postScore: postScore ? parseInt(postScore, 10) : null,
      attachmentType: postType,
      attachmentLink,
    });
  });
  const nextPageUrl = $("shreddit-post").last().attr("more-posts-cursor") ?? null;
  return { data, url: nextPageUrl };
}

export async function scrapeUserPosts(username, sort, maxPages = null) {
  const url = `https://www.reddit.com/user/${username}/submitted/?sort=${sort}`;
  const response = await fetchResponse(url, { waitForSelector: "shreddit-post" });
  const { data } = parseUserPosts(response);
  return data;
}

export function parseUserComments(response) {
  const $ = cheerio.load(response.html);
  const data = [];
  // Modern Reddit user-comments are wrapped in <shreddit-profile-comment>.
  // The thread "Reply to" context lives in the comment's `aria-label`
  // ("Thread for <user>'s comment on <post title>") and the parent `href`.
  $("shreddit-profile-comment").each((_, el) => {
    const $c = $(el);
    const commentId = $c.attr("comment-id") || null;
    const href = $c.attr("href") || null; // /r/<sub>/comments/<post>/comment/<id>/
    const author = "spez_placeholder"; // overridden below from username arg
    // Pull thread title from inner <a aria-label="Thread for X's comment on TITLE">
    const ariaLabel = $c.find("a[aria-label*='comment on']").first().attr("aria-label") || "";
    let postTitle = null;
    let postAuthor = null;
    const m = /^Thread for ([^']+)'s comment on (.+)$/.exec(ariaLabel.trim());
    if (m) {
      postAuthor = m[1];
      postTitle = m[2];
    }
    // Parent subreddit lives on the comment's first /r/ link.
    let postSubreddit = null;
    const subRe = /^\/r\/([^/]+)\//;
    if (href) {
      const sm = subRe.exec(href);
      if (sm) postSubreddit = `r/${sm[1]}`;
    }
    // Comment body sits in the slotted body element.
    const bodyEl = $c.find("div[id*='comment'][slot='comment'], div.md, div.text-14, p").first();
    const commentBody = (bodyEl.text() || "").trim();
    const attachedLinks = $c.find("a[href^='http']")
      .map((_, a) => $(a).attr("href"))
      .get()
      .filter((u) => u && !u.includes("reddit.com"));
    let parentLink = null;
    if (href) {
      // Strip the trailing /comment/<id>/?context=N to get the post link.
      parentLink = `https://www.reddit.com${href.split("/comment/")[0]}/`;
    }
    data.push({
      authorId: null,
      author,
      authorProfile: author ? `https://www.reddit.com/user/${author}` : null,
      commentId,
      commentLink: href ? `https://www.reddit.com${href}` : null,
      commentBody,
      attachedCommentLinks: attachedLinks,
      publishingDate: $c.find("faceplate-timeago time").attr("datetime") || $c.find("time").attr("datetime") || null,
      dislikes: null,
      upvotes: null,
      downvotes: null,
      replyTo: {
        postTitle,
        postLink: parentLink,
        postAuthor,
        postSubreddit,
      },
    });
  });
  return { data, url: null };
}

export async function scrapeUserComments(username, sort, maxPages = null) {
  const url = `https://www.reddit.com/user/${username}/comments/?sort=${sort}`;
  const response = await fetchResponse(url, { waitForSelector: "shreddit-profile-comment" });
  const { data } = parseUserComments(response);
  // Backfill the author (parser doesn't have access to the original username).
  for (const c of data) {
    c.author = username;
    c.authorProfile = `https://www.reddit.com/user/${username}`;
  }
  return data;
}
