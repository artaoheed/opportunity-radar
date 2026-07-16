"""Query templates per category, rotated daily to vary sources while staying
inside the Brave quota. Budget: QUERIES_PER_CATEGORY x 3 categories per day
(default 9/day = ~270/month, well under the 2,000/month Brave ceiling)."""

from datetime import datetime
from zoneinfo import ZoneInfo

from .. import settings

TZ = ZoneInfo(settings.TIMEZONE)

# Sources deliberately biased toward places that skip mainstream job boards:
# ATS domains (Greenhouse/Lever/Ashby), VC portfolio job boards, CFP trackers.
TEMPLATES: dict[str, list[str]] = {
    "job": [
        'site:boards.greenhouse.io "DevOps engineer" remote',
        'site:jobs.lever.co "platform engineer" remote',
        'site:jobs.ashbyhq.com MLOps OR "ML platform" engineer',
        '"site reliability engineer" hiring remote worldwide',
        '"DevOps engineer" hiring remote Africa OR Nigeria',
        'site:boards.greenhouse.io "infrastructure engineer" remote',
        '"technical program manager" infrastructure hiring remote',
    ],
    "startup": [
        '"founding engineer" infrastructure OR platform OR DevOps',
        'YC W26 OR S26 startup hiring "infrastructure engineer"',
        'seed stage startup "first DevOps hire" OR "first infrastructure hire"',
        '"early stage" startup hiring SRE OR "platform engineer" remote',
        'site:jobs.ashbyhq.com founding OR "employee #1" engineer',
        'a16z OR sequoia portfolio jobs "DevOps" OR "platform engineer"',
        '"we just raised" hiring "DevOps" OR "infrastructure"',
    ],
    "cfp": [
        '"call for papers" DevOps OR SRE conference 2026',
        '"call for proposals" cloud native OR Kubernetes 2026',
        'DevOpsDays 2026 "CFP" open',
        '"call for speakers" MLOps OR "platform engineering" 2026',
        'KubeCon OR "cloud native" 2026 "call for proposals"',
        'tech conference Africa 2026 "call for papers"',
        '"CFP closes" DevOps OR MLOps OR SRE',
    ],
}


def todays_queries() -> list[tuple[str, str]]:
    """Return [(category, query), ...] for today, rotated by day-of-year so
    the same run on the same day is deterministic and consecutive days
    hit different templates."""
    day = datetime.now(TZ).timetuple().tm_yday
    n = settings.QUERIES_PER_CATEGORY
    out: list[tuple[str, str]] = []
    for category, templates in TEMPLATES.items():
        for i in range(n):
            out.append((category, templates[(day + i) % len(templates)]))
    return out
