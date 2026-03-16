"""
Job Board Scraper - Matt Kobzik
Scrapes Greenhouse, Lever, and Ashby job boards for target roles,
deduplicates, filters, scores with Claude, and writes to Notion.

Usage:
    python3 job_scraper_v3.py           # normal run — scrape + score new jobs
    python3 job_scraper_v3.py --test    # dry-run (no writes, no API calls)
    python3 job_scraper_v3.py --rescore # re-score all unscored Notion rows
"""

import os
import requests
import json
from datetime import datetime
import time
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Load .env file if present (pip install python-dotenv)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── CONFIG ─────────────────────────────────────────────────────────────────────

KEYWORDS = [
    "customer success manager",
    "customer success",
    "technical account manager",
    "technical customer success",
    "product expert",
    "strategic customer success",
    "enterprise customer success",
    "customer engineer",
    "partner success manager",
    "customer solutions engineer",
    "implementation manager",
    "onboarding manager",
    "solutions consultant",
    "value engineer",
]

SENIORITY_EXCLUDE = [
    "director", "vp ", "vice president", "head of", "principal",
    "associate", "coordinator", "intern", "junior", "entry level", "entry-level",
    "senior manager", "staff",
]

LOCATION_KEYWORDS = [
    "remote", "anywhere", "us remote", "work from home",
    "north america", "usa", "- us", "- usa", "remote, us",
]

GEO_EXCLUDE = [
    "latam", "latin america", "emea", "europe", "dach", "apj", "apac", "asia",
    "western europe", "eastern europe",
    "australia", "singapore", "india", "united kingdom", "canada",
    "germany", "france", "netherlands", "ireland", "sweden", "denmark",
    "norway", "finland", "spain", "italy", "poland", "israel",
    "japan", "korea", "china", "brazil", "mexico", "argentina",
    "new zealand", "philippines", "indonesia", "thailand", "vietnam",
    "colombia", "peru", "chile", "ukraine",
    "london", "dubai", "toronto", "ontario", "vancouver", "montreal",
    "remote - uk", "remote - eu", "remote - europe",
    "remote uk", "& ie", "uk &",
    ", amer", "- amer", "-amer",
]

TITLE_GEO_EXCLUDE = [
    "latam", "latin america", "emea", "apac", "apj", "dach",
    "canada", " uk", "colombia", "dubai", "middle east", "africa",
    "europe", "germany", "france", "australia", "india",
]

ONSITE_EXACT_BLOCK = [
    "new york, new york", "new york, ny", "new york city",
    "san francisco, california", "san francisco, ca", "san francisco",
    "seattle, washington", "seattle, wa",
    "austin, texas", "austin, tx",
    "chicago, illinois", "chicago, il",
    "boston, massachusetts", "boston, ma",
    "los angeles, california", "los angeles, ca",
    "denver, colorado", "denver, co",
    "atlanta, georgia", "atlanta, ga",
    "miami, florida", "miami, fl",
    "washington, dc", "washington, d.c.",
    "dallas, texas", "dallas, tx",
    "delhi", "mississauga",
]

# ── NOTION CONFIG ──────────────────────────────────────────────────────────────

NOTION_TOKEN   = os.environ.get("NOTION_TOKEN", "")
NOTION_DB_ID   = os.environ.get("NOTION_DB_ID", "")
NOTION_VERSION = "2022-06-28"

# ── CLAUDE CONFIG ──────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

CANDIDATE_PROFILE = """
Name: Matt Kobzik
Location: Burlington, VT (fully remote only)
Target roles: Customer Success Manager (CSM), Technical Account Manager (TAM), Product Expert, Solutions Engineer
Target companies: SaaS, data/analytics tooling, developer infrastructure, climate tech
Most recent role: Manager, Reporting & Analytics Services at Onit (legal SaaS) — led 5-person analytics team, ~$140K base
Background: 8+ years enterprise SaaS — CSM, analytics, BI, API integration consulting
Key strengths: Enterprise customer relationships, executive business reviews, data/analytics enablement, retention & expansion
Technical skills: SQL, Tableau, Salesforce, OData/API integration, platform analytics
What matters: Mission-aligned companies (open source, data tooling, climate), technical depth, mid-market to enterprise segment
Not interested in: Finance/fintech, legal tech, healthcare, highly quota-heavy SE roles
Ideal fit signals: Data/analytics product, developer tooling, post-sales technical advisory, CSM with data angle, Product Expert at a tool he'd actually use
"""

