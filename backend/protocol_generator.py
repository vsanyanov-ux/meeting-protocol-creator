import os
from docx import Document
from docx.shared import Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE
import datetime
import re

def generate_docx(content: str) -> str:
    """Generate a high-end corporate DOCX protocol with strict formatting."""
    doc = Document()
    
    # 0. Page Margins (World Standard)
    section = doc.sections[0]
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(1.5)
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(2.0)
    
    # Global Style Adjustments
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Calibri'
    font.size = Pt(11)
    
    # 1. Main Title (Centered and Distinctive)
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_title = title_p.add_run('ПРОТОКОЛ СОВЕЩАНИЯ')
    run_title.bold = True
    run_title.font.size = Pt(26)
    run_title.font.color.rgb = RGBColor(31, 73, 125) # Dark Blue
    
    # 2. Meta Info Header
    p_meta = doc.add_paragraph()
    p_meta.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run_meta = p_meta.add_run(f"Сформировано: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}")
    run_meta.italic = True
    run_meta.font.size = Pt(9)
    run_meta.font.color.rgb = RGBColor(128, 128, 128) # Gray

    # Horizontal Bar Separator
    p_sep = doc.add_paragraph()
    p_sep.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_sep = p_sep.add_run("________________________________________________________________________________")
    run_sep.font.color.rgb = RGBColor(128, 128, 128)

    # Split content by lines
    lines = content.split('\n')
    table_data = []
    
    def finalize_table(doc_obj, data):
        if not data: return
        # Create a 4-column table
        table = doc_obj.add_table(rows=len(data), cols=4)
        table.style = 'Table Grid'
        table.autofit = False # Enforce explicit widths
        
        # Set specific column widths for a corporate look
        # Total width ≈ 17cm (21 - 2.5 - 1.5)
        widths = [Cm(1.0), Cm(9.0), Cm(3.5), Cm(3.5)]
        for i, width in enumerate(widths):
            table.columns[i].width = width
        
        for r_idx, row_data in enumerate(data):
            for c_idx, cell_data in enumerate(row_data):
                if c_idx < 4:
                    cell = table.cell(r_idx, c_idx)
                    cell.text = str(cell_data)
                    # Bold headers and fill background
                    if r_idx == 0:
                        for p in cell.paragraphs:
                            for run in p.runs:
                                run.bold = True
                                run.font.size = Pt(10)
        doc_obj.add_paragraph("")

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue

        # Table detection
        if line_stripped.startswith('|') and line_stripped.endswith('|'):
            # Improved separator line detection: skip if it's just pipes, dashes, colons and whitespace
            if re.match(r"^[|\-\s:]+$", line_stripped):
                continue
            
            cols = [col.strip() for col in line_stripped.split('|')[1:-1]]
            # Pad / Trim
            if len(cols) > 4: cols = cols[:4]
            while len(cols) < 4: cols.append("-")
            table_data.append(cols)
            continue
        
        # If we had accumulated table rows
        if table_data:
            finalize_table(doc, table_data)
            table_data = []

        # Heading detection (## Section)
        if line_stripped.startswith('##'):
            doc.add_paragraph() # spacing
            h_text = line_stripped.replace('#', '').strip().upper()
            h_p = doc.add_paragraph()
            run_h = h_p.add_run(h_text)
            run_h.font.name = 'Calibri'
            run_h.font.size = Pt(14)
            run_h.bold = True
            run_h.font.color.rgb = RGBColor(31, 73, 125)
            continue
        
        # Bold label detection (e.g. "Label: Value")
        # Handles Russian and English labels ending in : or –
        match_label = re.match(r"^([\w\sа-яА-ЯёЁ]+[:–])(.*)$", line_stripped)
        if match_label:
            p = doc.add_paragraph()
            run_lbl = p.add_run(match_label.group(1))
            run_lbl.bold = True
            run_lbl.font.size = Pt(11)
            p.add_run(match_label.group(2))
        else:
            # Clean Markdown Bold **Text**
            p_text = re.sub(r"\*\*(.*?)\*\*", r"\1", line_stripped)
            p_text = p_text.replace("__", "").strip()
            if p_text:
                p = doc.add_paragraph(p_text)
                p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # Final table check
    if table_data:
        finalize_table(doc, table_data)
            
    # Save to a temporary file
    temp_dir = "temp_protocols"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
        
    filename = f"Protocol_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    filepath = os.path.join(temp_dir, filename)
    doc.save(filepath)
    
    return filepath
