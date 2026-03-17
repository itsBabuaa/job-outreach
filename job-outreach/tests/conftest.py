"""Shared fixtures and Hypothesis strategies for Job Digest Mailer tests."""
import pytest
from hypothesis import strategies as st


# --- Hypothesis strategies ---

job_listing_strategy = st.fixed_dictionaries({
    "title": st.text(min_size=1, max_size=100).filter(lambda s: s.strip()),
    "company": st.text(min_size=1, max_size=80).filter(lambda s: s.strip()),
    "url": st.from_regex(r"https://[a-z]{3,12}\.com/jobs/[a-z0-9]{1,8}", fullmatch=True),
    "tags": st.lists(st.text(min_size=1, max_size=30).filter(lambda s: s.strip()), min_size=0, max_size=5),
    "date_posted": st.dates().map(lambda d: d.isoformat()),
    "source": st.sampled_from(["remotive", "weworkremotely", "custom"]),
    "salary": st.text(max_size=60),
    "requirements": st.text(max_size=200),
    "summary": st.text(max_size=300),
})

subscriber_strategy = st.fixed_dictionaries({
    "email": st.from_regex(r"[a-z]{3,8}@[a-z]{3,8}\.(com|org|io)", fullmatch=True),
    "status": st.sampled_from(["active", "inactive"]),
    "skill_set": st.lists(st.text(min_size=1, max_size=30).filter(lambda s: s.strip()), min_size=1, max_size=5),
})

config_env_vars_strategy = st.fixed_dictionaries({
    "GMAIL_USER": st.from_regex(r"[a-z]{3,8}@gmail\.com", fullmatch=True),
    "GMAIL_APP_PASSWORD": st.text(min_size=1, max_size=20).filter(lambda s: s.strip()),
    "GEMINI_API_KEY": st.text(min_size=1, max_size=40).filter(lambda s: s.strip()),
    "SUPABASE_URL": st.from_regex(r"https://[a-z]{4,10}\.supabase\.co", fullmatch=True),
    "SUPABASE_KEY": st.text(min_size=1, max_size=40).filter(lambda s: s.strip()),
})

REQUIRED_ENV_VARS = [
    "GMAIL_USER",
    "GMAIL_APP_PASSWORD",
    "GEMINI_API_KEY",
    "SUPABASE_URL",
    "SUPABASE_KEY",
]
