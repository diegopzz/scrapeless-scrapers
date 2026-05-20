# Google Play — CLI surface

Scrape Google Play app detail pages from the command line with the
[`scrapeless-scraping-browser`](https://www.npmjs.com/package/scrapeless-scraping-browser)
CLI. One Scrapeless cloud session drives a real browser; the app page is extracted in-browser with
the CLI's `eval` subcommand. Output matches the `nodejs/` and `python/` surfaces — see
[`../../DATA_MODEL.md`](../../DATA_MODEL.md).

The CLI surface covers `scrape_app`. `scrape_apps` from `nodejs/` is just a loop over `scrape_app` —
re-run with a different `GOOGLE_PLAY_SAMPLE_ID` per app.

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
in-page extractor. The cleanest fields come from the embedded `application/ld+json`
`SoftwareApplication` blob, so the run waits for that script tag before extracting.

```bash
# open a cloud browser session — returns a task id in data.taskId
scrapeless-scraping-browser new-session --name google-play-cli --ttl 300 --proxy-country US --json
#   -> {"data":{"taskId":"<SID>"}}

SID=<SID>   # paste the taskId from above

# navigate to an app detail page, then wait for the JSON-LD blob
scrapeless-scraping-browser --session-id "$SID" open "https://play.google.com/store/apps/details?id=com.spotify.music&hl=en_US&gl=US"
scrapeless-scraping-browser --session-id "$SID" wait "script[type='application/ld+json']"

# run the in-page extractor — its JSON comes back in data.result
# save the app extractor (a single expression returning a JSON string)
cat > app.js <<'JS'
// In-page extractor for a Google Play app detail page
// (https://play.google.com/store/apps/details?id=<package>).
// Returns a JSON string — a single App (see ../../../DATA_MODEL.md).
JSON.stringify(
  (function () {
    const txt = (node) => (node?.textContent ?? "").trim();

    // Pick out the SoftwareApplication blob from one of the JSON-LD scripts.
    const findSoftwareApplicationLd = () => {
      let found = null;
      document
        .querySelectorAll("script[type='application/ld+json']")
        .forEach((el) => {
          if (found) return;
          const raw = (el.textContent || "").trim();
          if (!raw) return;
          try {
            const parsed = JSON.parse(raw);
            const arr = Array.isArray(parsed) ? parsed : [parsed];
            for (const obj of arr) {
              const t = obj && obj["@type"];
              if (typeof t === "string" && t.toLowerCase().includes("application")) {
                found = obj;
                return;
              }
              if (
                Array.isArray(t) &&
                t.some((s) => String(s).toLowerCase().includes("application"))
              ) {
                found = obj;
                return;
              }
            }
          } catch (e) {}
        });
      return found;
    };

    const readMetaTitle = () =>
      document.querySelector("meta[property='og:title']")?.getAttribute("content") ||
      document.querySelector("meta[name='twitter:title']")?.getAttribute("content") ||
      txt(document.querySelector("title"));

    const readMetaDescription = () =>
      document.querySelector("meta[name='description']")?.getAttribute("content") ||
      document.querySelector("meta[property='og:description']")?.getAttribute("content") ||
      "";

    const readIcon = () =>
      document.querySelector("meta[property='og:image']")?.getAttribute("content") ||
      document.querySelector("img[alt='Icon image']")?.getAttribute("src") ||
      "";

    const readDeveloper = () =>
      txt(
        document.querySelector(
          "a[href*='/store/apps/dev'], a[href*='/store/apps/developer']"
        )
      ) || "";

    const readInstallBand = () => {
      let band = "";
      const els = document.querySelectorAll("div, span");
      for (const el of els) {
        if (txt(el) === "Downloads") {
          const sib = el.parentElement?.children?.[0];
          const v = txt(sib);
          if (v && /[\d+]/.test(v)) {
            band = v + " Downloads";
            break;
          }
        }
      }
      if (band) return band;
      const m = (document.body.textContent || "").match(
        /(\d[\d,]*\+)\s+(downloads|installs)/i
      );
      return m ? m[1] + " " + m[2] : "";
    };

    const readLatestUpdate = () => {
      let value = "";
      const els = document.querySelectorAll("div, span");
      for (const el of els) {
        if (/^Updated(?: on)?$/i.test(txt(el))) {
          const v = txt(el.nextElementSibling);
          if (v) {
            value = v;
            break;
          }
        }
      }
      if (value) return value;
      return (
        document
          .querySelector("[itemprop='datePublished']")
          ?.getAttribute("content") || ""
      );
    };

    const readCategories = (ld) => {
      const cats = new Set();
      const cat = ld && ld.applicationCategory;
      if (typeof cat === "string") cats.add(cat.trim());
      if (Array.isArray(cat)) for (const c of cat) cats.add(String(c).trim());
      document
        .querySelectorAll("a[href*='/store/apps/category/']")
        .forEach((el) => {
          const t = txt(el);
          if (t && !/^view all|see more/i.test(t)) cats.add(t);
        });
      return [...cats].filter(Boolean);
    };

    const readScreenshots = () => {
      const seen = new Set();
      const out = [];
      document
        .querySelectorAll("img[src*='play-lh.googleusercontent.com']")
        .forEach((el) => {
          const src = (el.getAttribute("src") || "").split("=")[0];
          if (!src || seen.has(src)) return;
          seen.add(src);
          out.push(src);
        });
      return out.slice(1, 21);
    };

    const readPrice = (ld) => {
      const offers = ld && ld.offers;
      const offerList = Array.isArray(offers) ? offers : offers ? [offers] : [];
      for (const o of offerList) {
        if (!o) continue;
        if (o.price === "0" || o.price === 0 || o.price === "0.00") return "Free";
        if (o.price && o.priceCurrency) return o.priceCurrency + " " + o.price;
        if (o.price) return String(o.price);
      }
      const btn = txt(document.querySelector("button[aria-label^='Install']"));
      return btn || "";
    };

    const parseFloatOrNull = (v) => {
      const n = Number(v);
      return Number.isFinite(n) ? n : null;
    };
    const parseIntOrNull = (v) => {
      const n = parseInt(String(v), 10);
      return Number.isFinite(n) ? n : null;
    };

    const ld = findSoftwareApplicationLd();
    const params = new URLSearchParams(location.search);
    const packageId = params.get("id") || "";

    return {
      id: packageId,
      name: (ld?.name ?? readMetaTitle() ?? "").trim(),
      developer: (ld?.author?.name ?? ld?.author ?? readDeveloper() ?? "")
        .toString()
        .trim(),
      rating: parseFloatOrNull(ld?.aggregateRating?.ratingValue),
      rating_count: parseIntOrNull(
        ld?.aggregateRating?.ratingCount ?? ld?.aggregateRating?.reviewCount
      ),
      price: readPrice(ld),
      installs: readInstallBand(),
      description: (ld?.description ?? readMetaDescription() ?? "").trim(),
      categories: readCategories(ld),
      latest_update: readLatestUpdate(),
      screenshots: readScreenshots(),
      icon: (ld?.image ?? ld?.logo ?? readIcon() ?? "").toString().trim(),
      url: location.href,
    };
  })()
)
JS

scrapeless-scraping-browser --session-id "$SID" eval "$(cat app.js)" --json

# release the session when done
scrapeless-scraping-browser --session-id "$SID" close
```

`data.result` is a single `App`:

```json
{
  "id": "com.spotify.music",
  "name": "Spotify: Music and Podcasts",
  "developer": "Spotify AB",
  "rating": 4.336979389190674,
  "rating_count": 35562293,
  "price": "Free",
  "installs": "1B+ Downloads",
  "categories": ["MUSIC_AND_AUDIO", "Kids"],
  "latest_update": "May 11, 2026",
  "icon": "https://play-lh.googleusercontent.com/...",
  "url": "https://play.google.com/store/apps/details?id=com.spotify.music&hl=en_US&gl=US"
}
```

## 4. Output shape

The single `eval/*.js` file is a one-line expression that returns a JSON string, kept in lockstep
with the JSON-LD + DOM helpers in [`../nodejs/google-play.mjs`](../nodejs/google-play.mjs):

| Extractor | Returns |
| --- | --- |
| `app.js` | one `App` |

Full field tables — types, which are required, where each comes from — are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in
[`results/`](results/).
