import html
import smtplib
import ssl
from email.message import EmailMessage
from config import get_settings
from .errors import EmailDeliveryError

def send_otp_email(to: str, name: str, otp: str, purpose: str) -> None:
    settings = get_settings()
    if not settings.smtp_configured or not settings.smtp_from_email:
        raise EmailDeliveryError("Email service is not configured.")
    subject = "Your Passcode verification code"
    action = "verify your email" if purpose == "registration" else "sign in"
    safe_name = html.escape(name)
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    msg["To"] = to
    msg.set_content(f"Hello {name},\n\nUse this code to {action}: {otp}\n\nIt expires in 5 minutes. If you did not request this code, you can ignore this email.")
    msg.add_alternative(
        f"<html><body><p>Hello {safe_name},</p><p>Use this code to {html.escape(action)}:</p>"
        f"<p style='font-size:28px;font-weight:bold;letter-spacing:6px'>{otp}</p>"
        "<p>This code expires in 5 minutes. If you did not request it, ignore this email.</p></body></html>",
        subtype="html",
    )
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls(context=ssl.create_default_context())
            smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(msg)
    except (OSError, smtplib.SMTPException) as exc:
        raise EmailDeliveryError("Could not send the email.") from exc
