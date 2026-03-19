"""Scraper module: fetches job listings from multiple sources focused on India."""
import json
import logging
import re
import time
import urllib.parse
from dataclasses import dataclass, field

import google.generativeai as genai
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

INDIA_KEYWORDS = ["india", "worldwide", "anywhere", "global", "asia", "remote", "bangalore",
                  "mumbai", "delhi", "hyderabad", "pune", "chennai", "kolkata", "noida", "gurgaon", "gurugram"]

# LinkedIn search keywords for entry-level India jobs
LINKEDIN_SEARCH_KEYWORDS = [
    "python developer", "machine learning", "data analyst",
    "software engineer", "frontend developer", "backend developer",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def _is_india_friendly(location: str) -> bool:
    if not location:
        return True
    loc = location.lower()
    return any(kw in loc for kw in INDIA_KEYWORDS)


def _extract_experience(text: str) -> str:
    text_lower = text.lower()
    match = re.search(r'(\d+)\s*[-–to]+\s*(\d+)\s*(?:years?|yrs?)', text_lower)
    if match:
        return f"{match.group(1)}-{match.group(2)} years"
    match = re.search(r'(\d+)\+?\s*(?:years?|yrs?)', text_lower)
    if match:
        return f"{match.group(1)}+ years"
    if any(kw in text_lower for kw in ["entry level", "entry-level", "junior", "fresher", "intern"]):
        return "Entry Level"
    return ""


def _is_entry_level(experience: str) -> bool:
    if not experience:
        return True
    exp_lower = experience.lower()
    if any(kw in exp_lower for kw in ["entry", "junior", "intern", "fresher", "0"]):
        return True
    match = re.search(r'(\d+)', exp_lower)
    if match:
        return int(match.group(1)) <= 2
    return True


@dataclass
class JobListing:
    title: str
    company: str
    url: str
    tags: list[str] = field(default_factory=list)
    date_posted: str = ""
    source: str = ""
    salary: str = ""
    experience: str = ""
    requirements: str = ""
    summary: str = ""
    location: str = ""


# --- Source 1: Remotive API ---

def fetch_remotive_jobs() -> list[JobListing]:
    """Fetch India-friendly entry-level jobs from Remotive API."""
    try:
        resp = requests.get("https://remotive.com/api/remote-jobs", timeout=30, headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()
        jobs = []
        for j in data.get("jobs", []):
            desc = j.get("description", "") or ""
            location = j.get("candidate_required_location", "") or ""
            if not _is_india_friendly(location.lower()):
                continue
            exp = _extract_experience(desc)
            if not _is_entry_level(exp):
                continue
            jobs.append(JobListing(
                title=j.get("title", ""),
                company=j.get("company_name", ""),
                url=j.get("url", ""),
                tags=[t.strip() for t in j.get("tags", []) if t.strip()],
                date_posted=j.get("publication_date", "")[:10],
                source="Remotive",
                salary=j.get("salary", "") or "",
                experience=exp,
                summary=desc[:200] if desc else "",
                location=location or "Remote",
            ))
        logger.info("Remotive: fetched %d India-friendly entry-level jobs", len(jobs))
        return jobs
    except Exception as e:
        logger.error("Failed to fetch Remotive jobs: %s", e)
        return []


# --- Source 2: LinkedIn (public job search, no auth needed) ---

def fetch_linkedin_jobs() -> list[JobListing]:
    """Fetch entry-level jobs in India from LinkedIn's public job search."""
    all_jobs = []
    for keyword in LINKEDIN_SEARCH_KEYWORDS:
        try:
            params = {
                "keywords": keyword,
                "location": "India",
                "f_E": "1,2",  # Entry level + Associate
                "f_TPR": "r86400",  # Past 24 hours
                "position": "1",
                "pageNum": "0",
            }
            url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?{urllib.parse.urlencode(params)}"
            resp = requests.get(url, timeout=30, headers=HEADERS)
            if resp.status_code != 200:
                logger.warning("LinkedIn returned %d for '%s'", resp.status_code, keyword)
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            for card in soup.select("li"):
                title_el = card.select_one("h3.base-search-card__title")
                company_el = card.select_one("h4.base-search-card__subtitle")
                link_el = card.select_one("a.base-card__full-link")
                location_el = card.select_one("span.job-search-card__location")
                date_el = card.select_one("time")

                title = title_el.get_text(strip=True) if title_el else ""
                company = company_el.get_text(strip=True) if company_el else ""
                job_url = link_el.get("href", "").split("?")[0] if link_el else ""
                location = location_el.get_text(strip=True) if location_el else "India"
                date_posted = date_el.get("datetime", "") if date_el else ""

                if not title or not job_url:
                    continue
                all_jobs.append(JobListing(
                    title=title,
                    company=company,
                    url=job_url,
                    tags=[keyword],
                    date_posted=date_posted[:10],
                    source="LinkedIn",
                    salary="",
                    experience="Entry Level",
                    summary="",
                    location=location,
                ))
        except Exception as e:
            logger.error("Failed to fetch LinkedIn jobs for '%s': %s", keyword, e)
    logger.info("LinkedIn: fetched %d jobs from India", len(all_jobs))
    return all_jobs


# --- Source 3: Arbeitnow (free API, supports India/remote filter) ---

def fetch_arbeitnow_jobs() -> list[JobListing]:
    """Fetch remote jobs from Arbeitnow free API."""
    try:
        resp = requests.get("https://www.arbeitnow.com/api/job-board-api", timeout=30, headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()
        jobs = []
        for j in data.get("data", []):
            location = j.get("location", "") or ""
            if not j.get("remote", False) and not _is_india_friendly(location.lower()):
                continue
            desc = j.get("description", "") or ""
            exp = _extract_experience(desc)
            if not _is_entry_level(exp):
                continue
            tags = [t.strip() for t in j.get("tags", []) if t.strip()]
            jobs.append(JobListing(
                title=j.get("title", ""),
                company=j.get("company_name", ""),
                url=j.get("url", ""),
                tags=tags,
                date_posted=j.get("created_at", "")[:10],
                source="Arbeitnow",
                salary="",
                experience=exp,
                summary=BeautifulSoup(desc, "html.parser").get_text()[:200] if desc else "",
                location="Remote" if j.get("remote") else location,
            ))
        logger.info("Arbeitnow: fetched %d jobs", len(jobs))
        return jobs
    except Exception as e:
        logger.error("Failed to fetch Arbeitnow jobs: %s", e)
        return []


# --- Source 4: Internshala ---

INTERNSHALA_CATEGORIES = [
    "python-development", "web-development", "machine-learning",
    "data-science", "software-development", "frontend-development",
]


def fetch_internshala_jobs() -> list[JobListing]:
    """Fetch entry-level jobs/internships from Internshala."""
    all_jobs: list[JobListing] = []
    for category in INTERNSHALA_CATEGORIES:
        try:
            url = f"https://internshala.com/jobs/{category}-jobs"
            resp = requests.get(url, timeout=30, headers=HEADERS)
            if resp.status_code != 200:
                logger.warning("Internshala returned %d for '%s'", resp.status_code, category)
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            for card in soup.select(".individual_internship, .individual_job"):
                title_el = card.select_one(".job-internship-name a, .profile a, h3 a")
                company_el = card.select_one(".company-name a, .company_name a, p.company-name")
                link_el = card.select_one(".job-internship-name a, .profile a, h3 a")
                location_el = card.select_one(".locations a, #location_names a, .location_link")
                salary_el = card.select_one(".salary .desktop-text, .stipend, span.salary")

                title = title_el.get_text(strip=True) if title_el else ""
                company = company_el.get_text(strip=True) if company_el else ""
                href = link_el.get("href", "") if link_el else ""
                job_url = f"https://internshala.com{href}" if href and not href.startswith("http") else href
                location = location_el.get_text(strip=True) if location_el else "India"
                salary = salary_el.get_text(strip=True) if salary_el else ""

                if not title or not job_url:
                    continue
                all_jobs.append(JobListing(
                    title=title, company=company, url=job_url,
                    tags=[category.replace("-", " ")],
                    date_posted="", source="Internshala",
                    salary=salary, experience="Entry Level",
                    summary="", location=location,
                ))
            time.sleep(1)  # polite delay between requests
        except Exception as e:
            logger.error("Failed to fetch Internshala jobs for '%s': %s", category, e)
    logger.info("Internshala: fetched %d jobs", len(all_jobs))
    return all_jobs


# --- Source 5: Foundit (formerly Monster India) ---

FOUNDIT_SEARCH_KEYWORDS = [
    "python developer", "data analyst", "software engineer",
    "frontend developer", "backend developer", "machine learning",
]


def fetch_foundit_jobs() -> list[JobListing]:
    """Fetch entry-level jobs from Foundit (Monster India)."""
    all_jobs: list[JobListing] = []
    for keyword in FOUNDIT_SEARCH_KEYWORDS:
        try:
            encoded = urllib.parse.quote(keyword)
            url = f"https://www.foundit.in/srp/results?query={encoded}&experienceRanges=0~2&locations=India"
            resp = requests.get(url, timeout=30, headers=HEADERS)
            if resp.status_code != 200:
                logger.warning("Foundit returned %d for '%s'", resp.status_code, keyword)
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            for card in soup.select(".srpResultCardContainer, .card-apply-content, .jobTuple"):
                title_el = card.select_one(".jobTitle, .title, a.job-tittle, h3 a")
                company_el = card.select_one(".companyName, .company-name, .comp-name")
                link_el = card.select_one("a.jobTitle, a.title, a.job-tittle, h3 a")
                location_el = card.select_one(".location, .loc, .locWdth")
                salary_el = card.select_one(".salary, .sal")
                exp_el = card.select_one(".experience, .exp")

                title = title_el.get_text(strip=True) if title_el else ""
                company = company_el.get_text(strip=True) if company_el else ""
                href = link_el.get("href", "") if link_el else ""
                job_url = href if href.startswith("http") else f"https://www.foundit.in{href}" if href else ""
                location = location_el.get_text(strip=True) if location_el else "India"
                salary = salary_el.get_text(strip=True) if salary_el else ""
                experience = exp_el.get_text(strip=True) if exp_el else ""

                if not title or not job_url:
                    continue
                all_jobs.append(JobListing(
                    title=title, company=company, url=job_url,
                    tags=[keyword], date_posted="", source="Foundit",
                    salary=salary, experience=experience or "0-2 years",
                    summary="", location=location,
                ))
            time.sleep(1)
        except Exception as e:
            logger.error("Failed to fetch Foundit jobs for '%s': %s", keyword, e)
    logger.info("Foundit: fetched %d jobs", len(all_jobs))
    return all_jobs


# --- Source 6: Naukri.com ---

NAUKRI_SEARCH_KEYWORDS = [
    "python developer", "data analyst", "software engineer",
    "frontend developer", "backend developer", "machine learning",
]


def fetch_naukri_jobs() -> list[JobListing]:
    """Fetch entry-level jobs from Naukri.com."""
    all_jobs: list[JobListing] = []
    for keyword in NAUKRI_SEARCH_KEYWORDS:
        try:
            slug = keyword.replace(" ", "-")
            url = f"https://www.naukri.com/{slug}-jobs?experience=0-2"
            resp = requests.get(url, timeout=30, headers=HEADERS)
            if resp.status_code != 200:
                logger.warning("Naukri returned %d for '%s'", resp.status_code, keyword)
                continue
            soup = BeautifulSoup(resp.text, "html.parser")

            # Naukri embeds job data in script tags as JSON-LD
            for script in soup.select('script[type="application/ld+json"]'):
                try:
                    data = json.loads(script.string or "")
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        if item.get("@type") != "JobPosting":
                            continue
                        title = item.get("title", "")
                        company = ""
                        org = item.get("hiringOrganization", {})
                        if isinstance(org, dict):
                            company = org.get("name", "")
                        job_url = item.get("url", "")
                        location = ""
                        loc = item.get("jobLocation", {})
                        if isinstance(loc, dict):
                            addr = loc.get("address", {})
                            if isinstance(addr, dict):
                                location = addr.get("addressLocality", "") or addr.get("addressRegion", "")
                        elif isinstance(loc, list) and loc:
                            addr = loc[0].get("address", {})
                            if isinstance(addr, dict):
                                location = addr.get("addressLocality", "")
                        salary_obj = item.get("baseSalary", {})
                        salary = ""
                        if isinstance(salary_obj, dict):
                            val = salary_obj.get("value", {})
                            if isinstance(val, dict):
                                min_v = val.get("minValue", "")
                                max_v = val.get("maxValue", "")
                                salary = f"₹{min_v}-{max_v}" if min_v and max_v else ""
                        date_posted = item.get("datePosted", "")[:10]

                        if not title or not job_url:
                            continue
                        all_jobs.append(JobListing(
                            title=title, company=company, url=job_url,
                            tags=[keyword], date_posted=date_posted,
                            source="Naukri", salary=salary,
                            experience="0-2 years", summary="",
                            location=location or "India",
                        ))
                except (json.JSONDecodeError, TypeError):
                    continue

            # Also try HTML card selectors as fallback
            for card in soup.select(".jobTuple, .srp-jobtuple-wrapper, article.jobTuple"):
                title_el = card.select_one("a.title, .jobTitle a, .info h2 a")
                company_el = card.select_one(".comp-name, .companyInfo a, .subTitle a")
                link_el = card.select_one("a.title, .jobTitle a, .info h2 a")
                location_el = card.select_one(".loc, .location, .locWdth")
                salary_el = card.select_one(".sal, .salary")
                exp_el = card.select_one(".exp, .experience")

                title = title_el.get_text(strip=True) if title_el else ""
                company = company_el.get_text(strip=True) if company_el else ""
                href = link_el.get("href", "") if link_el else ""
                job_url = href if href.startswith("http") else f"https://www.naukri.com{href}" if href else ""
                location = location_el.get_text(strip=True) if location_el else "India"
                salary = salary_el.get_text(strip=True) if salary_el else ""
                experience = exp_el.get_text(strip=True) if exp_el else ""

                if not title or not job_url:
                    continue
                all_jobs.append(JobListing(
                    title=title, company=company, url=job_url,
                    tags=[keyword], date_posted="", source="Naukri",
                    salary=salary, experience=experience or "0-2 years",
                    summary="", location=location,
                ))
            time.sleep(1)
        except Exception as e:
            logger.error("Failed to fetch Naukri jobs for '%s': %s", keyword, e)
    logger.info("Naukri: fetched %d jobs", len(all_jobs))
    return all_jobs


# --- LLM-based job filtering using Gemini ---

def filter_jobs_with_llm(jobs: list[JobListing], gemini_api_key: str) -> list[JobListing]:
    """Use Gemini to filter and rank scraped jobs for relevance and quality.

    The LLM evaluates each job for:
    - Genuine entry-level suitability (0-2 years)
    - India/remote friendliness
    - Legitimacy (filters spam, fake, or misleading postings)
    - Quality of the opportunity

    Returns the filtered list of jobs sorted by relevance.
    """
    if not jobs:
        return []
    if not gemini_api_key:
        logger.warning("No Gemini API key provided, skipping LLM filtering")
        return jobs

    # Process in batches to stay within token limits
    BATCH_SIZE = 30
    filtered_jobs: list[JobListing] = []

    genai.configure(api_key=gemini_api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    for batch_start in range(0, len(jobs), BATCH_SIZE):
        batch = jobs[batch_start:batch_start + BATCH_SIZE]
        job_summaries = []
        for i, job in enumerate(batch):
            job_summaries.append(
                f"{i}: title=\"{job.title}\", company=\"{job.company}\", "
                f"location=\"{job.location}\", salary=\"{job.salary}\", "
                f"experience=\"{job.experience}\", source=\"{job.source}\", "
                f"tags={job.tags}"
            )

        prompt = (
            "You are a job listing quality filter for entry-level candidates in India.\n"
            "Review these job listings and return ONLY the indices of jobs that are:\n"
            "1. Genuinely entry-level or suitable for 0-2 years experience\n"
            "2. Based in India or genuinely remote-friendly\n"
            "3. Appear to be legitimate postings (not spam, scams, or misleading)\n"
            "4. From real companies with reasonable job descriptions\n\n"
            "Filter OUT jobs that:\n"
            "- Require 3+ years of experience despite being listed as entry-level\n"
            "- Are clearly spam or fake postings\n"
            "- Are unpaid with no clear internship value\n"
            "- Have misleading titles (e.g., 'Senior' roles listed as entry-level)\n\n"
            "Job listings:\n" + "\n".join(job_summaries) + "\n\n"
            "Return a JSON array of the accepted job indices, e.g. [0, 2, 5, 7].\n"
            "Return ONLY the JSON array, nothing else."
        )

        try:
            response = model.generate_content(prompt)
            text = response.text.strip()
            # Extract JSON array from response
            match = re.search(r'\[[\d\s,]*\]', text)
            if match:
                accepted_indices = json.loads(match.group())
                for idx in accepted_indices:
                    if 0 <= idx < len(batch):
                        filtered_jobs.append(batch[idx])
            else:
                logger.warning("LLM filter returned unparseable response, keeping batch as-is")
                filtered_jobs.extend(batch)
        except Exception as e:
            logger.warning("LLM filtering failed for batch: %s. Keeping batch as-is.", e)
            filtered_jobs.extend(batch)

        time.sleep(0.5)  # rate limit between batches

    logger.info("LLM filter: %d → %d jobs", len(jobs), len(filtered_jobs))
    return filtered_jobs


# --- Generic web source scraper ---

def scrape_web_source(source_config: dict) -> list[JobListing]:
    """Scrape a single web source using requests + BeautifulSoup."""
    try:
        resp = requests.get(source_config["url"], timeout=30, headers=HEADERS)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        jobs = []
        selectors = source_config.get("selectors", {})
        for item in soup.select(selectors.get("listing", ".job-listing")):
            title_el = item.select_one(selectors.get("title", ".title"))
            company_el = item.select_one(selectors.get("company", ".company"))
            link_el = item.select_one(selectors.get("link", "a"))
            salary_el = item.select_one(selectors.get("salary", ".salary"))
            location_el = item.select_one(selectors.get("location", ".location"))
            title = title_el.get_text(strip=True) if title_el else ""
            company = company_el.get_text(strip=True) if company_el else ""
            url = link_el.get("href", "") if link_el else ""
            location = location_el.get_text(strip=True) if location_el else ""
            if not title or not url:
                continue
            if location and not _is_india_friendly(location.lower()):
                continue
            jobs.append(JobListing(
                title=title, company=company, url=url, tags=[], date_posted="",
                source=source_config.get("name", "web"),
                salary=salary_el.get_text(strip=True) if salary_el else "",
                experience="", requirements="", summary="", location=location or "Remote",
            ))
        return jobs
    except Exception as e:
        logger.error("Failed to scrape %s: %s", source_config.get("name", "unknown"), e)
        return []


# --- Main entry point ---

def scrape_all_jobs(sources: list[dict] | None = None, gemini_api_key: str = "") -> list[JobListing]:
    """Fetch from all sources, combine, deduplicate, and filter with LLM."""
    sources = sources or []
    all_jobs: list[JobListing] = []

    # Built-in sources
    all_jobs.extend(fetch_remotive_jobs())
    all_jobs.extend(fetch_linkedin_jobs())
    all_jobs.extend(fetch_arbeitnow_jobs())
    all_jobs.extend(fetch_internshala_jobs())
    all_jobs.extend(fetch_foundit_jobs())
    all_jobs.extend(fetch_naukri_jobs())

    # Custom web sources from config
    for src in sources:
        all_jobs.extend(scrape_web_source(src))

    if not all_jobs:
        logger.warning("All sources returned zero job listings.")
        return []

    # Deduplicate by URL
    seen_urls: set[str] = set()
    unique_jobs: list[JobListing] = []
    for job in all_jobs:
        if job.url and job.url not in seen_urls:
            seen_urls.add(job.url)
            unique_jobs.append(job)

    logger.info("Total unique jobs after dedup: %d", len(unique_jobs))

    # LLM-based filtering for quality and relevance
    filtered_jobs = filter_jobs_with_llm(unique_jobs, gemini_api_key)

    return filtered_jobs
