import sys
import os

# Add backend to path 
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from protocol_generator import generate_docx

test_content = """
## Общая информация
Тема: Испытания новых материалов для АЭС
Участники: Иванов И.И. (ЦНИИТМАШ), Петров П.П. (Росатом)

## Повестка дня
1. Обсуждение состава стали 08Х18Н10Т.
2. Сроки проведения ультразвукового контроля.

## Решения и задачи
| № | Задача | Ответственный | Срок |
|---|---|---|---|
| 1 | Подготовить образцы для сварки | Иванов И.И. | 20.04.2026 |
| 2 | Провести анализ микроструктуры | Смирнов С.С. | 25.04.2026 |

## Заключение
Совещание признано успешным. Следующая встреча через неделю.
"""

if __name__ == "__main__":
    print("Generating test enterprise protocol...")
    try:
        path = generate_docx(test_content)
        print(f"Protocol generated successfully at: {path}")
        print("Please check the document for Logo, 'КОНФИДЕНЦИАЛЬНО' footer, and Times New Roman styling.")
    except Exception as e:
        print(f"Error generating protocol: {e}")
