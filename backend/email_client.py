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
    msg['Reply-To'] = smtp_user
    
    # Message-ID should have the proper domain to avoid spam filters
    domain = smtp_host.replace("smtp.", "") if smtp_host else "yandex.ru"
    msg['Message-ID'] = make_msgid(domain=domain)
    msg['Date'] = formatdate(localtime=True)
    
    # Anti-spam headers
    msg['X-Priority'] = '3'
    msg['X-Mailer'] = 'Microsoft Outlook 16.0'  # Identifies as a common client
    msg['Precedence'] = 'list'

    # Plain text version
    msg.set_content(body)

    # Professional HTML version
    html_body = f"""
    <html>
        <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 10px;">
                <h2 style="color: #2c3e50;">Протокол совещания готов</h2>
                <p>Здравствуйте!</p>
                <p>Результат обработки вашего файла сформирован и доступен во вложении к данному письму.</p>
                <div style="background-color: #f9f9f9; padding: 15px; border-left: 4px solid #3498db; margin: 20px 0;">
                    {body.replace('\n', '<br>')}
                </div>
                <p style="font-size: 0.9em; color: #7f8c8d;">
                    Это автоматическое уведомление от сервиса <b>Meeting Protocol Creator</b>.<br>
                    Пожалуйста, не отвечайте на это письмо.
                </p>
            </div>
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
        logger.info(f"Connecting to {smtp_host}:{smtp_port}...")
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
            server.starttls()
            
        with server:
            logger.info("SMTP connection established, logging in...")
            server.login(smtp_user, smtp_password)
            logger.info("Login successful, sending message...")
            server.send_message(msg)
            logger.info(f"Email successfully sent to {recipient_email}")
            return True
    except Exception as e:
        logger.error(f"Failed to send email to {recipient_email}: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return False
