"""
Email service — Send OTP emails for account restoration.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import get_settings
from app.core.logger import logger

settings = get_settings()


def send_otp_email(to_email: str, otp: str) -> None:
    """
    Send OTP verification email.
    Called as a background task from the restore endpoint.
    Falls back gracefully if SMTP is not configured.
    """
    try:
        if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            logger.warning(
                f"SMTP not configured. OTP for {to_email}: {otp} (logged for dev)"
            )
            return

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Prompt Enhancer — Account Restoration OTP"
        msg["From"] = settings.FROM_EMAIL
        msg["To"] = to_email

        # Plain text version
        text = f"""
Your OTP for account restoration is: {otp}

This code expires in {settings.OTP_EXPIRE_MINUTES} minutes.

If you did not request this, please ignore this email.

— Prompt Enhancer Team
"""

        # HTML version
        html = f"""
<html>
<body style="font-family: 'Segoe UI', sans-serif; background: #f5f5f5; padding: 40px;">
  <div style="max-width: 480px; margin: 0 auto; background: #fff; border-radius: 12px;
              padding: 40px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
    <h2 style="color: #1a1a2e; margin-bottom: 8px;">Account Restoration</h2>
    <p style="color: #555; line-height: 1.6;">
      Use the following OTP to restore your Prompt Enhancer account:
    </p>
    <div style="background: #f0f4ff; border-radius: 8px; padding: 20px; text-align: center;
                margin: 24px 0;">
      <span style="font-size: 32px; font-weight: 700; letter-spacing: 6px; color: #3b82f6;">
        {otp}
      </span>
    </div>
    <p style="color: #888; font-size: 13px;">
      This code expires in {settings.OTP_EXPIRE_MINUTES} minutes.
      If you did not request this, please ignore this email.
    </p>
  </div>
</body>
</html>
"""

        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.FROM_EMAIL, to_email, msg.as_string())

        logger.info(f"OTP email sent to {to_email}")

    except Exception as e:
        logger.error(f"Failed to send OTP email to {to_email}: {e}")
        # Don't raise — the OTP is still stored and usable
        # In production, you'd want alerting here
