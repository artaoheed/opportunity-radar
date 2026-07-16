"""Quota guard. Every external API call goes through this.

Rule: if a call would push a provider past QUOTA_STOP_FRACTION (default 90%)
of its free-tier ceiling, the call is refused. The caller decides whether to
fall back (Brave -> DuckDuckGo, Groq -> Gemini) or abort the run. Nothing
ever silently crosses a free quota."""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from . import db, settings

log = logging.getLogger(__name__)

TZ = ZoneInfo(settings.TIMEZONE)


class QuotaExceeded(Exception):
    def __init__(self, provider: str, used: int, limit: int):
        self.provider = provider
        self.used = used
        self.limit = limit
        super().__init__(f"{provider}: {used}/{limit} used, refusing further calls")


class QuotaGuard:
    """provider -> (limit, period). period is 'month' or 'day'."""

    PROVIDERS = {
        "brave": (settings.BRAVE_MONTHLY_LIMIT, "month"),
        "groq": (settings.GROQ_DAILY_LIMIT, "day"),
        "gemini": (settings.GEMINI_DAILY_LIMIT, "day"),
    }

    def __init__(self, conn):
        self.conn = conn

    @staticmethod
    def _period_key(period: str) -> str:
        now = datetime.now(TZ)
        return now.strftime("%Y-%m") if period == "month" else now.strftime("%Y-%m-%d")

    def check(self, provider: str) -> None:
        """Raise QuotaExceeded if one more call would breach the stop line."""
        limit, period = self.PROVIDERS[provider]
        used = db.get_usage(self.conn, provider, self._period_key(period))
        if used + 1 > limit * settings.QUOTA_STOP_FRACTION:
            raise QuotaExceeded(provider, used, limit)

    def record(self, provider: str, by: int = 1) -> None:
        _, period = self.PROVIDERS[provider]
        db.increment_usage(self.conn, provider, self._period_key(period), by)

    def status_line(self) -> str:
        parts = []
        for provider, (limit, period) in self.PROVIDERS.items():
            used = db.get_usage(self.conn, provider, self._period_key(period))
            parts.append(f"{provider} {used}/{limit} ({period})")
        return ", ".join(parts)