RESUME_TEXT = """
PROFESSIONAL SUMMARY
Customer Success leader with 8+ years driving adoption, retention, and expansion for enterprise SaaS platforms. Proven track record owning strategic books of business, delivering executive business reviews, and translating complex technical platforms into measurable business outcomes. Skilled at building trusted advisor relationships across technical and executive stakeholders including guiding customers through API integrations and analytics workflows.

EXPERIENCE

ONIT — Manager, Reporting & Analytics Services (April 2024 – February 2026)
- Led a team of 5 delivering analytics services to enterprise SaaS customers
- Delivered executive business reviews, translating usage insights into KPI improvements and renewal strategy
- Advised enterprise clients on OData API integration and data warehouse connectivity

ONIT — Customer Success Manager (September 2021 – March 2024)
- Managed 10–12 enterprise SaaS customers ($100k–$300k ARR)
- Drove 12+ renewals totaling $1M+ ARR, 25% of total brand revenue
- Surfaced ~$2M in cost savings via advanced data analysis for a key client
- Partnered with Product and Engineering to launch two analytics offerings
- Led launch of Tableau-based analytics platform using ML models
- Q2 2023 Managed Services MVP

NEWELL BRANDS — Product Manager (Jan 2020 – Aug 2021)
- Owned lifecycle of two internal analytics platforms
- Led BI platform implementation as technical SME

NEWELL BRANDS — Account Manager (Aug 2017 – Dec 2019)
- Managed eCommerce accounts (First Alert, Yankee Candle)

EDUCATION
UNH — BA History | Climatebase climate tech accelerator | Work on Climate volunteer | Burlington city board member
"""

# ── EMAIL CONFIG ───────────────────────────────────────────────────────────────
EMAIL_ENABLED      = False
EMAIL_FROM         = "you@gmail.com"
EMAIL_TO           = "you@gmail.com"
EMAIL_SUBJECT      = "Job Scraper — New Matches Today"
GMAIL_APP_PASSWORD = ""

# ── COMPANY LIST ───────────────────────────────────────────────────────────────

