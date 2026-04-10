import os
from dotenv import load_dotenv
from email_client import send_email

load_dotenv()

recipient = os.getenv("RECIPIENT_EMAIL", "vanyanov@yandex.ru")
print(f"Testing email to {recipient}...")

# Using a real docx file from temp_protocols for better test
attachment = "temp_protocols/Protocol_20260410_100610.docx"
import datetime
now_str = datetime.datetime.now().strftime("%H:%M:%S")

success = send_email(
    recipient_email=recipient,
    subject=f"Protocol Test {now_str}",
    body=f"This is an automated test at {now_str}.\nAttachments: 1 docx file.\nOriginal: Protocol_20260410_100610.docx",
    attachment_path=attachment
)

if success:
    print("✅ Email sent successfully!")
else:
    print("❌ Failed to send email.")
