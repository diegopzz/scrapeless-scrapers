// ChatGPT scraper using the official @scrapeless-ai/sdk + puppeteer-core over CDP.
//
// function names and emitted field names match verbatim.
//
// Flow:
// - Mint a cloud browser session (CDP WS endpoint).
// - puppeteer-core connects, opens `https://chatgpt.com/?prompt=<text>`.
// - Dismiss the credentials picker, click "send", capture the SSE response
//   from `/backend-anon/f/conversation` and feed it to `parseChatgptStream`.
// - For follow-up prompts, POST `/backend-anon/conversation` from inside
//   the page via in-page fetch (cookies + Cloudflare cookies stay alive).
//
// Public/anonymous content only.

import { Scrapeless } from "@scrapeless-ai/sdk";
import puppeteer from "puppeteer-core";
import { randomUUID } from "node:crypto";

const DEFAULT_PROXY_COUNTRY = "US";
const DEFAULT_SESSION_TTL = 300;

const TRANSIENT_NET_ERRORS = [
  "ERR_TUNNEL_CONNECTION_FAILED",
  "ERR_CONNECTION_CLOSED",
  "ERR_CONNECTION_RESET",
  "ERR_CONNECTION_REFUSED",
  "ERR_TIMED_OUT",
  "ERR_NETWORK_CHANGED",
  "ERR_EMPTY_RESPONSE",
  "ERR_PROXY_CONNECTION_FAILED",
  "Navigation timeout",
  "net::",
];

function isTransientError(err) {
  const msg = String(err?.message ?? err ?? "");
  return TRANSIENT_NET_ERRORS.some((s) => msg.includes(s));
}

function requireKey() {
  const k = process.env.SCRAPELESS_API_KEY ?? process.env.SCRAPELESS_KEY;
  if (!k) throw new Error("SCRAPELESS_API_KEY env var not set. Sign up at https://app.scrapeless.com");
  return k;
}

function client() {
  return new Scrapeless({ apiKey: requireKey() });
}

// Warm up the cloud browser session against the OpenAI marketing origin
// before opening chatgpt.com — establishes Cloudflare cookies on a less-
// defended endpoint so the chatgpt.com TLS handshake doesn't get ripped
// down with ERR_CONNECTION_CLOSED on the first hop.
async function warmupChatgpt(page) {
  try {
    await page.goto("https://chat.openai.com/", { waitUntil: "domcontentloaded", timeout: 30000 });
    await new Promise((r) => setTimeout(r, 2000));
  } catch (_) {}
}

async function withSessionRetry(fn, { retries = 2, label = "chatgpt" } = {}) {
  let lastError;
  for (let attempt = 0; attempt <= retries; attempt++) {
    const { browserWSEndpoint } = await client().browser.create({
      proxyCountry: DEFAULT_PROXY_COUNTRY, sessionTTL: DEFAULT_SESSION_TTL,
    });
    let browser;
    try {
      browser = await puppeteer.connect({ browserWSEndpoint });
      const page = await browser.newPage();
      return await fn(page, browser);
    } catch (e) {
      lastError = e;
      if (!isTransientError(e) && attempt > 0) throw e;
      if (attempt === retries) break;
      const sleepMs = 5000 * Math.pow(2, attempt);
      await new Promise((r) => setTimeout(r, sleepMs));
    } finally {
      try { await browser?.close(); } catch (_) {}
    }
  }
  throw new Error(`${label}: giving up after ${retries + 1} attempts: ${lastError?.message ?? lastError}`);
}

// ---------------- SSE parser (mirror of the upstream reference's parse_chatgpt_stream) ----------------

export function parseChatgptStream(rawSse) {
  const messages = new Map();
  let conversationId = null;
  let currentId = null;
  let lastO = null;
  let lastP = null;

  const store = (msg) => {
    const id = msg?.id;
    if (!id) return null;
    const parts = msg?.content?.parts ?? [""];
    messages.set(id, {
      role: msg?.author?.role ?? "",
      content: typeof parts[0] === "string" ? parts[0] : "",
    });
    return id;
  };

  const append = (p, o, v) => {
    if (o === "append" && typeof v === "string" && p && p.includes("content/parts/0") && currentId && messages.has(currentId)) {
      const m = messages.get(currentId);
      m.content += v;
      messages.set(currentId, m);
    }
  };

  for (let line of rawSse.split(/\r?\n/)) {
    line = line.trim();
    if (!line.startsWith("data:")) continue;
    const raw = line.slice(5).trim();
    if (raw === "[DONE]") break;
    let data;
    try { data = JSON.parse(raw); } catch { continue; }
    if (!data || typeof data !== "object") continue;

    if (data.type === "input_message") {
      currentId = store(data.input_message ?? {}) ?? currentId;
      conversationId = conversationId ?? data.conversation_id ?? null;
      continue;
    }

    lastO = data.o ?? lastO;
    lastP = data.p ?? lastP;
    const v = data.v;

    if (v && typeof v === "object" && !Array.isArray(v) && "message" in v) {
      currentId = store(v.message) ?? currentId;
      conversationId = conversationId
        ?? v.conversation_id
        ?? v.message?.metadata?.conversation_id
        ?? null;
    } else if (Array.isArray(v)) {
      for (const patch of v) append(patch?.p, patch?.o, patch?.v);
    } else {
      append(lastP, lastO, v);
    }
  }

  let parentMessageId = null;
  const ids = [...messages.keys()];
  for (let i = ids.length - 1; i >= 0; i--) {
    if (messages.get(ids[i]).role === "assistant") {
      parentMessageId = ids[i];
      break;
    }
  }
  const resultMessages = [];
  for (const m of messages.values()) {
    if (m.role && m.content) resultMessages.push({ role: m.role, content: m.content });
  }

  return {
    conversation_id: conversationId,
    parent_message_id: parentMessageId,
    messages: resultMessages,
  };
}