COMPANIES = [
    # ── Greenhouse ─────────────────────────────────────────────────────────────
    {"name": "Amplitude",           "ats": "greenhouse", "id": "amplitude"},
    {"name": "ClickHouse",          "ats": "greenhouse", "id": "clickhouse"},
    {"name": "dbt Labs",            "ats": "greenhouse", "id": "dbtlabsinc"},
    {"name": "Hightouch",           "ats": "greenhouse", "id": "hightouch"},
    {"name": "PitchBook",           "ats": "greenhouse", "id": "pitchbookdata"},
    {"name": "PlanetScale",         "ats": "greenhouse", "id": "planetscale"},
    {"name": "Recorded Future",     "ats": "greenhouse", "id": "recordedfuture"},
    {"name": "Remote",              "ats": "greenhouse", "id": "remotecom"},
    {"name": "Sigma Computing",     "ats": "greenhouse", "id": "sigmacomputing",  "applied": True},
    {"name": "SingleStore",         "ats": "greenhouse", "id": "singlestore"},
    {"name": "Starburst Data",      "ats": "greenhouse", "id": "starburst"},
    {"name": "Temporal",            "ats": "greenhouse", "id": "temporaltechnologies"},
    {"name": "Yugabyte",            "ats": "greenhouse", "id": "yugabyte"},
    {"name": "Arize AI",            "ats": "greenhouse", "id": "arizeai"},
    {"name": "Dagster Labs",        "ats": "greenhouse", "id": "dagsterlabs"},
    {"name": "Materialize",         "ats": "greenhouse", "id": "materialize"},
    {"name": "Triple Whale",        "ats": "greenhouse", "id": "triplewhale"},
    {"name": "Fivetran",            "ats": "greenhouse", "id": "fivetran"},
    {"name": "Databricks",          "ats": "greenhouse", "id": "databricks"},
    {"name": "Imply",               "ats": "greenhouse", "id": "imply"},
    {"name": "Brex",                "ats": "greenhouse", "id": "brex"},
    {"name": "Scale AI",            "ats": "greenhouse", "id": "scaleai"},
    {"name": "DataGrail",           "ats": "greenhouse", "id": "datagrail",       "applied": True},
    {"name": "Hex",                 "ats": "greenhouse", "id": "hextechnologies", "applied": True},
    {"name": "Glean",               "ats": "greenhouse", "id": "gleanwork"},
    {"name": "TigerData",           "ats": "greenhouse", "id": "timescale"},
    {"name": "Mixpanel",            "ats": "greenhouse", "id": "mixpanel"},
    {"name": "LaunchDarkly",        "ats": "greenhouse", "id": "launchdarkly"},
    {"name": "Grafana Labs",        "ats": "greenhouse", "id": "grafanalabs"},
    {"name": "Honeycomb",           "ats": "greenhouse", "id": "honeycomb"},
    {"name": "Redpanda",            "ats": "greenhouse", "id": "redpandadata"},
    {"name": "GitLab",              "ats": "greenhouse", "id": "gitlab"},
    {"name": "Figma",               "ats": "greenhouse", "id": "figma"},
    {"name": "Retool",              "ats": "greenhouse", "id": "retool"},
    {"name": "Weights & Biases",    "ats": "greenhouse", "id": "wandb"},
    {"name": "Hugging Face",        "ats": "greenhouse", "id": "huggingface"},
    {"name": "Help Scout",          "ats": "greenhouse", "id": "helpscout"},
    {"name": "Descript",            "ats": "greenhouse", "id": "descript"},
    # ── Lever ──────────────────────────────────────────────────────────────────
    {"name": "Articulate",          "ats": "lever",      "id": "articulate"},
    {"name": "Canary Technologies", "ats": "lever",      "id": "canarytechnologies"},
    {"name": "Clarify Health",      "ats": "lever",      "id": "clarifyhealth"},
    {"name": "GoHighLevel",         "ats": "lever",      "id": "gohighlevel"},
    {"name": "HappyCo",             "ats": "lever",      "id": "happyco"},
    {"name": "Highspot",            "ats": "lever",      "id": "highspot"},
    {"name": "Hive",                "ats": "lever",      "id": "hive"},
    {"name": "Kiddom",              "ats": "lever",      "id": "kiddom"},
    {"name": "Metabase",            "ats": "lever",      "id": "metabase"},
    {"name": "Promenade",           "ats": "lever",      "id": "promenade"},
    {"name": "Regal Voice",         "ats": "lever",      "id": "regalvoice"},
    {"name": "Restaurant365",       "ats": "lever",      "id": "restaurant365"},
    {"name": "Tinybird",            "ats": "lever",      "id": "tinybird"},
    {"name": "Datafold",            "ats": "lever",      "id": "datafold"},
    # ── Ashby ──────────────────────────────────────────────────────────────────
    {"name": "Statsig",             "ats": "ashby",      "id": "statsig"},
    {"name": "Monte Carlo Data",    "ats": "ashby",      "id": "montecarlodata"},
    {"name": "Sift",                "ats": "ashby",      "id": "sift"},
    {"name": "Anomalo",             "ats": "ashby",      "id": "anomalo"},
    {"name": "Astronomer",          "ats": "ashby",      "id": "astronomer"},
    {"name": "Atlan",               "ats": "ashby",      "id": "atlan"},
    {"name": "Cube",                "ats": "ashby",      "id": "cube"},
    {"name": "Lightdash",           "ats": "ashby",      "id": "lightdash"},
    {"name": "Outerbounds",         "ats": "ashby",      "id": "outerbounds"},
    {"name": "PostHog",             "ats": "ashby",      "id": "posthog"},
    {"name": "Prefect",             "ats": "ashby",      "id": "prefect"},
    {"name": "Secoda",              "ats": "ashby",      "id": "Secoda"},
    {"name": "Supabase",            "ats": "ashby",      "id": "supabase"},
    {"name": "Omni Analytics",      "ats": "ashby",      "id": "omni",            "applied": True},
    {"name": "Hightouch",           "ats": "ashby",      "id": "Hightouch",       "applied": True},
    {"name": "Stellic",             "ats": "ashby",      "id": "stellic",         "applied": True},
    {"name": "Vultr",               "ats": "ashby",      "id": "vultr"},
    {"name": "Airbyte",             "ats": "ashby",      "id": "airbyte"},
    {"name": "Confluent",           "ats": "ashby",      "id": "confluent"},
    {"name": "Snowflake",           "ats": "ashby",      "id": "snowflake"},
    {"name": "MotherDuck",          "ats": "ashby",      "id": "MotherDuck"},
    {"name": "Tecton",              "ats": "ashby",      "id": "tectonai"},
    {"name": "Notion",              "ats": "ashby",      "id": "notion"},
    {"name": "Linear",              "ats": "ashby",      "id": "linear"},
    {"name": "Cohere",              "ats": "ashby",      "id": "cohere"},
    {"name": "Neon",                "ats": "ashby",      "id": "Neon"},
    {"name": "Zapier",              "ats": "ashby",      "id": "zapier"},
    {"name": "Vercel",              "ats": "ashby",      "id": "vercel"},
]

