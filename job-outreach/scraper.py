"""Scraper module: fetches job listings from multiple sources focused on India."""
import logging
import re
import urllib.parse
from dataclasses import dataclass, field
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

def scrape_all_jobs(sources: list[dict] | None = None) -> list[JobListing]:
    """Fetch from all sources, combine, and deduplicate by URL."""
    sources = sources or []
    all_jobs: list[JobListing] = []

    # Built-in sources
    all_jobs.extend(fetch_remotive_jobs())
    all_jobs.extend(fetch_linkedin_jobs())
    all_jobs.extend(fetch_arbeitnow_jobs())

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
    return unique_jobs
