# Job Scraper

A Python job scraper built during an active job search. Scrapes Greenhouse, Lever, and Ashby ATS APIs across a curated list of target companies — plus Remotive and Jobicy remote job boards — filters results by role type, seniority, and location, scores each match using the Anthropic API, and writes new jobs to a Notion database daily.

Built and iterated with help from Claude. Not written by an engineer — written by a CSM who identified a problem and figured out the tools to solve it.

---

## What it does

- Scrapes job listings from **80+ target companies** across Greenhouse, Lever, and Ashby ATS platforms
- Also pulls from **Remotive** and **Jobicy** remote-only job boards for broader coverage
- Filters by **title keywords** (CSM, TAM, Product Expert, Customer Engineer, etc.)
- Filters out senior/director-level roles and non-US/non-remote locations
- **Deduplicates** against existing Notion rows so you only see new jobs
- **Scores each job 1–5** using Claude Haiku based on a candidate profile and resume summary
- Writes results to a **Notion database** with score, notes, salary, source, and status
- Supports multiple run modes for testing and reviewing scores before committing to Notion

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/Matt-Kobzik/job-scraper.git
cd job-scraper
```

### 2. Install dependencies

```bash
pip3 install requests python-dotenv
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your values:

```
ANTHROPIC_API_KEY=your_anthropic_api_key
NOTION_TOKEN=your_notion_integration_token
NOTION_DB_ID=your_notion_database_id
```

- **Anthropic API key**: [console.anthropic.com](https://console.anthropic.com)
- **Notion token**: [notion.so/profile/integrations](https://www.notion.so/profile/integrations) — create an internal integration
- **Notion DB ID**: found in your database's URL

### 4. Set up Notion

Create a Notion database with these properties:

| Property | Type |
|----------|------|
| Title | Title |
| ID | Text |
| Company | Text |
| Location | Text |
| URL | URL |
| Source | Select |
| Date Added | Date |
| Status | Select |
| Salary | Text |
| Metadata | Text |
| Fit Score | Number |
| Fit Notes | Text |
| Fit Scored At | Date |

Connect your Notion integration to the database via **··· → Connections**.

---

## Usage

```bash
# Normal run — scrape, score, and write new jobs to Notion
python3 job_scraper.py

# Dry run — scrape only, print matches to terminal, no writes or API calls
python3 job_scraper.py --test

# Preview scrape — scrape + score + print sorted results to terminal, no Notion writes
# Use this to validate quality before committing to Notion
python3 job_scraper.py --preview-scrape

# Preview scrape with a limit (cheaper for spot-checking scoring quality)
python3 job_scraper.py --preview-scrape --limit 10

# Preview rescore — score existing unscored Notion rows and print to terminal, no writes
python3 job_scraper.py --preview-rescore

# Preview rescore with a limit
python3 job_scraper.py --preview-rescore --limit 10

# Rescore — score all unscored Notion rows and write scores to Notion
python3 job_scraper.py --rescore
```

---

## Customization

### Target companies
Edit the `COMPANIES` list in `job_scraper.py`. Each entry needs a `name`, `ats` (greenhouse/lever/ashby), and `id` (the slug used in the ATS job board URL).

To find a company's ATS slug, look at their careers page URL:
- Greenhouse: `boards.greenhouse.io/{slug}`
- Lever: `jobs.lever.co/{slug}`
- Ashby: `jobs.ashbyhq.com/{slug}`

### Role keywords
Edit `KEYWORDS` to add or remove job title filters.

### Candidate profile
Edit `CANDIDATE_PROFILE` and `RESUME_TEXT` to match your own background. This is passed to Claude for fit scoring.

---

## Cost

Running daily costs roughly **$1–3/month** using Claude Haiku (~$0.001/job scored). The scraper only scores *new* jobs on each run, so after the initial backlog is cleared, daily costs are minimal.

---

## Project structure

```
job-scraper/
├── job_scraper.py     # Main script
├── .env.example       # Environment variable template
├── .gitignore
└── README.md
```

---

## Background

Built this because manually checking job boards every day is slow and noisy. By targeting specific companies I actually want to work at and scoring results against my background automatically, I can triage a daily feed in under 5 minutes instead of an hour.

The Notion integration gives me a structured, sortable database I can filter by fit score, company, and status — and link to a separate Job Tracker for active applications.
