import os
import smtplib
from email.message import EmailMessage
from email.utils import make_msgid, formatdate
from loguru import logger

def send_email(recipient_email: str, subject: str, body: str, attachment_path: str):
    """Send an email with an attachment and HTML alternative."""
    # Loading details from environment variables
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    display_name = os.getenv("SMTP_DISPLAY_NAME", "Meeting Protocol Creator")

    msg = EmailMessage()
    msg['Subject'] = f"Документ: {subject.split(':')[-1].strip()}"
    msg['From'] = f"{display_name} <{smtp_user}>"
    msg['To'] = recipient_email
    msg['Message-ID'] = make_msgid()
    msg['Date'] = formatdate(localtime=True)
    
    # Anti-spam headers
    msg['X-Priority'] = '3'
    msg['X-Mailer'] = 'Mail-Service'
    msg['Precedence'] = 'list'
    msg['List-Unsubscribe'] = f'<mailto:{smtp_user}>'

    # Plain text version
    msg.set_content(body)

    # Simple HTML version
    html_body = f"""
    <html>
        <body style="font-family: sans-serif;">
            <p>Здравствуйте!</p>
            <p>Файл готов и прикреплен к письму.</p>
            <p>---<br>{body}</p>
        </body>
    </html>
    """
    msg.add_alternative(html_body, subtype='html')

    # Attach the file
    if attachment_path and os.path.exists(attachment_path):
        with open(attachment_path, 'rb') as f:
            file_data = f.read()
            file_name = os.path.basename(attachment_path)
            # Use specific MIME for DOCX
            msg.add_attachment(
                file_data, 
                maintype='application', 
                subtype='vnd.openxmlformats-officedocument.wordprocessingml.document', 
                filename=file_name
            )

    try:
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30) as server:
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
                logger.info(f"Email successfully sent (SSL) to {recipient_email}")
                return True
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
                logger.info(f"Email successfully sent (STARTTLS) to {recipient_email}")
                return True
    except Exception as e:
        logger.error(f"Failed to send email to {recipient_email}: {e}")
        return False
