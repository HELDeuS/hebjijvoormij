import os
import smtplib
import threading
from email.mime.text import MIMEText


def mail_configured():
    return bool(os.environ.get("SMTP_HOST"))


def send_email(to_email, subject, body):
    """Verstuurt een e-mail via de geconfigureerde SMTP-server.
    Geeft False terug als er geen e-mailadres is of de verzending faalt;
    fouten worden gelogd en breken de app nooit."""
    if not to_email or not mail_configured():
        return False
    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER", "")
    password = os.environ.get("SMTP_PASSWORD", "")
    sender = os.environ.get("SMTP_FROM", user or "hebjijvoormij@localhost")
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to_email
        with smtplib.SMTP(host, port, timeout=15) as server:
            if os.environ.get("SMTP_TLS", "1") not in ("0", "false", "no"):
                server.starttls()
            if user and password:
                server.login(user, password)
            server.send_message(msg)
        print(f"mail: verstuurd aan {to_email}: {subject}", flush=True)
        return True
    except Exception as exc:
        print(f"mail: verzending aan {to_email} faalde: {exc}", flush=True)
        return False


def send_email_async(to_email, subject, body):
    """Verstuurt een e-mail in een achtergronddraad, zodat de
    webrequest nooit op een trage of onbereikbare SMTP-server wacht."""
    thread = threading.Thread(
        target=send_email,
        args=(to_email, subject, body),
        daemon=True,
    )
    thread.start()
