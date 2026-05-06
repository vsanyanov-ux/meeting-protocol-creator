import os
import smtplib
import time
import socket
from email.message import EmailMessage
from email.utils import make_msgid, formatdate
from loguru import logger

def retry_on_timeout(retries=2, delay=1):
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_error = None
            for i in range(retries):
                try:
                    return func(*args, **kwargs)
                except (socket.timeout, TimeoutError, ConnectionRefusedError) as e:
                    last_error = e
                    logger.warning(f"SMTP connection attempt {i+1} failed (timeout/offline): {e}. Retrying in {delay}s...")
                    time.sleep(delay)
                except Exception as e:
                    raise e
            raise last_error
        return wrapper
    return decorator

def send_email(recipient_email: str, subject: str, body: str, attachment_path: str):
    """Send an email with an attachment and simple HTML."""
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")

    msg = EmailMessage()
    # Use clean subject
    clean_subject = subject.split(':')[-1].strip()
    msg['Subject'] = f"Протокол: {clean_subject}"
    
    # Use only email address in From to avoid Yandex filters
    msg['From'] = smtp_user
    msg['To'] = recipient_email
    msg['Date'] = formatdate(localtime=True)
    msg['Message-ID'] = make_msgid(domain='yandex.ru')

    # Plain text version
    msg.set_content(body)

    # Simplified HTML version
    html_body = f"""
    <html>
        <body style="font-family: sans-serif;">
            <h2>Ваш протокол готов</h2>
            <p>{body.replace('\n', '<br>')}</p>
            <hr>
            <p style="color: #666; font-size: 0.8em;">Отправлено автоматически сервисом Протоколист.</p>
        </body>
    </html>
    """
    msg.add_alternative(html_body, subtype='html')

    # Attach the file
    if attachment_path and os.path.exists(attachment_path):
        with open(attachment_path, 'rb') as f:
            file_data = f.read()
            file_name = os.path.basename(attachment_path)
            msg.add_attachment(
                file_data, 
                maintype='application', 
                subtype='octet-stream', 
                filename=file_name
            )

    def _do_send():
        logger.info(f"Connecting to {smtp_host}:{smtp_port}...")
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            server.starttls()
            
        with server:
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
            logger.info(f"Email successfully sent to {recipient_email}")
            return True

    try:
        return retry_on_timeout(retries=2, delay=2)(_do_send)()
    except Exception as e:
        logger.error(f"Failed to send email to {recipient_email}: {e}")
        return False
