import sys
import os
sys.path.append(os.getcwd())
from protocol_generator import generate_docx
from docx import Document

content = """## PROTOCOL
Format: test, Provider: test

## ОТЧЕТ AI-АУДИТОРА
OK"""

path = generate_docx(content)
doc = Document(path)
full_text = "\n".join([p.text for p in doc.paragraphs])
print(f"FULL TEXT:\n{full_text}")
if "OK" in full_text:
    print("SUCCESS: OK found")
else:
    print("FAILURE: OK not found")
os.remove(path)
