"""Score candidates against the profile in config/profile.md.

One LLM call per batch of SCORING_BATCH_SIZE candidates (not one per
candidate) to keep free-tier usage tiny: a normal day is 1-3 calls total.
Groq (Llama 3.3 70B) primary; Gemini (GEMINI_MODEL, default 2.5 Flash)
automatic fallback when Groq is quota-blocked, errors, or has no key."""

import json
import logging
import re
from pathlib import Path

import requests

from . import settings
from .circuit_breaker import QuotaExceeded, QuotaGuard
from .extract import Candidate

log = logging.getLogger(__name__)

CATEGORIES = ("job", "startup", "cfp", "devfund")

PROFILE_PATH = Path(__file__).resolve().parent.parent / "config" / "profile.md"

PROMPT_TEMPLATE = """You are a strict filter for an opportunity digest.

CANDIDATE PROFILE:
{profile}

Below is a JSON array of opportunities found today (index, category, title,
url, snippet). Score each 0-100 for relevance to this profile:
- 80-100: strong direct match (right role family, plausibly attainable, open now)
- 50-79: relevant but imperfect (adjacent role, unclear seniority, tight deadline)
- 20-49: weakly related
- 0-19: irrelevant, expired, spam, or not actually an opportunity (e.g. a blog post about hiring)

Also correct the category if wrong (one of: job, startup, cfp, devfund) and
write a one-line rationale (max 20 words). Use devfund for roles with foreign
donors, development agencies, or their implementing firms/consultancies
running programmes in Nigeria.

Respond with ONLY a JSON array, no markdown fences, no commentary:
[{{"i": 0, "score": 85, "category": "job", "rationale": "..."}}]

CANDIDATES:
{candidates}"""


def _load_profile() -> str:
    return PROFILE_PATH.read_text(encoding="utf-8")


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    # If the model added prose, grab the outermost JSON array.
    m = re.search(r"\[.*\]", text, re.DOTALL)
    return m.group(0) if m else text


def _redact(exc: Exception) -> str:
    """Gemini puts the API key in the URL; never let it reach the logs."""
    msg = str(exc)
    for secret in (settings.GEMINI_API_KEY, settings.GROQ_API_KEY):
        if secret:
            msg = msg.replace(secret, "***")
    return msg


def _call_groq(prompt: str) -> str:
    resp = requests.post(
        settings.GROQ_ENDPOINT,
        headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
        json={
            "model": settings.GROQ_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 2048,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _call_gemini(prompt: str) -> str:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
    )
    resp = requests.post(
        url,
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2048},
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


def _score_batch(guard: QuotaGuard, batch: list[Candidate]) -> None:
    payload = json.dumps(
        [
            {"i": i, "category": c.category, "title": c.title,
             "url": c.url, "snippet": c.snippet}
            for i, c in enumerate(batch)
        ],
        ensure_ascii=False,
    )
    prompt = PROMPT_TEMPLATE.format(profile=_load_profile(), candidates=payload)

    text = None
    # Primary: Groq
    if settings.GROQ_API_KEY:
        try:
            guard.check("groq")
            guard.record("groq")
            text = _call_groq(prompt)
        except QuotaExceeded as exc:
            log.warning("Groq quota-blocked (%s), falling back to Gemini", exc)
        except requests.RequestException as exc:
            log.warning("Groq call failed (%s), falling back to Gemini", _redact(exc))

    # Fallback: Gemini
    if text is None:
        if not settings.GEMINI_API_KEY:
            raise RuntimeError("Groq unavailable and no GEMINI_API_KEY set")
        guard.check("gemini")  # raises QuotaExceeded -> run aborts cleanly
        guard.record("gemini")
        try:
            text = _call_gemini(prompt)
        except requests.RequestException as exc:
            raise RuntimeError(f"Gemini call failed: {_redact(exc)}") from None

    try:
        rows = json.loads(_strip_fences(text))
    except json.JSONDecodeError as exc:
        log.error("LLM returned unparseable JSON: %s\n%s", exc, text[:500])
        raise RuntimeError("scoring output unparseable") from exc

    for row in rows:
        i = row.get("i")
        if not isinstance(i, int) or not (0 <= i < len(batch)):
            continue
        batch[i].score = max(0, min(100, int(row.get("score", 0))))
        cat = row.get("category")
        if cat in CATEGORIES:
            batch[i].category = cat
        batch[i].rationale = str(row.get("rationale", ""))[:200]

    # Anything the model skipped gets score 0 rather than None.
    for c in batch:
        if c.score is None:
            c.score = 0


def score_all(guard: QuotaGuard, candidates: list[Candidate]) -> None:
    """Mutates candidates in place, setting score/rationale/category."""
    size = settings.SCORING_BATCH_SIZE
    for start in range(0, len(candidates), size):
        _score_batch(guard, candidates[start:start + size])
