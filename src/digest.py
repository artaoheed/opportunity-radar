"""Build the digest email (HTML + plaintext) from scored candidates."""

import html
from datetime import datetime
from zoneinfo import ZoneInfo

from . import settings
from .extract import Candidate

TZ = ZoneInfo(settings.TIMEZONE)

CATEGORY_LABELS = {
    "job": "Job",
    "startup": "Startup role",
    "cfp": "CFP",
    "devfund": "Donor programme (Nigeria)",
}


def select_top(candidates: list[Candidate]) -> list[Candidate]:
    """Pick the digest: up to DEVFUND_SLOTS devfund items first, then fill to
    DIGEST_SIZE with the best remaining of any category. Only items at or
    above MIN_SCORE qualify. Returned in score order."""
    eligible = sorted(
        (c for c in candidates if (c.score or 0) >= settings.MIN_SCORE),
        key=lambda c: c.score or 0,
        reverse=True,
    )
    reserved = [c for c in eligible if c.category == "devfund"][: settings.DEVFUND_SLOTS]
    picked = {c.url_hash for c in reserved}
    rest = [c for c in eligible if c.url_hash not in picked]
    top = reserved + rest[: max(0, settings.DIGEST_SIZE - len(reserved))]
    return sorted(top, key=lambda c: c.score or 0, reverse=True)


def subject(items: list[Candidate]) -> str:
    date = datetime.now(TZ).strftime("%a %d %b")
    return f"Opportunity Radar: {len(items)} for {date}"


def plaintext(items: list[Candidate], quota_line: str) -> str:
    lines = [f"Opportunity Radar: {datetime.now(TZ).strftime('%A %d %B %Y')}", ""]
    for n, c in enumerate(items, 1):
        lines += [
            f"{n}. [{CATEGORY_LABELS.get(c.category, c.category)}] {c.title} (score {c.score})",
            f"   {c.url}",
            f"   {c.rationale}",
            "",
        ]
    lines += ["--", f"Quota: {quota_line}"]
    return "\n".join(lines)


def html_body(items: list[Candidate], quota_line: str) -> str:
    rows = []
    for n, c in enumerate(items, 1):
        rows.append(f"""
        <tr>
          <td style="padding:10px 8px;border-bottom:1px solid #e2e2e2;vertical-align:top;color:#888;">{n}</td>
          <td style="padding:10px 8px;border-bottom:1px solid #e2e2e2;">
            <div style="font-size:11px;letter-spacing:1px;color:#0a7d4f;text-transform:uppercase;">
              {CATEGORY_LABELS.get(c.category, c.category)} · score {c.score}
            </div>
            <a href="{html.escape(c.url, quote=True)}"
               style="font-size:15px;color:#1a1a1a;font-weight:600;text-decoration:none;">
              {html.escape(c.title)}
            </a>
            <div style="font-size:13px;color:#555;margin-top:3px;">{html.escape(c.rationale)}</div>
          </td>
        </tr>""")
    date = datetime.now(TZ).strftime("%A %d %B %Y")
    return f"""<!DOCTYPE html>
<html><body style="margin:0;padding:0;background:#f6f6f4;font-family:Segoe UI,Arial,sans-serif;">
  <div style="max-width:640px;margin:0 auto;padding:24px 16px;">
    <h1 style="font-size:20px;margin:0 0 4px;">Opportunity Radar</h1>
    <div style="font-size:13px;color:#777;margin-bottom:16px;">{date} · top {len(items)}</div>
    <table style="width:100%;border-collapse:collapse;background:#fff;border-radius:6px;">
      {''.join(rows)}
    </table>
    <div style="font-size:11px;color:#999;margin-top:14px;">Quota: {html.escape(quota_line)}</div>
  </div>
</body></html>"""
