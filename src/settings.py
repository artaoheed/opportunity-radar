"""Central configuration. Everything comes from environment variables so the
same code runs locally (WSL, with a .env loaded via `set -a; source .env`)
and in GitHub Actions (secrets injected as env)."""

import os


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


# --- Postgres (existing baseline-LLMOps instance, separate database) ---
PG_HOST = os.environ.get("PG_HOST", "")            # GCP node external IP
PG_PORT = _int("PG_PORT", 30432)                   # NodePort already opened
PG_USER = os.environ.get("PG_USER", "appuser")
PG_PASSWORD = os.environ.get("PG_PASSWORD", "")
PG_DATABASE = os.environ.get("PG_DATABASE", "opportunity_radar")

# --- Search ---
BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", "")
BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
RESULTS_PER_QUERY = _int("RESULTS_PER_QUERY", 10)
QUERIES_PER_CATEGORY = _int("QUERIES_PER_CATEGORY", 3)

# --- LLM ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
SCORING_BATCH_SIZE = _int("SCORING_BATCH_SIZE", 20)

# --- Email ---
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
SMTP_USER = os.environ.get("SMTP_USER", "")        # gmail address
SMTP_APP_PASSWORD = os.environ.get("SMTP_APP_PASSWORD", "")
DIGEST_TO = os.environ.get("DIGEST_TO", SMTP_USER)
SEND_EMPTY_DIGEST = os.environ.get("SEND_EMPTY_DIGEST", "false").lower() == "true"

# --- Digest ---
DIGEST_SIZE = _int("DIGEST_SIZE", 8)
MIN_SCORE = _int("MIN_SCORE", 40)

# --- Circuit breaker: free-tier ceilings (set conservatively; adjust if the
# provider publishes different numbers for your account) ---
BRAVE_MONTHLY_LIMIT = _int("BRAVE_MONTHLY_LIMIT", 2000)
GROQ_DAILY_LIMIT = _int("GROQ_DAILY_LIMIT", 1000)
GEMINI_DAILY_LIMIT = _int("GEMINI_DAILY_LIMIT", 1500)
QUOTA_STOP_FRACTION = float(os.environ.get("QUOTA_STOP_FRACTION", "0.9"))

TIMEZONE = "Africa/Lagos"


def validate() -> list[str]:
    """Return a list of missing required settings. Empty list means good."""
    missing = []
    for name, value in [
        ("PG_HOST", PG_HOST),
        ("PG_PASSWORD", PG_PASSWORD),
        ("BRAVE_API_KEY", BRAVE_API_KEY),
        ("GROQ_API_KEY", GROQ_API_KEY),
        ("SMTP_USER", SMTP_USER),
        ("SMTP_APP_PASSWORD", SMTP_APP_PASSWORD),
    ]:
        if not value:
            missing.append(name)
    # Gemini is a fallback: warn-level, not fatal. Handled by caller.
    return missing
