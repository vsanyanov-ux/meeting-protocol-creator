import os
import smtplib
from email.message import EmailMessage
import logging

def send_email(recipient_email: str, subject: str, body: str, attachment_path: str):
    """Send an email with an attachment."""
    # Loading details from environment variables
    # (These will be set in the .env and loaded by main.py)
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = smtp_user
    msg['To'] = recipient_email
    msg.set_content(body)

    # Attach the file
    with open(attachment_path, 'rb') as f:
        file_data = f.read()
        file_name = os.path.basename(attachment_path)
        msg.add_attachment(file_data, maintype='application', subtype='vnd.openxmlformats-officedocument.wordprocessingml.document', filename=file_name)

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
            logging.info(f"Email successfully sent to {recipient_email}")
            return True
    except Exception as e:
        logging.error(f"Failed to send email: {e}")
        return False
