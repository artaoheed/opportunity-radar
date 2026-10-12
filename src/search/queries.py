"""Query templates per category, rotated daily to vary sources while staying
inside the Brave quota. Budget: QUERIES_PER_CATEGORY x 4 categories per run
(default 12/run, every 2 days = ~180/month, well under the 2,000/month
Brave ceiling)."""

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
        '"technical program manager" OR "program lead" platform OR infrastructure hiring',
        'site:boards.greenhouse.io "developer relations" OR "developer advocate"',
        '"DevRel" OR "developer advocate" hiring remote 2026',
        'site:jobs.lever.co "program manager" technical OR engineering',
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
    # Foreign donors and their implementing firms running Nigeria programmes.
    # These roles value state-level delivery experience (3MTT SPM/CM ops) and
    # are often paid in foreign currency. Site-scoped where the firm posts
    # its own vacancies; broader phrasing catches the rest.
    "devfund": [
        'Nigeria "project manager" digital skills GIZ OR FCDO OR "European Union" vacancy',
        'site:jobs.giz.de Nigeria',
        'Nigeria "programme manager" OR "project coordinator" digital economy donor-funded',
        'site:devex.com Nigeria "project manager" OR "team leader" digital',
        '"Nigeria" "state coordinator" OR "state lead" programme vacancy World Bank OR UNDP OR FCDO',
        'Nigeria vacancy DAI OR Palladium OR "Adam Smith International" OR Cowater digital',
        'Nigeria consultant "expert roster" OR "call for experts" digital skills OR "digital economy"',
        'site:unjobs.org Nigeria "project manager" OR "programme analyst" digital',
        '"Nigeria" "team leader" OR "key expert" EU-funded digital OR skills tender',
        'site:reliefweb.int/job Nigeria "project manager" OR "programme manager"',
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
