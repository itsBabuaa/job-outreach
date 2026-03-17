"""Centralized configuration and validation for Job Digest Mailer."""
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv


@dataclass
class AppConfig:
    gmail_user: str = ""
    gmail_app_password: str = ""
    gemini_api_key: str = ""
    supabase_url: str = ""
    supabase_key: str = ""
    web_sources: list[dict] = field(default_factory=list)
    daily_email_limit: int = 500


REQUIRED_FIELDS = [
    ("gmail_user", "GMAIL_USER"),
    ("gmail_app_password", "GMAIL_APP_PASSWORD"),
    ("gemini_api_key", "GEMINI_API_KEY"),
    ("supabase_url", "SUPABASE_URL"),
    ("supabase_key", "SUPABASE_KEY"),
]


def load_config() -> AppConfig:
    """Load config from environment variables via python-dotenv."""
    load_dotenv()
    config = AppConfig(
        gmail_user=os.getenv("GMAIL_USER", ""),
        gmail_app_password=os.getenv("GMAIL_APP_PASSWORD", ""),
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        supabase_url=os.getenv("SUPABASE_URL", ""),
        supabase_key=os.getenv("SUPABASE_KEY", ""),
    )
    validate_config(config)
    return config


def validate_config(config: AppConfig) -> None:
    """Validate all required fields are non-empty. Raises ValueError naming missing vars."""
    missing = [
        env_var
        for attr, env_var in REQUIRED_FIELDS
        if not getattr(config, attr, "").strip()
    ]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
