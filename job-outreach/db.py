"""Database module for Supabase interactions."""
import os
import logging
from supabase import create_client, Client

logger = logging.getLogger(__name__)


def get_supabase_client() -> Client:
    """Initialize and return Supabase client from env vars."""
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY", "")
    return create_client(url, key)


def store_jobs(client: Client, jobs: list[dict]) -> int:
    """Upsert jobs into job_listings table. Returns count of new jobs."""
    if not jobs:
        return 0
    rows = []
    for j in jobs:
        row = {
            "url": j["url"],
            "title": j["title"],
            "company": j["company"],
            "tags": j.get("tags", []),
            "date_posted": j.get("date_posted") or None,
            "source": j.get("source", ""),
            "salary": j.get("salary", ""),
            "requirements": j.get("requirements", ""),
            "summary": j.get("summary", ""),
        }
        rows.append(row)
    result = client.table("job_listings").upsert(rows, on_conflict="url").execute()
    return len(result.data) if result.data else 0


def get_active_subscribers(client: Client) -> list[dict]:
    """Return all subscribers where status = 'active'."""
    result = client.table("subscribers").select("*").eq("status", "active").execute()
    return result.data or []


def get_unsent_jobs_for_subscriber(client: Client, subscriber_id: str, skill_set: list[str]) -> list[dict]:
    """Return jobs not previously sent to this subscriber."""
    # Get IDs of jobs already sent to this subscriber
    sent = (
        client.table("sent_digest_jobs")
        .select("job_id, sent_digests!inner(subscriber_id)")
        .eq("sent_digests.subscriber_id", subscriber_id)
        .execute()
    )
    sent_job_ids = {row["job_id"] for row in (sent.data or [])}

    # Get all jobs
    all_jobs = client.table("job_listings").select("*").execute()
    jobs = all_jobs.data or []

    # Filter out already-sent jobs
    return [j for j in jobs if j["id"] not in sent_job_ids]


def record_sent_digest(client: Client, subscriber_id: str, job_ids: list[str], date_sent: str) -> None:
    """Record which jobs were sent to which subscriber."""
    digest = client.table("sent_digests").insert({
        "subscriber_id": subscriber_id,
        "date_sent": date_sent,
        "job_count": len(job_ids),
    }).execute()
    digest_id = digest.data[0]["id"]
    if job_ids:
        junction_rows = [{"digest_id": digest_id, "job_id": jid} for jid in job_ids]
        client.table("sent_digest_jobs").insert(junction_rows).execute()


# --- Subscriber CRUD ---

def add_subscriber(client: Client, email: str, skill_set: list[str]) -> dict:
    """Add a new subscriber. Raises on duplicate email."""
    result = client.table("subscribers").insert({
        "email": email,
        "skill_set": skill_set,
    }).execute()
    return result.data[0]


def update_subscriber(client: Client, subscriber_id: str, **fields) -> dict:
    """Update subscriber fields (email, status, skill_set)."""
    result = client.table("subscribers").update(fields).eq("id", subscriber_id).execute()
    return result.data[0] if result.data else {}


def delete_subscriber(client: Client, subscriber_id: str) -> None:
    """Delete a subscriber record."""
    client.table("subscribers").delete().eq("id", subscriber_id).execute()


def get_all_subscribers(client: Client) -> list[dict]:
    """Return all subscribers (for admin dashboard)."""
    result = client.table("subscribers").select("*").execute()
    return result.data or []


def get_jobs_paginated(client: Client, page: int, per_page: int) -> tuple[list[dict], int]:
    """Return paginated job listings and total count."""
    page = max(1, page)
    start = (page - 1) * per_page
    end = start + per_page - 1
    result = client.table("job_listings").select("*", count="exact").range(start, end).execute()
    return result.data or [], result.count or 0


def get_digest_log(client: Client, page: int, per_page: int) -> tuple[list[dict], int]:
    """Return paginated digest send history."""
    page = max(1, page)
    start = (page - 1) * per_page
    end = start + per_page - 1
    result = (
        client.table("sent_digests")
        .select("*, subscribers(email)", count="exact")
        .range(start, end)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or [], result.count or 0
