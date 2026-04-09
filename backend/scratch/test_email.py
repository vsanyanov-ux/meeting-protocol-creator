import os
from dotenv import load_dotenv
from email_client import send_email

load_dotenv()

recipient = os.getenv("RECIPIENT_EMAIL", "v.s.anyanov@gmail.com")
print(f"Testing email to {recipient}...")

success = send_email(
    recipient_email=recipient,
    subject="Test Email from Antigravity",
    body="This is a test email to verify SMTP settings.",
    attachment_path="temp_content.txt" # using an existing small file
)

if success:
    print("✅ Email sent successfully!")
else:
    print("❌ Failed to send email.")