// ---------------- browser orchestration ----------------

async function dismissOverlays(page) {
  try { await page.click("#credentials-picker-container #close", { timeout: 2000 }); } catch (_) {}
  try { await page.click("div[aria-live='polite'] button", { timeout: 2000 }); } catch (_) {}
}

async function sendAndCapture(page, { timeoutMs = 60000 } = {}) {
  const captured = {};
  const handler = async (response) => {
    try {
      const url = response.url();
      if (!url.includes("backend-anon/f/conversation") && !url.includes("backend-anon/conversation")) return;
      const headers = response.headers() || {};
      const ctype = headers["content-type"] || "";
      if (!ctype.includes("event-stream") && !ctype.includes("stream")) return;
      const body = await response.text();
      const req = response.request();
      captured.sse_body = body;
      captured.request_body = req.postData() ?? "";
      captured.request_headers = req.headers();
    } catch (_) {}
  };
  page.on("response", handler);

  await page.waitForSelector("button[data-testid='send-button']", { timeout: 15000 });
  await dismissOverlays(page);
  await page.click("button[data-testid='send-button']");

  const deadline = Date.now() + timeoutMs;
  while (!captured.sse_body && Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, 500));
  }
  page.off("response", handler);
  return captured;
}

// ---------------- scrape functions ----------------

export async function scrapeConversation(prompt) {
  const url = `https://chatgpt.com/?prompt=${encodeURIComponent(prompt)}`;
  return withSessionRetry(async (page) => {
    await warmupChatgpt(page);
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
    const captured = await sendAndCapture(page, { timeoutMs: 60000 });
    const parsed = parseChatgptStream(captured.sse_body ?? "");
    const assistant = parsed.messages.filter((m) => m.role === "assistant").map((m) => m.content);
    return assistant.join("\n\n").trim();
  }, { label: "scrape_conversation" });
}

function buildPostRequest(prompt, conversationId, parentMessageId, originalBody, headers) {
  const newBody = { ...originalBody };
  newBody.conversation_id = conversationId;
  newBody.parent_message_id = parentMessageId;
  newBody.messages = [
    {
      id: randomUUID(),
      author: { role: "user" },
      create_time: Date.now() / 1000,
      content: { content_type: "text", parts: [prompt] },
    },
  ];
  return { headers, body: newBody };
}

export async function scrapeConversations(prompts) {
  if (!prompts?.length) return [];
  const firstUrl = `https://chatgpt.com/?prompt=${encodeURIComponent(prompts[0])}`;

  return withSessionRetry(async (page) => {
    let promptIndex = 0;
    const conversations = [];
    await warmupChatgpt(page);
    await page.goto(firstUrl, { waitUntil: "domcontentloaded", timeout: 45000 });
    const captured = await sendAndCapture(page, { timeoutMs: 60000 });

    const parsed = parseChatgptStream(captured.sse_body ?? "");
    let conversationId = parsed.conversation_id;
    let parentMessageId = parsed.parent_message_id;

    if (conversationId) {
      conversations.push({
        conversation_id: conversationId,
        messages: parsed.messages ?? [],
      });
    }

    let originalBody = {};
    try { originalBody = JSON.parse(captured.request_body || "{}"); } catch {}
    const headers = captured.request_headers || {};

    while (promptIndex < prompts.length - 1) {
      promptIndex += 1;
      if (!conversationId) break;
      const req = buildPostRequest(
        prompts[promptIndex], conversationId, parentMessageId ?? "", originalBody, headers,
      );
      const text = await page.evaluate(async ({ url, body, headers }) => {
        const res = await fetch(url, {
          method: "POST",
          headers,
          body: JSON.stringify(body),
          credentials: "include",
        });
        return await res.text();
      }, { url: "https://chatgpt.com/backend-anon/conversation", body: req.body, headers: req.headers });
      const postParsed = parseChatgptStream(text);
      if (postParsed.parent_message_id) parentMessageId = postParsed.parent_message_id;
      if (conversations.length && postParsed.messages?.length) {
        conversations[conversations.length - 1].messages.push(...postParsed.messages);
      }
    }
    return conversations;
  }, { label: "scrape_conversations" });
}
