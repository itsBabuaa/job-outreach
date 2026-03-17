# 🚀 Job Digest Mailer

Automated daily job digest pipeline that scrapes entry-level jobs from multiple sources, matches them to subscriber skills, and delivers personalized HTML email digests — focused on **India-based** and **remote** opportunities.

**POWERED BY Babuaa**

---

## ✨ Features

- 🔍 Scrapes jobs from **LinkedIn**, **Remotive**, and **Arbeitnow** daily
- 🇮🇳 Filters for India-friendly locations (India, Remote, Worldwide)
- 📋 Targets **0-2 years experience** / entry-level roles
- 🤖 AI-powered digest emails via **Google Gemini** (with plain-text fallback)
- 💌 Beautiful HTML emails with job cards, salary, location, and "Apply Now" buttons
- ⏰ Runs daily at **7 PM UTC** via GitHub Actions
- 🗄️ Stores data in **Supabase** (free Postgres)
- 🖥️ Flask **Admin Dashboard** to manage subscribers and view jobs

---

## 🏗️ Architecture

```mermaid
flowchart TD
    GHA["⏰ GitHub Actions<br/>Cron: 7 PM UTC"] --> Pipeline["🔄 Pipeline Orchestrator"]

    Pipeline --> Scraper["🔍 Scraper Module"]
    Scraper --> LinkedIn["LinkedIn<br/>India + Entry Level"]
    Scraper --> Remotive["Remotive API<br/>Remote Jobs"]
    Scraper --> Arbeitnow["Arbeitnow API<br/>Remote Jobs"]
    Scraper --> WebSources["Custom Web Sources<br/>BeautifulSoup"]

    Pipeline --> Store["🗄️ Store Jobs"]
    Store --> Supabase[("Supabase<br/>Postgres")]

    Pipeline --> Digest["📝 Digest Generator"]
    Digest --> SkillMatch["Skill Matching<br/>Keywords Filter"]
    Digest --> Gemini["Google Gemini<br/>AI Email Body"]
    Digest --> Fallback["Plain-text<br/>Fallback Template"]

    Pipeline --> Mailer["📧 Mailer"]
    Mailer --> Gmail["Gmail SMTP<br/>HTML Emails"]

    Pipeline --> Record["📊 Record Sent"]
    Record --> Supabase

    Admin["🖥️ Flask Admin<br/>Dashboard"] --> Supabase
    Admin -.-> Pipeline
```

## 📧 Email Flow

```mermaid
flowchart LR
    A["Scrape 3 Sources"] --> B["Filter: India + 0-2 yrs"]
    B --> C["Deduplicate by URL"]
    C --> D["Store in Supabase"]
    D --> E["Match Skills per Subscriber"]
    E --> F["Top 10 Jobs"]
    F --> G{"Gemini API OK?"}
    G -->|Yes| H["AI-Generated HTML Email"]
    G -->|No| I["Fallback HTML Template"]
    H --> J["📬 Send via Gmail"]
    I --> J
    J --> K["Record in sent_digests"]
```

## 📂 Project Structure

```
job-outreach/
├── config.py              # Environment config & validation
├── scraper.py             # Multi-source job scraper (LinkedIn, Remotive, Arbeitnow)
├── db.py                  # Supabase database operations
├── digest.py              # Skill matching + HTML email generation
├── mailer.py              # Gmail SMTP sender with rate limiting
├── pipeline.py            # End-to-end orchestrator
├── admin/
│   ├── app.py             # Flask admin dashboard
│   └── templates/         # Jinja2 HTML templates
├── migrations/
│   └── 001_initial_schema.sql
├── tests/
│   ├── conftest.py        # Shared fixtures & Hypothesis strategies
│   └── ...
├── pyproject.toml
└── .env.example
```

## 🗄️ Database Schema

```mermaid
erDiagram
    subscribers {
        uuid id PK
        text email UK
        text status "active | inactive"
        text_arr skill_set
        timestamptz created_at
        timestamptz updated_at
    }
    job_listings {
        uuid id PK
        text url UK
        text title
        text company
        text_arr tags
        date date_posted
        text source
        text salary
        text requirements
        text summary
        timestamptz scraped_at
    }
    sent_digests {
        uuid id PK
        uuid subscriber_id FK
        date date_sent
        int job_count
        timestamptz created_at
    }
    sent_digest_jobs {
        uuid digest_id FK
        uuid job_id FK
    }
    subscribers ||--o{ sent_digests : "receives"
    sent_digests ||--o{ sent_digest_jobs : "contains"
    job_listings ||--o{ sent_digest_jobs : "included_in"
```

## 🚀 Setup

### 1. Supabase
- Create a free project at [supabase.com](https://supabase.com)
- Run `job-outreach/migrations/001_initial_schema.sql` in the SQL Editor

### 2. Gmail App Password
- Enable 2FA on your Google account
- Create an app password at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)

### 3. Gemini API Key
- Get a free key at [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)

### 4. GitHub Secrets
Add these in your repo → Settings → Secrets → Actions:

| Secret | Description |
|--------|-------------|
| `GMAIL_USER` | Your Gmail address |
| `GMAIL_APP_PASSWORD` | 16-char app password |
| `GEMINI_API_KEY` | Google Gemini API key |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_KEY` | Supabase anon key |

### 5. Add Subscribers
```sql
INSERT INTO subscribers (email, status, skill_set)
VALUES (
  'you@example.com',
  'active',
  ARRAY['Python','Machine Learning','Data Analysis','Flask','FastAPI']
);
```

## 🏃 Run Locally

```bash
cd job-outreach
cp .env.example .env   # Fill in real values
uv sync
uv run python pipeline.py        # Run the digest pipeline
uv run python admin/app.py       # Start admin dashboard at localhost:5000
```

## ⏰ Automated Schedule

The GitHub Actions workflow runs daily at **7 PM UTC** (12:30 AM IST). You can also trigger it manually from the Actions tab.

## 📊 Job Sources

| Source | Type | Focus |
|--------|------|-------|
| LinkedIn | HTML scraping | India, entry-level |
| Remotive | REST API | Remote, worldwide |
| Arbeitnow | REST API | Remote jobs |

---

**POWERED BY Babuaa** ✨
