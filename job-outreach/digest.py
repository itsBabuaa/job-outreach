"""Digest Generator: matches jobs to subscribers and generates email content."""
import logging
import google.generativeai as genai

logger = logging.getLogger(__name__)


def match_jobs_to_skills(jobs: list[dict], skill_set: list[str]) -> list[dict]:
    """Filter jobs where title, tags, or company match any skill keyword. Case-insensitive."""
    if not skill_set:
        return []
    keywords = [kw.lower() for kw in skill_set]
    matched = []
    for job in jobs:
        searchable = " ".join([
            job.get("title", ""),
            job.get("company", ""),
            " ".join(job.get("tags", [])),
        ]).lower()
        if any(kw in searchable for kw in keywords):
            matched.append(job)
    return matched


def generate_digest_with_gemini(jobs: list[dict], subscriber_name: str) -> str:
    """Call Gemini API to compose a formatted email body. Raises on API error."""
    job_lines = []
    for j in jobs:
        location = j.get("location", "") or "Remote"
        parts = [f"- {j['title']} at {j['company']}"]
        parts.append(f"  Location: {location}")
        if j.get("salary"):
            parts.append(f"  Pay: {j['salary']}")
        if j.get("experience"):
            parts.append(f"  Experience: {j['experience']}")
        if j.get("requirements"):
            parts.append(f"  Requirements: {j['requirements']}")
        if j.get("summary"):
            parts.append(f"  Summary: {j['summary']}")
        parts.append(f"  Apply: {j['url']}")
        job_lines.append("\n".join(parts))

    prompt = (
        f"Write a friendly, professional email digest for {subscriber_name} "
        f"with these {len(jobs)} job listings targeted at India-based candidates. "
        f"Show salary in INR where possible. Include the title, company, location, pay, "
        f"experience level, requirements, a short summary, and application link for each:\n\n"
        + "\n\n".join(job_lines)
    )
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    return response.text


def generate_digest_fallback(jobs: list[dict]) -> str:
    """Plain-text fallback listing title, company, URL, salary, requirements, and summary."""
    lines = [f"Your Job Digest - India ({len(jobs)} listings)\n{'=' * 40}\n"]
    for i, j in enumerate(jobs, 1):
        location = j.get("location", "") or "Remote"
        lines.append(f"{i}. {j['title']} at {j['company']}")
        lines.append(f"   Location: {location}")
        if j.get("salary"):
            lines.append(f"   Pay: {j['salary']}")
        if j.get("experience"):
            lines.append(f"   Experience: {j['experience']}")
        if j.get("requirements"):
            lines.append(f"   Requirements: {j['requirements']}")
        if j.get("summary"):
            lines.append(f"   Summary: {j['summary']}")
        lines.append(f"   Apply: {j['url']}")
        lines.append("")
    return "\n".join(lines)


def create_digest(subscriber: dict, jobs: list[dict], sent_job_ids: set | None = None) -> str | None:
    """
    Full digest creation flow:
    1. Match jobs to subscriber skill_set
    2. Exclude previously sent jobs
    3. Cap at 10
    4. Generate email body (Gemini with fallback)
    Returns None if zero matches.
    """
    matched = match_jobs_to_skills(jobs, subscriber.get("skill_set", []))

    # Exclude previously sent jobs
    if sent_job_ids:
        matched = [j for j in matched if j.get("id") not in sent_job_ids]

    if not matched:
        logger.info("No matching jobs for subscriber %s", subscriber.get("email"))
        return None

    # Cap at 10
    selected = matched[:10]

    # Try Gemini, fall back to plain text
    try:
        return generate_digest_with_gemini(selected, subscriber.get("email", "Subscriber"))
    except Exception as e:
        logger.warning("Gemini API failed, using fallback: %s", e)
        return generate_digest_fallback(selected)