# ── FETCHERS ───────────────────────────────────────────────────────────────────

def fetch_greenhouse(company_id):
    url = f"https://boards-api.greenhouse.io/v1/boards/{company_id}/jobs?content=true"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.json().get("jobs", [])
    except requests.exceptions.HTTPError as e:
        print(f"  [Greenhouse] HTTP {e.response.status_code} for {company_id}")
        return []
    except Exception as e:
        print(f"  [Greenhouse] Error: {e}")
        return []

def fetch_lever(company_id):
    url = f"https://api.lever.co/v0/postings/{company_id}?mode=json"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    except requests.exceptions.HTTPError as e:
        print(f"  [Lever] HTTP {e.response.status_code} for {company_id}")
        return []
    except Exception as e:
        print(f"  [Lever] Error: {e}")
        return []

def fetch_ashby(company_id):
    url = f"https://api.ashbyhq.com/posting-api/job-board/{company_id}?includeCompensation=true"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.json().get("jobs", [])
    except requests.exceptions.HTTPError as e:
        print(f"  [Ashby] HTTP {e.response.status_code} for {company_id}")
        return []
    except Exception as e:
        print(f"  [Ashby] Error: {e}")
        return []

# ── FILTERS ────────────────────────────────────────────────────────────────────

def matches_title(title):
    t = title.lower()
    return any(kw in t for kw in KEYWORDS)

def matches_seniority(title):
    t = title.lower()
    return not any(ex in t for ex in SENIORITY_EXCLUDE)

def matches_location(location, title=""):
    if title:
        t = title.lower()
        if any(geo in t for geo in TITLE_GEO_EXCLUDE):
            return False
    if not location:
        return True
    loc = location.lower()
    if any(sig in loc for sig in ONSITE_EXACT_BLOCK):
        return False
    if any(geo in loc for geo in GEO_EXCLUDE):
        return False
    if loc.strip() in ("united states", "us", "usa"):
        return True
    return any(kw in loc for kw in LOCATION_KEYWORDS)

# ── PARSERS ────────────────────────────────────────────────────────────────────

