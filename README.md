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

## Is this for you? (Read this first)

You do **not** need to be an engineer, but you'll be copying commands into a terminal and editing a Python file in a text editor. Plan on **45–90 minutes** the first time. If you get stuck, paste the error message into Claude or ChatGPT along with the step you were on — most problems below are common and quick to fix.

> **Important:** this repo is configured with the original author's resume, job preferences, and location filters. It will score jobs against *his* background until you replace them. See [Make it yours](#make-it-yours-do-this-before-your-first-real-run).

---

## Before you start

You'll need:

| Thing | Notes |
|-------|-------|
| **Python 3.8 or newer** | Check by running `python3 --version` (Mac/Linux) or `python --version` (Windows) in a terminal. If it isn't installed, get it from [python.org/downloads](https://www.python.org/downloads/). On Windows, tick **"Add Python to PATH"** in the installer. |
| **A terminal** | Mac: open **Terminal** (Cmd+Space, type "Terminal"). Windows: open **PowerShell** (Start menu, type "PowerShell"). |
| **A text editor** | Anything works (VS Code, Notepad, TextEdit in plain-text mode). Don't use Word or Pages. |
| **An Anthropic API account** | Separate from a Claude.ai subscription. You'll need to add a few dollars of credit at [console.anthropic.com](https://console.anthropic.com). |
| **A Notion account** | The free plan works. |

On Windows, use `python` wherever this guide says `python3`, and `pip` wherever it says `pip3`.

---

## Setup

### 1. Get the code

**Option A — no Git needed:** on the GitHub page for this repo, click **Code → Download ZIP**, unzip it, then in your terminal move into the folder:

```bash
cd path/to/job-scraper
```

(Tip: type `cd ` then drag the unzipped folder into the terminal window to fill in the path.)

**Option B — with Git:**

```bash
git clone https://github.com/Matt-Kobzik/job-scraper.git
cd job-scraper
```

### 2. Install dependencies

```bash
pip3 install -r requirements.txt
```

(Equivalent to `pip3 install requests python-dotenv`.) If you see `command not found: pip3`, try `python3 -m pip install -r requirements.txt`.

### 3. Create your `.env` file (your secret keys)

Make a copy of `.env.example` named exactly `.env` (with the leading dot, no `.txt` on the end):

```bash
# Mac / Linux
cp .env.example .env

# Windows PowerShell
copy .env.example .env
```

Files starting with a dot are hidden by default, so you may not see it in Finder/Explorer. Open it from the terminal instead:

```bash
# Mac
open -e .env

# Windows
notepad .env
```

Fill in your three values. **No quotes, no spaces around the `=`:**

```
ANTHROPIC_API_KEY=sk-ant-...
NOTION_TOKEN=ntn_...
NOTION_DB_ID=0123456789abcdef0123456789abcdef
```

Where to get each one:

- **Anthropic API key** — [console.anthropic.com](https://console.anthropic.com) → **API Keys** → **Create Key**. Copy it immediately; you can't view it again. Add credit under **Billing** or scoring will fail.
- **Notion token** — [notion.so/profile/integrations](https://www.notion.so/profile/integrations) → **New integration** → type **Internal** → create it, then copy the **Internal Integration Secret**.
- **Notion database ID** — finish step 4 first, then see "Finding your database ID" below.

Never share your `.env` file or post these keys anywhere. (`.env` is already excluded from Git so it won't be uploaded by accident.)

### 4. Set up Notion

Create a new **full-page database** in Notion (type `/database` and choose **Table view – full page**), then set up these properties. **Names must match exactly, including capitalization and spaces**, and the types must match too.

| Property | Notion type | Notes |
|----------|-------------|-------|
| Title | Title | Every database already has this column — leave it as is |
| ID | **Text** | Used to detect duplicates |
| Company | Text | |
| Location | Text | |
| URL | URL | |
| Source | Select | You don't need to add options; the script creates them |
| Date Added | Date | |
| Status | Select | New rows are created with the value "New" |
| Salary | Text | |
| Metadata | Text | |
| Fit Score | **Number** | |
| Fit Notes | Text | |
| Fit Scored At | Date | |

Then **connect your integration to the database**: open the database page, click **··· (top right) → Connections**, and add the integration you created. Skipping this is the most common cause of errors.

**Finding your database ID:** open the database as a full page and copy its link (**Share → Copy link**, or from the browser address bar). It looks like:

```
https://www.notion.so/yourworkspace/0123456789abcdef0123456789abcdef?v=...
```

The database ID is the 32-character string of letters and numbers between the last `/` and the `?v=`.

### 5. Make it yours (do this before your first real run)

Open `job_scraper.py` in your text editor. Everything you need to change is in the block at the top, under the `# ── CONFIG ──` headings. Search for the names in capitals below.

| Name in the file | What it does | What to do |
|------------------|--------------|------------|
| `CANDIDATE_PROFILE` | Tells Claude who you are and what you want | **Rewrite completely** — target roles, location, industries, deal-breakers |
| `RESUME_TEXT` | Your background, used for scoring | **Replace with your own** resume summary |
| `KEYWORDS` | Job titles worth keeping | Add or remove titles for your target roles |
| `SENIORITY_EXCLUDE` | Titles containing these words are dropped | Adjust to your level (e.g. remove `"senior manager"` if you want those) |
| `LOCATION_KEYWORDS`, `GEO_EXCLUDE`, `TITLE_GEO_EXCLUDE` | Keep remote/US roles, drop other regions | Tuned for **US fully-remote** searches. Change if you're open to other countries |
| `ONSITE_EXACT_BLOCK` | Drops jobs listed only as a specific big city | Remove a city if you live there and want on-site roles |
| `COMPANIES` | The companies to watch | Add/remove lines (see below). `"applied": True` just tags a job in the Metadata column |

**Privacy note:** your resume text lives in `job_scraper.py`. If you put this code on GitHub, keep the repository **private** — don't fork the public one, because forks of public repos stay public.

**Adding a company:** find its careers page, look at the web address, and copy the short name ("slug"):

- Greenhouse: `boards.greenhouse.io/{slug}` or `job-boards.greenhouse.io/{slug}`
- Lever: `jobs.lever.co/{slug}`
- Ashby: `jobs.ashbyhq.com/{slug}`

Then add a line in `COMPANIES`, matching the pattern of the existing ones:

```python
{"name": "Example Co", "ats": "greenhouse", "id": "exampleco"},
```

If a company uses a different system (Workday, Rippling, etc.), this tool can't read it.

### 6. First run — go in this order

Each step costs a little more or touches more of your accounts than the last, so you catch problems early.

```bash
# 1. Free: scrape and filter only. Needs no accounts. Confirms Python + install work.
python3 job_scraper.py --test

# 2. Cheap: also scores 10 jobs and prints them. Reads (never writes) your Notion DB.
python3 job_scraper.py --preview-scrape --limit 10

# 3. The real thing: scores every new job and writes to Notion.
python3 job_scraper.py
```

Read the step 2 scores. If they look wrong, fix `CANDIDATE_PROFILE` / `RESUME_TEXT` and re-run step 2 before moving on. The first real run can find a few hundred jobs, so it takes a while and costs a bit more than a normal day.

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

Note: rescoring works from what's stored in Notion (title, company, location, salary), not the full job description, so rescored jobs get less context than jobs scored when first found.

---

## Running it every day

The script only runs when you tell it to. Pick one:

### Option A — GitHub Actions (runs in the cloud, even when your computer is off)

1. Create a **new private repository** on GitHub and upload these files (keep the folder structure, including `.github/workflows/daily.yml`).
2. In the repo go to **Settings → Secrets and variables → Actions → New repository secret** and add three secrets named exactly `ANTHROPIC_API_KEY`, `NOTION_TOKEN`, and `NOTION_DB_ID`.
3. Open the **Actions** tab, choose **Daily job scrape**, and click **Run workflow** to test it.
4. After that it runs daily on its own. Change the time in the `cron:` line of `daily.yml` (times are in UTC).

GitHub pauses scheduled workflows after about 60 days with no activity in the repo. If new jobs stop appearing, open the Actions tab and re-enable it.

### Option B — On your own computer

Run `python3 job_scraper.py` whenever you like, or schedule it with **cron** (Mac/Linux) or **Task Scheduler** (Windows). The computer has to be on and online at that time.

---

## Troubleshooting

| What you see | What it means / fix |
|--------------|---------------------|
| `command not found: python3` / `'python' is not recognized` | Python isn't installed or isn't on your PATH. Reinstall from python.org and tick "Add Python to PATH". On Windows try `python` or `py` instead of `python3`. |
| `ModuleNotFoundError: No module named 'requests'` | Dependencies aren't installed. Run `pip3 install -r requirements.txt` (or `python3 -m pip install -r requirements.txt`). |
| `ERROR connecting to Notion: 401 ... Unauthorized` | `NOTION_TOKEN` is wrong or has stray quotes/spaces. Re-copy it into `.env`. |
| `ERROR connecting to Notion: 404 ... Not Found` | Either `NOTION_DB_ID` is wrong, or you haven't added the integration under **··· → Connections** on the database. |
| `[Notion] Failed to write ...: 400 ...` mentioning a property | A column name or type doesn't match the table in step 4 (e.g. `ID` is Title instead of Text, or `Fit Score` isn't a Number). Fix the column in Notion. |
| `ANTHROPIC_API_KEY not set — jobs will be added without fit scores` | The key isn't being read. Check that the file is named exactly `.env`, sits in the same folder as `job_scraper.py`, and has no quotes. |
| `[Claude] Scoring error: 401` | API key is wrong or was revoked. Create a new one. |
| `[Claude] Scoring error: 400` mentioning credit balance | Add credit under Billing at console.anthropic.com. |
| `[Claude] Scoring error: 404` / "model not found" | The model name in `score_job` (search for `claude-haiku`) has been retired. Replace it with a current Haiku model name from the [Anthropic docs](https://docs.claude.com). |
| `[Greenhouse] HTTP 404 for xyz` (or Lever/Ashby) | That company's slug is wrong or they've moved to a different job system. Check its careers page URL, fix or delete the line in `COMPANIES`. The summary at the end lists every company that failed. |
| `New jobs found: 0` | Normal if nothing new matched — filters are strict by design. If it's always 0, check `KEYWORDS` and the location lists. |
| Everything scores 2–3 | Your `CANDIDATE_PROFILE` / `RESUME_TEXT` probably still contain the original author's details, or are too vague. |

---

## Cost

Running daily costs roughly **$1–3/month** using Claude Haiku (~$0.001/job scored). The scraper only scores *new* jobs on each run, so after the initial backlog is cleared, daily costs are minimal.

---

## Project structure

```
job-scraper/
├── job_scraper.py                  # Main script (all configuration lives at the top)
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment variable template
├── .github/workflows/daily.yml     # Optional: daily run on GitHub Actions
├── .gitignore
└── README.md
```

---

## Background

Built this because manually checking job boards every day is slow and noisy. By targeting specific companies I actually want to work at and scoring results against my background automatically, I can triage a daily feed in under 5 minutes instead of an hour.

The Notion integration gives me a structured, sortable database I can filter by fit score, company, and status — and link to a separate Job Tracker for active applications.
