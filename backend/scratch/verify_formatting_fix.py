import os
import sys
import io

# Force UTF-8 for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from docx import Document
from docx.shared import Pt

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from protocol_generator import generate_docx

def test_formatting():
    content = """## ОТЧЕТ AI-АУДИТОРА
### Краткий отчет

**Проверенные вопросы:**
1. Тест 1
2. Тест 2

**Найденные расхождения:**
- Ошибка 1

Заключение:
Все в порядке.

**Topic with text on same line:** description here
"""
    
    print("Generating docx...")
    filepath = generate_docx(content)
    print(f"Generated: {filepath}")
    
    doc = Document(filepath)
    
    print("\nVerifying content...")
    found_short_report = False
    subheadings_found = []
    
    for p in doc.paragraphs:
        text = p.text.strip()
        if not text: continue
        
        print(f"Paragraph: '{text}'")
        
        if "КРАТКИЙ ОТЧЕТ" in text.upper():
            # If it's the heading "ОТЧЕТ AI-АУДИТОРА", that's fine.
            # But the specific line "Краткий отчет" should be gone.
            if text == "КРАТКИЙ ОТЧЕТ":
                found_short_report = True
        
        # Check subheadings
        # Subheadings we expect: "Проверенные вопросы", "Найденные расхождения", "Заключение", "Topic with text on same line"
        expected_subheadings = ["Проверенные вопросы", "Найденные расхождения", "Заключение", "Topic with text on same line"]
        
        for expected in expected_subheadings:
            if text.startswith(expected):
                # Check formatting of the first run
                run = p.runs[0]
                is_bold = run.bold
                size = run.font.size.pt if run.font.size else None
                font_name = run.font.name
                
                print(f"  -> Found '{expected}': Bold={is_bold}, Size={size}, Font={font_name}")
                subheadings_found.append(expected)
                
                # Check for colon
                if ":" in run.text:
                    print(f"  !! WARNING: Colon found in run text: '{run.text}'")

    if found_short_report:
        print("\nFAIL: 'Краткий отчет' was found in the document.")
    else:
        print("\nSUCCESS: 'Краткий отчет' was correctly skipped.")
        
    missing = set(expected_subheadings) - set(subheadings_found)
    if missing:
        print(f"FAIL: Missing subheadings: {missing}")
    else:
        print("SUCCESS: All subheadings were found and formatted.")

if __name__ == "__main__":
    test_formatting()
