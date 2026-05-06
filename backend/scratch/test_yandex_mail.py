import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

def test_send_with_attachment():
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", 465))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    recipient = os.getenv("RECIPIENT_EMAIL")

    # Find any docx in temp_protocols to attach
    proto_dir = "temp_protocols"
    files = [f for f in os.listdir(proto_dir) if f.endswith(".docx")]
    if not files:
        print("No docx found in temp_protocols. Please run a real task first or place a file there.")
        return
    
    attachment_path = os.path.join(proto_dir, files[0])
    print(f"Testing send WITH ATTACHMENT {attachment_path} from {smtp_user} to {recipient}")

    msg = EmailMessage()
    msg['Subject'] = "Тест С ВЛОЖЕНИЕМ"
    msg['From'] = smtp_user
    msg['To'] = recipient
    msg.set_content("Проверка отправки с вложением.")

    with open(attachment_path, 'rb') as f:
        file_data = f.read()
        file_name = os.path.basename(attachment_path)
        msg.add_attachment(
            file_data, 
            maintype='application', 
            subtype='vnd.openxmlformats-officedocument.wordprocessingml.document', 
            filename=file_name
        )

    try:
        server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
        with server:
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
            print("Successfully sent with attachment!")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    test_send_with_attachment()
