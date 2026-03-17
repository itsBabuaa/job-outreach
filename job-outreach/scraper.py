"""Scraper module: fetches job listings from Remotive API and web sources."""
import logging
from dataclasses import dataclass, field
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# India-friendly location keywords
INDIA_KEYWORDS = ["india", "worldwide", "anywhere", "global", "asia", "remote"]


def _is_india_friendly(location: str) -> bool:
    """Check if a job location is available for India-based candidates."""
    if not location:
        return True  # No location restriction = assume worldwide
    return any(kw in location for kw in INDIA_KEYWORDS)


def _extract_experience(text: str) -> str:
    """Try to extract experience requirement from job description."""
    import re
    text_lower = text.lower()
    # Look for patterns like "0-2 years", "1+ years", "entry level", etc.
    match = re.search(r'(\d+)\s*[-–to]+\s*(\d+)\s*(?:years?|yrs?)', text_lower)
    if match:
        return f"{match.group(1)}-{match.group(2)} years"
    match = re.search(r'(\d+)\+?\s*(?:years?|yrs?)', text_lower)
    if match:
        return f"{match.group(1)}+ years"
    if "entry level" in text_lower or "entry-level" in text_lower or "junior" in text_lower:
        return "Entry Level"
    return ""


def _is_entry_level(experience: str) -> bool:
    """Check if experience requirement is 0-2 years or entry level."""
    if not experience:
        return True  # No experience listed = include it
    import re
    exp_lower = experience.lower()
    if "entry" in exp_lower or "junior" in exp_lower or "intern" in exp_lower:
        return True
    match = re.search(r'(\d+)', exp_lower)
    if match:
        min_years = int(match.group(1))
        return min_years <= 2
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


def fetch_remotive_jobs() -> list[JobListing]:
    """Fetch jobs from Remotive API. Returns empty list on failure."""
    try:
        resp = requests.get("https://remotive.com/api/remote-jobs", timeout=30)
        resp.raise_for_status()
        data = resp.json()
        jobs = []
        for j in data.get("jobs", []):
            desc = j.get("description", "") or ""
            location = j.get("candidate_required_location", "") or ""
            # Filter: only include jobs available in India or worldwide
            location_lower = location.lower()
            if not _is_india_friendly(location_lower):
                continue
            jobs.append(JobListing(
                title=j.get("title", ""),
                company=j.get("company_name", ""),
                url=j.get("url", ""),
                tags=[t.strip() for t in j.get("tags", []) if t.strip()],
                date_posted=j.get("publication_date", "")[:10],
                source="remotive",
                salary=j.get("salary", "") or "",
                experience=_extract_experience(desc),
                requirements="",
                summary=desc[:200] if desc else "",
                location=location,
            ))
        # Filter for 0-2 years experience
        return [j for j in jobs if _is_entry_level(j.experience)]
    except Exception as e:
        logger.error("Failed to fetch Remotive jobs: %s", e)
        return []


def scrape_web_source(source_config: dict) -> list[JobListing]:
    """Scrape a single web source using requests + BeautifulSoup. Returns empty list on failure."""
    try:
        resp = requests.get(source_config["url"], timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        jobs = []
        selectors = source_config.get("selectors", {})
        for item in soup.select(selectors.get("listing", ".job-listing")):
            title_el = item.select_one(selectors.get("title", ".title"))
            company_el = item.select_one(selectors.get("company", ".company"))
            link_el = item.select_one(selectors.get("link", "a"))
            salary_el = item.select_one(selectors.get("salary", ".salary"))
            req_el = item.select_one(selectors.get("requirements", ".requirements"))
            summary_el = item.select_one(selectors.get("summary", ".summary"))
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
                title=title,
                company=company,
                url=url,
                tags=[],
                date_posted="",
                source=source_config.get("name", "web"),
                salary=salary_el.get_text(strip=True) if salary_el else "",
                experience="",
                requirements=req_el.get_text(strip=True) if req_el else "",
                summary=summary_el.get_text(strip=True) if summary_el else "",
                location=location,
            ))
        return jobs
    except Exception as e:
        logger.error("Failed to scrape %s: %s", source_config.get("name", "unknown"), e)
        return []


def scrape_all_jobs(sources: list[dict]) -> list[JobListing]:
    """Fetch from Remotive + all web sources. Combines and deduplicates by URL."""
    all_jobs = fetch_remotive_jobs()
    for src in sources:
        all_jobs.extend(scrape_web_source(src))

    if not all_jobs:
        logger.warning("All sources returned zero job listings.")
        return []

    # Deduplicate by URL
    seen_urls: set[str] = set()
    unique_jobs: list[JobListing] = []
    for job in all_jobs:
        if job.url not in seen_urls:
            seen_urls.add(job.url)
            unique_jobs.append(job)
    return unique_jobs
