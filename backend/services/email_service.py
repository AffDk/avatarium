"""Email notification service — sends video-ready emails via SMTP."""

import logging
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from backend.config import settings

logger = logging.getLogger(__name__)


def _log(msg: str, *args: object) -> None:
    formatted = msg % args if args else msg
    logger.info(formatted)
    print(f"[EMAIL] {formatted}", file=sys.stderr, flush=True)


def send_video_ready_email(
    recipient_email: str,
    recipient_name: str,
    project_title: str,
    project_id: str,
) -> None:
    """Send a video-ready notification email with a download link.

    Silently logs and returns if SMTP is not configured, so unconfigured
    deployments don't cause pipeline failures.
    """
    if not settings.smtp_user or not settings.smtp_password:
        _log(
            "SMTP not configured — skipping email to %s for project %s",
            recipient_email,
            project_id,
        )
        return

    video_url = f"{settings.app_base_url.rstrip('/')}/projects/{project_id}"
    from_addr = settings.smtp_from or settings.smtp_user

    subject = f"Your Avatarium video is ready — {project_title}"

    html_body = f"""\
<!DOCTYPE html>
<html lang="en">
<body style="font-family: sans-serif; color: #222; max-width: 520px; margin: 0 auto; padding: 24px;">
  <h2 style="color: #6c47ff;">Your video is ready! 🎬</h2>
  <p>Hi {recipient_name},</p>
  <p>
    Your Avatarium project <strong>{project_title}</strong> has finished generating.
    You can view and download your video by visiting your project page:
  </p>
  <p style="text-align: center; margin: 32px 0;">
    <a href="{video_url}"
       style="background: #6c47ff; color: #fff; text-decoration: none;
              padding: 14px 28px; border-radius: 6px; font-size: 16px;">
      View &amp; Download Video
    </a>
  </p>
  <p style="font-size: 13px; color: #666;">
    If the button above doesn't work, paste this link into your browser:<br>
    <a href="{video_url}">{video_url}</a>
  </p>
  <hr style="border: none; border-top: 1px solid #eee; margin: 32px 0;">
  <p style="font-size: 12px; color: #aaa;">Avatarium · automated notification</p>
</body>
</html>
"""

    text_body = (
        f"Hi {recipient_name},\n\n"
        f"Your Avatarium project '{project_title}' has finished generating.\n\n"
        f"View and download your video here:\n{video_url}\n\n"
        "— Avatarium"
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = recipient_email
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.sendmail(from_addr, [recipient_email], msg.as_string())
        _log(
            "Video-ready email sent to %s for project %s",
            recipient_email,
            project_id,
        )
    except Exception as exc:
        logger.error(
            "Failed to send video-ready email to %s for project %s: %s",
            recipient_email,
            project_id,
            exc,
        )
