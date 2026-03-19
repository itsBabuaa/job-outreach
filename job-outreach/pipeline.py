"""Pipeline Orchestrator: end-to-end job digest flow."""
import logging
import sys
from dataclasses import asdict
from datetime import date

from config import load_config
from scraper import scrape_all_jobs
from db import (
    get_supabase_client, store_jobs, get_active_subscribers,
    get_unsent_jobs_for_subscriber, record_sent_digest,
)
from digest import create_digest
from mailer import send_digests, make_subject

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def run_pipeline() -> None:
    """Execute the full pipeline: scrape → store → digest → mail → record."""
    # 1. Validate config
    try:
        config = load_config()
    except ValueError as e:
        logger.critical("Config validation failed: %s", e)
        sys.exit(1)

    # 2. Initialize DB client
    try:
        client = get_supabase_client()
    except Exception as e:
        logger.critical("Failed to connect to Supabase: %s", e)
        sys.exit(1)

    # 3. Scrape all jobs (with LLM filtering)
    jobs = scrape_all_jobs(config.web_sources, gemini_api_key=config.gemini_api_key)
    if not jobs:
        logger.info("No jobs scraped. Skipping digest generation.")
        return

    # 4. Store jobs in DB
    job_dicts = [asdict(j) for j in jobs]
    new_count = store_jobs(client, job_dicts)
    logger.info("Stored %d new jobs (total scraped: %d)", new_count, len(jobs))

    # 5. Generate digests for each active subscriber
    subscribers = get_active_subscribers(client)
    logger.info("Found %d active subscribers", len(subscribers))

    today = date.today().isoformat()
    subject = make_subject()
    digests_to_send = []

    for sub in subscribers:
        unsent = get_unsent_jobs_for_subscriber(client, sub["id"], sub.get("skill_set", []))
        sent_ids = set()  # unsent already excludes sent jobs
        body = create_digest(sub, unsent, sent_ids)
        if body:
            digests_to_send.append({
                "to_email": sub["email"],
                "subject": subject,
                "body": body,
                "subscriber_id": sub["id"],
                "job_ids": [j["id"] for j in unsent[:10]],
            })

    # 6. Send digests
    if digests_to_send:
        email_payloads = [{"to_email": d["to_email"], "subject": d["subject"], "body": d["body"]} for d in digests_to_send]
        stats = send_digests(email_payloads)
        logger.info("Send stats: %s", stats)

        # 7. Record sent digests
        for d in digests_to_send:
            try:
                record_sent_digest(client, d["subscriber_id"], d["job_ids"], today)
            except Exception as e:
                logger.error("Failed to record digest for %s: %s", d["to_email"], e)
    else:
        logger.info("No digests to send.")


if __name__ == "__main__":
    run_pipeline()
