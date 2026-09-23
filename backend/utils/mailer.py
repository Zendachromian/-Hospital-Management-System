import os
import subprocess
from typing import List, Optional, Tuple
from flask import current_app

try:
    import requests
except Exception:
    requests = None


def send_mail(
    subject: str,
    recipients: List[str],
    body: Optional[str] = None,
    html: Optional[str] = None,
    sender: Optional[Tuple[str, str]] = None,
) -> bool:
    """Send an email using Gmail SMTP (primary) with fallback to .eml files.
    Priority:
    1) Gmail SMTP (configured credentials)
    2) Fallback: write .eml file to backend/exports/emails_outbox/
    Returns True if dispatched successfully, False otherwise.
    """
    app = current_app
    sender_name, sender_email = sender or (
        (app.config.get('MAIL_DEFAULT_SENDER')[0] if isinstance(app.config.get('MAIL_DEFAULT_SENDER'), tuple) else 'Hospital Management System'),
        (app.config.get('MAIL_DEFAULT_SENDER')[1] if isinstance(app.config.get('MAIL_DEFAULT_SENDER'), tuple) else app.config.get('MAIL_DEFAULT_SENDER')),
    )

    # 1) Gmail SMTP - Primary method
    app.logger.info(f'🔄 Attempting to send email via Gmail SMTP...')
    try:
        from flask_mail import Mail, Message
        mail = Mail(app)
        msg = Message(
            subject=subject,
            sender=(sender_name, sender_email),
            recipients=recipients,
            body=body or None,
            html=html or None,
        )
        mail.send(msg)
        app.logger.info(f'✅ Email sent via Gmail SMTP to {recipients}')
        return True
    except Exception as e:
        app.logger.error(f'❌ Gmail SMTP send failed: {e}')

    # 2) Fallback: write to outbox
    app.logger.warning(f'📁 Falling back to write .eml file to outbox...')
    try:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        outbox_dir = os.path.join(base_dir, 'exports', 'emails_outbox')
        os.makedirs(outbox_dir, exist_ok=True)
        fname = f"email_{sender_email.replace('@','_')}_{recipients[0].replace('@','_')}.eml"
        path = os.path.join(outbox_dir, fname)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f"From: {sender_name} <{sender_email}>\n")
            f.write(f"To: {', '.join(recipients)}\n")
            f.write(f"Subject: {subject}\n\n")
            if html:
                f.write("[HTML]\n")
                f.write(html)
                f.write("\n\n")
            if body:
                f.write("[TEXT]\n")
                f.write(body)
                f.write("\n")
        app.logger.warning(f'📧 Email saved to outbox: {fname}')
        return True
    except Exception as e:
        app.logger.error(f'💥 Outbox write failed: {e}')
        return False

