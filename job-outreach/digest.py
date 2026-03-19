"""Digest Generator: matches jobs to subscribers and generates email content."""
import logging
import google.generativeai as genai

logger = logging.getLogger(__name__)

FOOTER = """
<tr><td style="padding:30px 20px;text-align:center;border-top:1px solid #eee;">
  <p style="margin:0;color:#999;font-size:12px;">POWERED BY <strong style="color:#333;">Babuaa</strong></p>
</td></tr>
"""

EMAIL_WRAPPER_START = """<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f4f4f4;font-family:Arial,Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f4;padding:20px 0;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
<tr><td style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);padding:30px 20px;text-align:center;">
  <h1 style="margin:0;color:#fff;font-size:24px;">🚀 Your Daily Job Digest</h1>
  <p style="margin:8px 0 0;color:rgba(255,255,255,0.85);font-size:14px;">India · Remote · Entry Level (0-2 yrs)</p>
</td></tr>
"""

EMAIL_WRAPPER_END = """
""" + FOOTER + """
</table></td></tr></table></body></html>"""


def _job_card_html(index: int, job: dict) -> str:
    """Render a single job as an HTML card."""
    location = job.get("location", "") or "Remote"
    salary = job.get("salary", "") or "Not disclosed"
    experience = job.get("experience", "") or "Not specified"

    tags_html = ""
    if job.get("tags"):
        tags_html = " ".join(
            f'<span style="display:inline-block;background:#eef2ff;color:#4f46e5;padding:2px 8px;border-radius:12px;font-size:11px;margin:2px;">{t}</span>'
            for t in job["tags"][:5]
        )

    summary = job.get("summary", "")
    if len(summary) > 150:
        summary = summary[:150] + "..."

    return f'''
<tr><td style="padding:16px 20px;border-bottom:1px solid #f0f0f0;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td>
      <h3 style="margin:0 0 4px;color:#1a1a2e;font-size:16px;">{index}. {job.get('title', '')}</h3>
      <p style="margin:0 0 8px;color:#555;font-size:13px;">🏢 {job.get('company', '')} &nbsp;·&nbsp; 📍 {location}</p>
      <table cellpadding="0" cellspacing="0" style="margin-bottom:8px;">
        <tr>
          <td style="background:#f0fdf4;color:#166534;padding:3px 10px;border-radius:4px;font-size:12px;margin-right:8px;">💰 {salary}</td>
          <td style="width:8px;"></td>
          <td style="background:#fef3c7;color:#92400e;padding:3px 10px;border-radius:4px;font-size:12px;">📋 {experience}</td>
        </tr>
      </table>
      {f'<p style="margin:0 0 8px;color:#666;font-size:13px;">{summary}</p>' if summary else ''}
      {f'<div style="margin-bottom:8px;">{tags_html}</div>' if tags_html else ''}
      <a href="{job.get('url', '#')}" style="display:inline-block;background:#667eea;color:#fff;padding:8px 20px;border-radius:5px;text-decoration:none;font-size:13px;font-weight:bold;">Apply Now →</a>
    </td></tr>
  </table>
</td></tr>'''


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
    """Call Gemini API to compose HTML email body. Raises on API error."""
    job_cards = "".join(_job_card_html(i, j) for i, j in enumerate(jobs, 1))

    prompt = (
        f"Rewrite the following job listings into a warm, encouraging intro paragraph (2-3 sentences) "
        f"for {subscriber_name}. Mention that these are India-friendly remote jobs for entry-level candidates. "
        f"Return ONLY the intro paragraph as plain text, no HTML:\n\n"
        + "\n".join(f"- {j['title']} at {j['company']}" for j in jobs)
    )
    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(prompt)
    intro = response.text.strip()

    intro_html = f'<tr><td style="padding:20px;color:#444;font-size:14px;line-height:1.6;">{intro}</td></tr>'
    count_html = f'<tr><td style="padding:0 20px 10px;"><p style="margin:0;color:#888;font-size:12px;font-weight:bold;text-transform:uppercase;letter-spacing:1px;">📋 {len(jobs)} Jobs Found</p></td></tr>'

    return EMAIL_WRAPPER_START + intro_html + count_html + job_cards + EMAIL_WRAPPER_END


def generate_digest_fallback(jobs: list[dict]) -> str:
    """HTML fallback template when Gemini is unavailable."""
    job_cards = "".join(_job_card_html(i, j) for i, j in enumerate(jobs, 1))

    intro_html = f'''<tr><td style="padding:20px;color:#444;font-size:14px;line-height:1.6;">
        Here are today's top {len(jobs)} job picks matched to your skills. All positions are India-friendly and suited for 0-2 years of experience.
    </td></tr>'''
    count_html = f'<tr><td style="padding:0 20px 10px;"><p style="margin:0;color:#888;font-size:12px;font-weight:bold;text-transform:uppercase;letter-spacing:1px;">📋 {len(jobs)} Jobs Found</p></td></tr>'

    return EMAIL_WRAPPER_START + intro_html + count_html + job_cards + EMAIL_WRAPPER_END


def create_digest(subscriber: dict, jobs: list[dict], sent_job_ids: set | None = None) -> str | None:
    """Full digest creation flow."""
    matched = match_jobs_to_skills(jobs, subscriber.get("skill_set", []))

    if sent_job_ids:
        matched = [j for j in matched if j.get("id") not in sent_job_ids]

    if not matched:
        logger.info("No matching jobs for subscriber %s", subscriber.get("email"))
        return None

    selected = matched[:10]

    try:
        return generate_digest_with_gemini(selected, subscriber.get("email", "Subscriber"))
    except Exception as e:
        logger.warning("Gemini API failed, using fallback: %s", e)
        return generate_digest_fallback(selected)
