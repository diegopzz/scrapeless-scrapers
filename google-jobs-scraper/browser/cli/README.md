# Google Jobs — CLI surface

Scrape Google Jobs listings from the command line using the
[`scrapeless-scraping-browser`](https://www.npmjs.com/package/scrapeless-scraping-browser) CLI.

## 1. Install

    npm install -g scrapeless-scraping-browser

## 2. Set your API key

    export SCRAPELESS_API_KEY=sk_...

## 3. Open a session and navigate

    scrapeless-scraping-browser new-session --name gjobs-cli --ttl 300 --proxy-country US --json
    SID=<taskId>

    scrapeless-scraping-browser --session-id "$SID" open "https://www.google.com/search?q=software+engineer+jobs+austin+tx&gl=us&hl=en"
    scrapeless-scraping-browser --session-id "$SID" wait 8000

Note: use `wait` (milliseconds) instead of `wait "selector"` here, since the Jobs panel renders
via JavaScript after page load.

## 4. Run the in-page extractor

The extractor parses the Jobs panel card text from "Job postings" to the "more jobs" sentinel:

    scrapeless-scraping-browser --session-id "$SID" eval "
    JSON.stringify((function(){
      var TIME_RE=/^\d+\s+(?:second|minute|hour|day|week|month)s?\s+ago$/i;
      var SALARY_RE=/^\$[\d,]+|^\d+[–-]\d+\s+an?\s+(?:hour|year)/i;
      var LOC_VIA_RE=/^.+,\s+[A-Z]{2}\s+•\s+via\s+/;
      var JOB_TYPE_RE=/^(?:Full-time|Part-time|Contractor|Internship|Temporary)/i;
      var SKIP=new Set(['Saved jobs','Following','Feedback','Learn more','Follow','Search Results']);
      var lines=[];
      document.body.querySelectorAll('*').forEach(function(el){
        el.childNodes.forEach(function(n){if(n.nodeType===3&&n.textContent.trim())lines.push(n.textContent.trim());});
      });
      var results=[];var inJobs=false;var i=0;
      while(i<lines.length){
        var line=lines[i];
        if(line==='Job postings'){inJobs=true;i++;continue;}
        if(!inJobs){i++;continue;}
        if(line==='More jobs'||line==='Web results'||/\d+\+?\s+more jobs/.test(line))break;
        if(SKIP.has(line)||TIME_RE.test(line)||SALARY_RE.test(line)||JOB_TYPE_RE.test(line)){i++;continue;}
        if(line.length>5&&!LOC_VIA_RE.test(line)&&!line.startsWith('No degree')){
          var title=line,company='',location='',source='',postedAt='',salary='',jobType='';
          var j=i+1;
          while(j<lines.length&&j<i+10){
            var nxt=lines[j];
            if(TIME_RE.test(nxt)){postedAt=nxt;j++;continue;}
            if(SALARY_RE.test(nxt)){salary=nxt;j++;continue;}
            if(JOB_TYPE_RE.test(nxt)){jobType=nxt;j++;continue;}
            if(nxt.startsWith('No degree')){j++;continue;}
            if(LOC_VIA_RE.test(nxt)){var pts=nxt.split(' • via ');location=pts[0].trim();source=pts[1]?pts[1].trim():'';j++;continue;}
            if(!company&&nxt&&nxt!==title&&!SKIP.has(nxt)){company=nxt;j++;continue;}
            break;
          }
          if(company&&(postedAt||location)){results.push({title:title,company:company,location:location||null,source:source||null,posted_at:postedAt||null,salary:salary||null,job_type:jobType||null,url:null});i=j;continue;}
        }
        i++;
      }
      return results;
    })())
    " --json

    scrapeless-scraping-browser --session-id "$SID" close

## 5. Output shape

`data.result` is an array of `JobListing` objects. Full field tables are in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in [`results/`](results/).