def parse_greenhouse_job(job, company_name):
    title    = job.get("title", "")
    loc_obj  = job.get("location") or {}
    location = loc_obj.get("name", "") if isinstance(loc_obj, dict) else ""
    url      = job.get("absolute_url", "")
    job_id   = str(job.get("id", ""))
    updated  = job.get("updated_at", "")
    metadata = job.get("metadata") or []
    meta_str = "; ".join(
        f"{m.get('name','')}: {m.get('value','')}"
        for m in metadata
        if m.get("value") not in (None, "", [])
    ) if metadata else ""
    content  = job.get("content", "") or ""
    return {
        "id": f"gh_{job_id}", "company": company_name, "title": title,
        "location": location, "url": url, "source": "Greenhouse",
        "date_found": datetime.today().strftime("%Y-%m-%d"),
        "updated_at": updated[:10] if updated else "",
        "salary": "", "metadata": meta_str, "description": content,
    }

def parse_lever_job(job, company_name):
    title      = job.get("text", "")
    categories = job.get("categories") or {}
    location   = categories.get("location", "") or job.get("workplaceType", "") or ""
    url        = job.get("hostedUrl", "")
    job_id     = job.get("id", "")
    created_at = job.get("createdAt", 0)
    updated_at = ""
    if created_at:
        try:
            updated_at = datetime.fromtimestamp(created_at / 1000).strftime("%Y-%m-%d")
        except Exception:
            pass
    salary = ""
    sr = job.get("salaryRange") or {}
    if sr.get("min") and sr.get("max"):
        salary = f"${sr['min']:,.0f}–${sr['max']:,.0f} {sr.get('currency', 'USD')}"
    lists = job.get("lists") or []
    description = "\n".join(item.get("content", "") for item in lists)
    return {
        "id": f"lv_{job_id}", "company": company_name, "title": title,
        "location": location, "url": url, "source": "Lever",
        "date_found": datetime.today().strftime("%Y-%m-%d"),
        "updated_at": updated_at, "salary": salary, "metadata": "",
        "description": description,
    }

def parse_ashby_job(job, company_name):
    title    = job.get("title", "")
    location = job.get("location", "") or ""
    if not location:
        if job.get("isRemote"):
            location = "Remote"
        else:
            addr   = job.get("address") or {}
            postal = addr.get("postalAddress") or {}
            parts  = [postal.get("addressLocality",""), postal.get("addressRegion",""), postal.get("addressCountry","")]
            location = ", ".join(p for p in parts if p)
    url        = job.get("jobUrl", "") or job.get("applyUrl", "")
    job_id     = job.get("id", "") or job.get("jobUrl", "")
    updated_at = job.get("publishedAt", "")[:10] if job.get("publishedAt") else ""
    comp       = job.get("compensation") or {}
    salary     = comp.get("compensationTierSummary", "") or comp.get("scrapeableCompensationSalarySummary", "")
    description = job.get("descriptionHtml", "") or job.get("description", "") or ""
    return {
        "id": f"ab_{job_id}", "company": company_name, "title": title,
        "location": location, "url": url, "source": "Ashby",
        "date_found": datetime.today().strftime("%Y-%m-%d"),
        "updated_at": updated_at, "salary": salary, "metadata": "",
        "description": description,
    }

# ── FIT SCORING ────────────────────────────────────────────────────────────────

def score_job(job):
    if not ANTHROPIC_API_KEY:
        return None, None
    desc = (job.get("description") or "")[:3000].strip() or "(No description available)"
    prompt = f"""You are helping Matt Kobzik evaluate job fit during his active job search.

CANDIDATE PROFILE:
{CANDIDATE_PROFILE}

RESUME SUMMARY:
{RESUME_TEXT}

JOB TO EVALUATE:
Company: {job['company']}
Title: {job['title']}
Location: {job.get('location','')}
Salary: {job.get('salary') or 'Not listed'}
Description:
{desc}

Score this job's fit on a scale of 1-5 where:
- 5 — excellent match: right role type, right company type, strong technical/data angle, would genuinely excite Matt
- 4 — solid match: good role and company fit, minor gaps or unknowns
- 3 — plausible but meaningful concerns: wrong sector, quota-heavy, too junior/senior, or unclear fit
- 2 — weak fit: significant misalignment on role type, sector, or seniority
- 1 — poor fit: wrong role entirely, excluded sector (fintech, legal, healthcare), or highly quota-driven SE

Be critical and discriminating. Reserve 5s for genuinely strong matches. Most jobs should score 2-4.
Then write 2-3 sentences of honest analysis. Be direct — mention what aligns AND what gives pause.

Respond ONLY in this JSON format (no markdown, no extra text):
{{"score": <integer 1-5>, "notes": "<2-3 sentence analysis>"}}"""

    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 300,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        r.raise_for_status()
        raw = r.json()["content"][0]["text"].strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data  = json.loads(raw)
        score = data.get("score")
        notes = data.get("notes", "").strip()
        try:
            score = int(score)
            if score not in [1, 2, 3, 4, 5]:
                score = 3
        except (ValueError, TypeError):
            score = 3
        return score, notes
    except Exception as e:
        print(f"  [Claude] Scoring error: {e}")
        return None, None

