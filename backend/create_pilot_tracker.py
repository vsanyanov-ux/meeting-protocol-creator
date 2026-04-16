import pandas as pd
import os

def create_excel_tracker():
    """Generates a professional Pilot Results Tracker for enterprise sales."""
    
    # 1. Main Metrics Table
    data_metrics = {
        'Операция': [
            'Подготовка черновика (AI)',
            'Техническая сверка терм.',
            'Оформление по ГОСТу',
            'Рассылка протокола',
            'ИТОГО на 1 документ'
        ],
        'Время Вручную (мин)': [60, 30, 15, 5, 110],
        'Время с "Протоколистом" (мин)': [5, 10, 0, 2, 17],
        'Экономия (мин)': [55, 20, 15, 3, 93],
        'Экономия (%)': ['91%', '66%', '100%', '60%', '84%']
    }
    df_metrics = pd.DataFrame(data_metrics)
    
    # 2. Results Accumulator
    data_summary = {
        'Показатель': [
            'Всего протоколов за месяц',
            'Сэкономлено времени (часов)',
            'Стоимость часа инженера (руб)',
            'Общая экономия бюджета (руб)'
        ],
        'Значение': [40, 62, 2500, 155000]
    }
    df_summary = pd.DataFrame(data_summary)
    
    # Create the Excel file
    output_dir = "marketing_assets"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    filename = os.path.join(output_dir, "Pilot_Results_Tracker_v1.xlsx")
    
    with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
        df_metrics.to_excel(writer, sheet_name='Метрики_ROI', index=False, startrow=2)
        df_summary.to_excel(writer, sheet_name='Итоговый_расчет', index=False, startrow=2)
        
        # Access the workbook and sheets for formatting
        workbook = writer.book
        sheet1 = writer.sheets['Метрики_ROI']
        sheet2 = writer.sheets['Итоговый_расчет']
        
        # Formatting
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#003366',
            'font_color': 'white',
            'border': 1
        })
        
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 14,
            'font_color': '#003366'
        })
        
        sheet1.write('A1', 'Отчет об эффективности "Протоколист": Пилотный проект', title_format)
        sheet2.write('A1', 'Расчет ROI (окупаемости)', title_format)
        
        # Adjust column widths
        sheet1.set_column('A:A', 30)
        sheet1.set_column('B:E', 20)
        sheet2.set_column('A:A', 35)
        sheet2.set_column('B:B', 20)

    print(f"Success! Pilot Results Tracker created at: {filename}")
    return filename

if __name__ == "__main__":
    try:
        import xlsxwriter
        create_excel_tracker()
    except ImportError:
        print("Required lib 'xlsxwriter' not found. Installing...")
        os.system('pip install xlsxwriter')
        create_excel_tracker()
