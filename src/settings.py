"""Central configuration. Everything comes from environment variables so the
same code runs locally (WSL, with a .env loaded via `set -a; source .env`)
and in GitHub Actions (secrets injected as env)."""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _int(name: str, default: int) -> int:
    # Unset secrets arrive in Actions as empty strings, not missing keys.
    raw = os.environ.get(name, "").strip()
    return int(raw) if raw else default


def _str(name: str, default: str = "") -> str:
    return os.environ.get(name, "").strip() or default


# --- State store: SQLite file committed back to the repo by the workflow ---
DB_PATH = Path(_str("DB_PATH", str(REPO_ROOT / "data" / "radar.db")))

# --- Search ---
BRAVE_API_KEY = _str("BRAVE_API_KEY")              # optional: empty -> DuckDuckGo only
BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
RESULTS_PER_QUERY = _int("RESULTS_PER_QUERY", 10)
QUERIES_PER_CATEGORY = _int("QUERIES_PER_CATEGORY", 3)

# ReliefWeb jobs API (optional). Needs a pre-approved appname since Nov 2025.
RELIEFWEB_APPNAME = _str("RELIEFWEB_APPNAME")
RELIEFWEB_ENDPOINT = "https://api.reliefweb.int/v2/jobs"
RELIEFWEB_LIMIT = _int("RELIEFWEB_LIMIT", 30)

# --- LLM ---
GROQ_API_KEY = _str("GROQ_API_KEY")
GROQ_MODEL = _str("GROQ_MODEL", "openai/gpt-oss-120b")   # llama-3.3-70b retired Aug 2026
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_API_KEY = _str("GEMINI_API_KEY")
GEMINI_MODEL = _str("GEMINI_MODEL", "gemini-2.5-flash")   # 2.0 Flash is retired
SCORING_BATCH_SIZE = _int("SCORING_BATCH_SIZE", 20)

# --- Email ---
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
SMTP_USER = _str("SMTP_USER")                      # gmail address
SMTP_APP_PASSWORD = _str("SMTP_APP_PASSWORD")
DIGEST_TO = _str("DIGEST_TO", SMTP_USER)
SEND_EMPTY_DIGEST = _str("SEND_EMPTY_DIGEST", "false").lower() == "true"

# --- Digest ---
DIGEST_SIZE = _int("DIGEST_SIZE", 8)
MIN_SCORE = _int("MIN_SCORE", 40)
# Slots reserved for foreign-funded Nigeria programme roles, so they are not
# crowded out by engineering roles (or vice versa). Unused slots fall back to
# the best remaining candidates of any category.
DEVFUND_SLOTS = _int("DEVFUND_SLOTS", 3)

# --- Circuit breaker: quota ceilings ---
BRAVE_MONTHLY_LIMIT = _int("BRAVE_MONTHLY_LIMIT", 2000)
GROQ_DAILY_LIMIT = _int("GROQ_DAILY_LIMIT", 1000)
GEMINI_DAILY_LIMIT = _int("GEMINI_DAILY_LIMIT", 1500)
QUOTA_STOP_FRACTION = float(_str("QUOTA_STOP_FRACTION", "0.9"))

TIMEZONE = "Africa/Lagos"


def validate() -> list[str]:
    """Return a list of missing required settings. Empty list means good."""
    missing = []
    for name, value in [
        ("SMTP_USER", SMTP_USER),
        ("SMTP_APP_PASSWORD", SMTP_APP_PASSWORD),
    ]:
        if not value:
            missing.append(name)
    if not (GROQ_API_KEY or GEMINI_API_KEY):
        missing.append("GROQ_API_KEY or GEMINI_API_KEY")
    return missing
