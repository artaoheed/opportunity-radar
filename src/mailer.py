"""Send the digest over Gmail SMTP (app password, SSL on 465)."""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from . import settings

log = logging.getLogger(__name__)


def send(subject: str, text: str, html: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_USER
    msg["To"] = settings.DIGEST_TO
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as s:
        s.login(settings.SMTP_USER, settings.SMTP_APP_PASSWORD)
        s.sendmail(settings.SMTP_USER, [settings.DIGEST_TO], msg.as_string())
    log.info("Digest sent to %s", settings.DIGEST_TO)
