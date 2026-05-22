# Google Maps — CLI surface

Scrape Google Maps place lists and place detail pages from the command line with the
[`scrapeless-scraping-browser`](https://www.npmjs.com/package/scrapeless-scraping-browser)
CLI. One Scrapeless cloud session drives a real browser; each page is extracted in-browser with the
CLI's `eval` subcommand. Output matches the `nodejs/` and `python/` surfaces — see
[`../../DATA_MODEL.md`](../../DATA_MODEL.md).

## 1. Install

    npm install -g scrapeless-scraping-browser

`node` is also required.

## 2. Set your API key

    export SCRAPELESS_API_KEY=sk_...

## 3. Navigate to Google Maps

Google Maps renders entirely client-side and its `load` event fires late.
Use `eval` to navigate via `window.location.href` instead of `open`, which avoids
the CLI's `load`-event timeout:

    scrapeless-scraping-browser new-session --name gmaps-cli --ttl 300 --proxy-country US --json
    SID=<taskId from above>

    scrapeless-scraping-browser --session-id "$SID" eval "window.location.href='https://www.google.com/maps/search/coffee+shops+in+Austin+TX'"
    scrapeless-scraping-browser --session-id "$SID" wait 10000

## 4. Extract a place list

The extractor reads `[role='feed'] [role='article']` card elements and their `innerText`:

    scrapeless-scraping-browser --session-id "$SID" eval "$(cat places.js)" --json

where `places.js` is the inline extractor saved below. `data.result` is an array of Place objects.

Sample `places.js` (in-browser extractor):

    JSON.stringify((function(){
      var MAPS_BASE='https://www.google.com/maps';
      var RATING_RE=/(\d+(?:[.,]\d+)?)/;
      function parseRating(t){var m=RATING_RE.exec(t);if(m){var v=parseFloat(m[1].replace(',','.'));return(v>=1&&v<=5)?v:null;}return null;}
      return Array.from(document.querySelectorAll("[role='feed'] [role='article']")).slice(0,5).map(function(article){
        var link=article.querySelector('a.hfpxzc');
        if(!link)return null;
        var name=link.getAttribute('aria-label').trim();
        var href=link.href;
        var lines=article.innerText.split('\n').map(function(l){return l.trim();}).filter(Boolean);
        var rating=null,category=null,address=null,priceLevel=null,description=null;
        for(var i=0;i<lines.length;i++){
          var ln=lines[i];
          if(!rating){var m=RATING_RE.exec(ln);if(m){var v=parseFloat(m[1].replace(',','.'));if(v>=1&&v<=5){rating=v;continue;}}}
          if(ln.indexOf(' · ')>=0){var parts=ln.split(' · ').map(function(p){return p.trim();});
            for(var j=0;j<parts.length;j++){var p=parts[j];
              if(!category&&/shop|cafe|restaurant|bar|market|lounge/i.test(p))category=p;
              else if(!priceLevel&&/^\$[\d–-]/.test(p))priceLevel=p;
              else if(!address&&/\d+\s+\w/.test(p)&&p.length>6)address=p;
            }
          }else if(!description&&ln.length>15&&!/^(Open|Closed)/i.test(ln))description=ln;
        }
        return{name:name,category:category||null,address:address||null,phone:null,website:null,
               rating:rating,review_count:null,price_level:priceLevel||null,description:description||null,
               url:href.startsWith('http')?href:MAPS_BASE+href};
      }).filter(Boolean);
    })())

## 5. Extract a place detail

Navigate to a specific place URL, wait for the panel, then run the detail extractor:

    scrapeless-scraping-browser --session-id "$SID" eval "window.location.href='https://www.google.com/maps/place/Epoch+Coffee/@30.3186037,-97.7296551,15z/data=!4m6!3m5!1s0x8644ca6bc309e81b:0x1f1a903bbb66839!8m2!3d30.3186037!4d-97.7245402!16s%2Fg%2F1v76_180'"
    scrapeless-scraping-browser --session-id "$SID" wait 10000
    scrapeless-scraping-browser --session-id "$SID" eval "$(cat place.js)" --json

Sample `place.js` (in-browser extractor):

    JSON.stringify((function(){
      function getAriaVal(prefix){
        var els=document.querySelectorAll('[aria-label]');
        for(var i=0;i<els.length;i++){var l=els[i].getAttribute('aria-label')||'';if(l.indexOf(prefix)===0)return l.slice(prefix.length).trim()||null;}
        return null;
      }
      function parseRating(t){var m=/(\d+(?:[.,]\d+)?)/.exec(t);if(m){var v=parseFloat(m[1].replace(',','.'));return(v>=1&&v<=5)?v:null;}return null;}
      var ratingEl=document.querySelector('div.F7nice');
      var allText=document.documentElement.textContent||'';
      var priceM=/\$[\d–-]+(?:\s*per\s+person)?/.exec(allText);
      var descM=/(?:Cool|Hip|Trendy|Cozy|Popular|Vibrant|Classic|Modern|Casual)[^.]{10,200}\./.exec(allText);
      var catEl=document.querySelector('button.DkEaL');
      var reviewCount=null;
      var rEls=document.querySelectorAll('[aria-label]');
      for(var i=0;i<rEls.length;i++){var l=rEls[i].getAttribute('aria-label')||'';if(/reviews?/i.test(l)){var m=/([\d,]+)\s*reviews?/i.exec(l);if(m)reviewCount=parseInt(m[1].replace(/,/g,''),10);break;}}
      return{name:((document.querySelector('h1')||{}).textContent||'').trim(),
        category:catEl?catEl.textContent.trim():null,
        address:getAriaVal('Address: '),phone:getAriaVal('Phone: '),website:getAriaVal('Website: '),
        rating:parseRating(ratingEl?ratingEl.textContent:''),review_count:reviewCount,
        price_level:priceM?priceM[0]:null,description:descM?descM[0].trim():null,url:location.href};
    })())

    scrapeless-scraping-browser --session-id "$SID" close

## 6. Output shape

| Extractor | Returns |
| --- | --- |
| place list | array of Place summaries |
| place detail | single Place with all fields |

Full field tables are in [`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in
[`results/`](results/).