# ── NOTION API ─────────────────────────────────────────────────────────────────

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": NOTION_VERSION,
}

def get_existing_notion_ids():
    ids = set()
    url = f"https://api.notion.com/v1/databases/{NOTION_DB_ID}/query"
    payload = {"page_size": 100}
    while True:
        r = requests.post(url, headers=NOTION_HEADERS, json=payload, timeout=15)
        r.raise_for_status()
        data = r.json()
        for page in data.get("results", []):
            rich = page.get("properties", {}).get("ID", {}).get("rich_text", [])
            if rich:
                ids.add(rich[0].get("plain_text", ""))
        if not data.get("has_more"):
            break
        payload["start_cursor"] = data["next_cursor"]
    return ids

def get_unscored_notion_pages():
    pages = []
    url = f"https://api.notion.com/v1/databases/{NOTION_DB_ID}/query"
    payload = {
        "page_size": 100,
        "filter": {"property": "Fit Score", "number": {"is_empty": True}}
    }
    while True:
        r = requests.post(url, headers=NOTION_HEADERS, json=payload, timeout=15)
        r.raise_for_status()
        data = r.json()
        pages.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        payload["start_cursor"] = data["next_cursor"]
    return pages

def notion_page_to_job(page):
    props = page.get("properties", {})
    def get_text(key):
        p = props.get(key, {})
        rich = p.get("rich_text", []) or p.get("title", [])
        return rich[0]["plain_text"] if rich else ""
    return {
        "notion_page_id": page["id"],
        "id":             get_text("ID"),
        "company":        get_text("Company"),
        "title":          get_text("Title"),
        "location":       get_text("Location"),
        "url":            props.get("URL", {}).get("url", "") or "",
        "salary":         get_text("Salary"),
        "description":    "",
    }

