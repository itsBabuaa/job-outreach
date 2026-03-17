"""Flask Admin Dashboard for Job Digest Mailer."""
import sys
import os
import logging

# Add parent dir to path so we can import sibling modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flask import Flask, render_template, request, redirect, url_for, flash
from dotenv import load_dotenv
from db import (
    get_supabase_client, get_all_subscribers, add_subscriber,
    update_subscriber, delete_subscriber, get_jobs_paginated, get_digest_log,
)

load_dotenv()
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")


def _get_client():
    """Get Supabase client, raising on failure."""
    return get_supabase_client()


@app.route("/")
def index():
    try:
        _get_client()
        return render_template("index.html")
    except Exception as e:
        return render_template("error.html", error=str(e))


@app.route("/subscribers")
def subscribers():
    try:
        client = _get_client()
        subs = get_all_subscribers(client)
        return render_template("subscribers.html", subscribers=subs)
    except Exception as e:
        return render_template("error.html", error=str(e))


@app.route("/subscribers", methods=["POST"])
def add_subscriber_route():
    try:
        client = _get_client()
        email = request.form.get("email", "").strip()
        skills = [s.strip() for s in request.form.get("skill_set", "").split(",") if s.strip()]
        if not email:
            flash("Email is required.")
            return redirect(url_for("subscribers"))
        add_subscriber(client, email, skills)
        flash("Subscriber added.")
        return redirect(url_for("subscribers"))
    except Exception as e:
        flash(f"Error: {e}")
        return redirect(url_for("subscribers"))


@app.route("/subscribers/<sub_id>/edit", methods=["GET"])
def edit_subscriber_form(sub_id):
    try:
        client = _get_client()
        subs = get_all_subscribers(client)
        sub = next((s for s in subs if s["id"] == sub_id), None)
        if not sub:
            flash("Subscriber not found.")
            return redirect(url_for("subscribers"))
        return render_template("edit_subscriber.html", subscriber=sub)
    except Exception as e:
        return render_template("error.html", error=str(e))


@app.route("/subscribers/<sub_id>/edit", methods=["POST"])
def edit_subscriber_route(sub_id):
    try:
        client = _get_client()
        email = request.form.get("email", "").strip()
        status = request.form.get("status", "active")
        skills = [s.strip() for s in request.form.get("skill_set", "").split(",") if s.strip()]
        update_subscriber(client, sub_id, email=email, status=status, skill_set=skills)
        flash("Subscriber updated.")
        return redirect(url_for("subscribers"))
    except Exception as e:
        flash(f"Error: {e}")
        return redirect(url_for("subscribers"))


@app.route("/subscribers/<sub_id>/deactivate", methods=["POST"])
def deactivate_subscriber_route(sub_id):
    try:
        client = _get_client()
        update_subscriber(client, sub_id, status="inactive")
        flash("Subscriber deactivated.")
    except Exception as e:
        flash(f"Error: {e}")
    return redirect(url_for("subscribers"))


@app.route("/subscribers/<sub_id>/delete", methods=["POST"])
def delete_subscriber_route(sub_id):
    try:
        client = _get_client()
        delete_subscriber(client, sub_id)
        flash("Subscriber deleted.")
    except Exception as e:
        flash(f"Error: {e}")
    return redirect(url_for("subscribers"))


@app.route("/jobs")
def jobs():
    try:
        client = _get_client()
        page = max(1, int(request.args.get("page", 1)))
        per_page = 20
        job_list, total = get_jobs_paginated(client, page, per_page)
        total_pages = max(1, (total + per_page - 1) // per_page)
        return render_template("jobs.html", jobs=job_list, page=page, total_pages=total_pages)
    except Exception as e:
        return render_template("error.html", error=str(e))


@app.route("/digests")
def digests():
    try:
        client = _get_client()
        page = max(1, int(request.args.get("page", 1)))
        per_page = 20
        digest_list, total = get_digest_log(client, page, per_page)
        total_pages = max(1, (total + per_page - 1) // per_page)
        return render_template("digests.html", digests=digest_list, page=page, total_pages=total_pages)
    except Exception as e:
        return render_template("error.html", error=str(e))


@app.route("/trigger", methods=["POST"])
def trigger_pipeline():
    try:
        from pipeline import run_pipeline
        run_pipeline()
        flash("Pipeline triggered successfully.")
    except Exception as e:
        flash(f"Pipeline error: {e}")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
