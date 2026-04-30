import os
import smtplib
from dotenv import load_dotenv
from email.message import EmailMessage

load_dotenv()

def test_smtp():
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", 465))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    recipient = "v.s.anyanov@gmail.com"

    print(f"Testing SMTP: {host}:{port}")
    print(f"User: {user}")

    msg = EmailMessage()
    msg.set_content("Test connection")
    msg['Subject'] = "SMTP Test"
    msg['From'] = user
    msg['To'] = recipient

    try:
        if port == 465:
            print("Using SMTP_SSL...")
            server = smtplib.SMTP_SSL(host, port, timeout=10)
        else:
            print("Using STARTTLS...")
            server = smtplib.SMTP(host, port, timeout=10)
            server.starttls()
        
        with server:
            print("Connecting/Logging in...")
            server.login(user, password)
            print("Sending...")
            server.send_message(msg)
            print("Success!")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_smtp()
