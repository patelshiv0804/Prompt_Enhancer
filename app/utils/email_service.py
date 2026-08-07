"""
Email service — Send OTP emails for account restoration and password reset.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import get_settings
import logging

logger = logging.getLogger(__name__)

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
        msg["Subject"] = "Prompt Enhancer \u2014 Account Restoration OTP"
        msg["From"] = settings.FROM_EMAIL
        msg["To"] = to_email

        text = (
            f"Your OTP for account restoration is: {otp}\n\n"
            f"This code expires in {settings.OTP_EXPIRE_MINUTES} minutes.\n\n"
            f"If you did not request this, please ignore this email.\n\n"
            f"\u2014 Prompt Enhancer Team"
        )

        html = f"""<html>
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
</html>"""

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


def send_password_reset_otp_email(to_email: str, otp: str) -> None:
    """
    Send a password-reset OTP email with a PromptIQ-branded template.
    Falls back gracefully if SMTP is not configured (OTP is logged for dev).
    """
    try:
        if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            logger.warning(
                f"SMTP not configured. Password-reset OTP for {to_email}: {otp} (logged for dev)"
            )
            return

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "PromptIQ \u2014 Your Password Reset Code"
        msg["From"] = settings.FROM_EMAIL
        msg["To"] = to_email

        text = (
            f"Hi,\n\nWe received a request to reset your PromptIQ account password.\n\n"
            f"Your one-time reset code is: {otp}\n\n"
            f"This code expires in {settings.OTP_EXPIRE_MINUTES} minutes.\n\n"
            f"If you did not request a password reset, please ignore this email.\n\n"
            f"\u2014 The PromptIQ Team"
        )

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>PromptIQ Password Reset</title>
</head>
<body style="margin:0;padding:0;background:#FAFAFC;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#FAFAFC;padding:48px 16px;">
    <tr>
      <td align="center">
        <table width="520" cellpadding="0" cellspacing="0"
               style="background:#fff;border-radius:20px;overflow:hidden;
                      box-shadow:0 4px 24px rgba(23,26,43,0.08);">
          <tr>
            <td style="background:linear-gradient(90deg,#A78BFA,#EC4899,#A78BFA);height:6px;"></td>
          </tr>
          <tr>
            <td style="padding:40px 48px;">
              <p style="margin:0 0 32px;font-size:22px;font-weight:800;
                         letter-spacing:-0.04em;color:#171A2B;">
                Prompt<span style="color:#A78BFA;">IQ</span>
              </p>
              <h1 style="margin:0 0 12px;font-size:20px;font-weight:700;color:#111;
                          letter-spacing:-0.02em;">
                Password Reset Request
              </h1>
              <p style="margin:0 0 28px;font-size:15px;line-height:1.6;color:#555;">
                We received a request to reset the password for your PromptIQ account.
                Use the code below &mdash; it expires in
                <strong>{settings.OTP_EXPIRE_MINUTES} minutes</strong>.
              </p>
              <div style="background:linear-gradient(135deg,rgba(167,139,250,0.1),rgba(236,72,153,0.06));
                           border:1px solid rgba(167,139,250,0.35);border-radius:14px;
                           padding:28px;text-align:center;margin-bottom:28px;">
                <p style="margin:0 0 8px;font-size:11px;font-weight:600;letter-spacing:0.1em;
                            text-transform:uppercase;color:rgba(70,70,76,0.6);">
                  Your one-time code
                </p>
                <span style="font-size:40px;font-weight:800;letter-spacing:10px;
                              color:#A78BFA;font-family:'Courier New',monospace;">
                  {otp}
                </span>
              </div>
              <p style="margin:0 0 32px;font-size:13px;line-height:1.6;color:#888;">
                If you didn&rsquo;t request a password reset, you can safely ignore this email.
                Your password will not be changed until you complete the reset process.
              </p>
              <hr style="border:none;border-top:1px solid #f3f4f6;margin:0 0 24px;" />
              <p style="margin:0;font-size:12px;color:#aaa;line-height:1.6;">
                This email was sent by <strong>PromptIQ Intelligence Systems</strong>.<br/>
                Please do not reply to this message.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.FROM_EMAIL, to_email, msg.as_string())

        logger.info(f"Password-reset OTP email sent to {to_email}")

    except Exception as e:
        logger.error(f"Failed to send password-reset OTP email to {to_email}: {e}")
        # Don't raise — the OTP is still stored; in production add alerting here