def add_to_notion(job, score=None, score_notes=None):
    def rich(text):
        return [{"type": "text", "text": {"content": str(text)[:2000]}}]

    properties = {
        "Title":      {"title": rich(job["title"])},
        "ID":         {"rich_text": rich(job["id"])},
        "Company":    {"rich_text": rich(job["company"])},
        "Location":   {"rich_text": rich(job["location"])},
        "URL":        {"url": job["url"] or None},
        "Source":     {"select": {"name": job["source"]}},
        "Date Added": {"date": {"start": job["date_found"]}},
        "Status":     {"select": {"name": "New"}},
        "Salary":     {"rich_text": rich(job.get("salary", ""))},
        "Metadata":   {"rich_text": rich(job.get("metadata", ""))},
    }
    if score is not None:
        properties["Fit Score"]     = {"number": score}
        properties["Fit Scored At"] = {"date": {"start": datetime.today().strftime("%Y-%m-%d")}}
    if score_notes:
        properties["Fit Notes"] = {"rich_text": rich(score_notes)}

    r = requests.post(
        "https://api.notion.com/v1/pages",
        headers=NOTION_HEADERS,
        json={"parent": {"database_id": NOTION_DB_ID}, "properties": properties},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()

def update_notion_score(page_id, score, notes):
    def rich(text):
        return [{"type": "text", "text": {"content": str(text)[:2000]}}]
    payload = {
        "properties": {
            "Fit Score":     {"number": score},
            "Fit Notes":     {"rich_text": rich(notes)},
            "Fit Scored At": {"date": {"start": datetime.today().strftime("%Y-%m-%d")}},
        }
    }
    r = requests.patch(f"https://api.notion.com/v1/pages/{page_id}", headers=NOTION_HEADERS, json=payload, timeout=15)
    r.raise_for_status()

# ── EMAIL DIGEST ───────────────────────────────────────────────────────────────

def send_email_digest(new_jobs):
    if not EMAIL_ENABLED or not new_jobs:
        return
    lines = [f"Job Scraper found {len(new_jobs)} new match(es):\n"]
    for j in new_jobs:
        lines.append(f"  • {j['company']} — {j['title']} | {j['location']}")
        if j.get("fit_score") is not None:
            lines.append(f"    Fit: {j['fit_score']}/5")
        if j.get("fit_notes"):
            lines.append(f"    {j['fit_notes']}")
        lines.append(f"    {j['url']}\n")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = EMAIL_SUBJECT
    msg["From"]    = EMAIL_FROM
    msg["To"]      = EMAIL_TO
    msg.attach(MIMEText("\n".join(lines), "plain"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_FROM, GMAIL_APP_PASSWORD)
            server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        print(f"✉  Email sent to {EMAIL_TO}")
    except Exception as e:
        print(f"  [Email] Failed: {e}")

# ── RESCORE MODE ───────────────────────────────────────────────────────────────

def rescore_unscored():
    if not ANTHROPIC_API_KEY:
        print("ERROR: Set ANTHROPIC_API_KEY before running --rescore.")
        return
    print(f"\n{'='*60}")
    print(f"Rescore Run — {datetime.today().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")
    print("Fetching unscored rows from Notion...")
    pages = get_unscored_notion_pages()
    print(f"Found {len(pages)} unscored rows.\n")
    if not pages:
        print("Nothing to score.")
        return
    scored = 0
    for page in pages:
        job = notion_page_to_job(page)
        print(f"Scoring: {job['company']} — {job['title']}...")
        score, notes = score_job(job)
        if score is not None:
            update_notion_score(job["notion_page_id"], score, notes)
            print(f"  → {score}/5")
            scored += 1
        else:
            print(f"  → (scoring failed)")
        time.sleep(0.5)
    print(f"\nDone. Scored {scored}/{len(pages)} rows.")

# ── MAIN ───────────────────────────────────────────────────────────────────────

def run(dry_run=False):
    if dry_run:
        print("\n⚠️  DRY-RUN MODE — nothing will be written\n")

    print(f"\n{'='*60}")
    print(f"Job Scraper Run — {datetime.today().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")

    existing_ids = set()
    if not dry_run:
        print("Fetching existing job IDs from Notion...")
        try:
            existing_ids = get_existing_notion_ids()
            print(f"Found {len(existing_ids)} existing job IDs.\n")
        except Exception as e:
            print(f"ERROR connecting to Notion: {e}")
            print("Check NOTION_TOKEN and NOTION_DB_ID, and confirm the integration is connected to the database.")
            sys.exit(1)
    else:
        print("(Skipping Notion connection)\n")

    scoring_enabled = bool(ANTHROPIC_API_KEY) and not dry_run
    if not scoring_enabled and not dry_run:
        print("⚠️  ANTHROPIC_API_KEY not set — jobs will be added without fit scores.\n")

    new_jobs = []
    errors   = []

    for company in COMPANIES:
        name    = company["name"]
        ats     = company["ats"]
        cid     = company["id"]
        applied = company.get("applied", False)
        print(f"Fetching {name} ({ats}){'  [applied]' if applied else ''}...")

        if ats == "greenhouse":
            raw    = fetch_greenhouse(cid)
            parsed = [parse_greenhouse_job(j, name) for j in raw]
        elif ats == "lever":
            raw    = fetch_lever(cid)
            parsed = [parse_lever_job(j, name) for j in raw]
        elif ats == "ashby":
            raw    = fetch_ashby(cid)
            parsed = [parse_ashby_job(j, name) for j in raw]
        else:
            continue

        if not raw:
            errors.append(f"{name} ({ats}:{cid})")

        matched = 0
        for job in parsed:
            if job["id"] in existing_ids:
                continue
            if not matches_title(job["title"]):
                continue
            if not matches_seniority(job["title"]):
                continue
            if not matches_location(job["location"], job.get("title", "")):
                continue
            if applied:
                existing = job.get("metadata", "")
                job["metadata"] = ("applied; " + existing).strip("; ") if existing else "applied"
            new_jobs.append(job)
            matched += 1
            salary_note = f" | {job['salary']}" if job.get("salary") else ""
            print(f"  ✓ {job['title']} — {job['location']}{salary_note}")

        if matched == 0 and raw:
            print(f"  (no new matches from {len(raw)} postings)")

        time.sleep(0.4)

    print(f"\n{'─'*60}")
    print(f"New jobs found: {len(new_jobs)}")

    if errors:
        print(f"\nCompanies with fetch errors:")
        for e in errors:
            print(f"  • {e}")

    if new_jobs and not dry_run:
        print(f"\nWriting to Notion{' + scoring with Claude' if scoring_enabled else ''}...\n")
        written = 0
        for job in new_jobs:
            score, notes = None, None
            if scoring_enabled:
                print(f"  Scoring: {job['company']} — {job['title']}...")
                score, notes = score_job(job)
                if score is not None:
                    print(f"    → {score}/5")
                job["fit_score"] = score
                job["fit_notes"] = notes
                time.sleep(0.3)
            try:
                add_to_notion(job, score=score, score_notes=notes)
                written += 1
            except Exception as e:
                print(f"  [Notion] Failed to write {job['id']}: {e}")
        print(f"\nDone. {written}/{len(new_jobs)} jobs written to Notion.")
        send_email_digest(new_jobs)
    elif new_jobs and dry_run:
        print("\nDry-run — would have written:")
        for j in new_jobs:
            print(f"  {j['company']:28s}  {j['title']:45s}  {j['location']}")
    else:
        print("No new jobs to add.")

def preview_rescore(limit=None):
    """Score unscored Notion rows and print results to terminal. No writes."""
    if not ANTHROPIC_API_KEY:
        print("ERROR: Set ANTHROPIC_API_KEY before running --preview-rescore.")
        return
    print(f"\n{'='*60}")
    print(f"Preview Rescore — {datetime.today().strftime('%Y-%m-%d %H:%M')}")
    print(f"(terminal only — nothing will be written to Notion)")
    print(f"{'='*60}\n")
    print("Fetching unscored rows from Notion...")
    pages = get_unscored_notion_pages()
    if limit:
        pages = pages[:limit]
    print(f"Scoring {len(pages)} rows...\n")
    if not pages:
        print("Nothing to score.")
        return

    results = []
    for page in pages:
        job = notion_page_to_job(page)
        print(f"  Scoring: {job['company']} — {job['title']}...")
        score, notes = score_job(job)
        if score is not None:
            results.append((score, job['company'], job['title'], notes))
            print(f"    → {score}/5  {notes}")
        else:
            print(f"    → (scoring failed)")
        time.sleep(0.5)

    # Print sorted summary
    results.sort(key=lambda x: x[0], reverse=True)
    print(f"\n{'─'*60}")
    print(f"RESULTS SORTED BY SCORE ({len(results)} jobs)\n")
    for score, company, title, notes in results:
        print(f"  [{score}/5]  {company} — {title}")
        print(f"         {notes}\n")


if __name__ == "__main__":
    if "--rescore" in sys.argv:
        rescore_unscored()
    elif "--preview-rescore" in sys.argv:
        # Optional: pass --limit N to score only N jobs (e.g. --limit 10)
        limit = None
        if "--limit" in sys.argv:
            try:
                limit = int(sys.argv[sys.argv.index("--limit") + 1])
            except (IndexError, ValueError):
                pass
        preview_rescore(limit=limit)
    else:
        dry_run = "--test" in sys.argv
        run(dry_run=dry_run)
