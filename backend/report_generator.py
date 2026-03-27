import io
import os
import platform
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.fonts import addMapping

# --- Функция для поиска системного шрифта с поддержкой кириллицы ---
def get_system_font_path():
    """
    Возвращает путь к системному шрифту с поддержкой кириллицы.
    Сначала ищет Arial, затем Times New Roman, затем пробует DejaVu из папки проекта.
    Если ничего не найдено, возвращает None.
    """
    system = platform.system()
    possible_paths = []
    if system == "Windows":
        possible_paths = [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/times.ttf",
            "C:/Windows/Fonts/arialbd.ttf",   # жирный
            "C:/Windows/Fonts/timesbd.ttf"
        ]
    elif system == "Darwin":  # macOS
        possible_paths = [
            "/System/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Times.ttf",
            "/System/Library/Fonts/Arial Bold.ttf",
            "/System/Library/Fonts/Times Bold.ttf"
        ]
    elif system == "Linux":
        possible_paths = [
            "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ]
    # Проверяем наличие файлов
    for path in possible_paths:
        if os.path.exists(path):
            return path
    # Если системные не найдены, пробуем DejaVu в папке проекта
    project_dejavu = os.path.join(os.path.dirname(__file__), 'DejaVuSans.ttf')
    if os.path.exists(project_dejavu):
        return project_dejavu
    return None

def get_bold_font_path(regular_path):
    """Пытается найти жирное начертание для заданного шрифта"""
    if not regular_path:
        return None
    # Пробуем стандартные варианты
    dirname = os.path.dirname(regular_path)
    basename = os.path.basename(regular_path)
    name, ext = os.path.splitext(basename)
    bold_name = name.replace('Regular', 'Bold').replace('Sans', 'Sans-Bold')
    bold_path = os.path.join(dirname, bold_name + ext)
    if os.path.exists(bold_path):
        return bold_path
    # Для Arial
    if 'arial' in basename.lower():
        bold_path = os.path.join(dirname, 'arialbd.ttf')
        if os.path.exists(bold_path):
            return bold_path
    # Для Times
    if 'times' in basename.lower():
        bold_path = os.path.join(dirname, 'timesbd.ttf')
        if os.path.exists(bold_path):
            return bold_path
    return None

# Глобальная переменная для имени шрифта, используемого в PDF
PDF_FONT_NAME = 'Helvetica'  # fallback

# Пытаемся загрузить системный шрифт
font_path = get_system_font_path()
if font_path:
    try:
        pdfmetrics.registerFont(TTFont('CyrillicFont', font_path))
        PDF_FONT_NAME = 'CyrillicFont'
        # Пытаемся загрузить жирное начертание
        bold_path = get_bold_font_path(font_path)
        if bold_path:
            pdfmetrics.registerFont(TTFont('CyrillicFont-Bold', bold_path))
            # Связываем стили
            addMapping('CyrillicFont', 0, 0, 'CyrillicFont')          # normal
            addMapping('CyrillicFont', 1, 0, 'CyrillicFont-Bold')    # bold
    except Exception as e:
        print(f"Не удалось загрузить шрифт {font_path}: {e}")
        # Оставляем Helvetica
else:
    print("Системный шрифт с поддержкой кириллицы не найден. Используется Helvetica (кириллица не будет отображаться).")

def sanitize_sheet_title(title):
    """Заменяет недопустимые символы в названии листа Excel на подчеркивания и обрезает до 31 символа"""
    invalid_chars = r'[]:*?/\\'
    for ch in invalid_chars:
        title = title.replace(ch, '_')
    # Обрезаем до 31 символа
    if len(title) > 31:
        title = title[:31]
    return title

def generate_excel_report(data, group_code, start_date, end_date):
    """
    Generate Excel report as BytesIO object.
    data: list of dicts with keys: full_name, subgroup, present, late, excused, absent, total, percent
    """
    wb = Workbook()
    sheet_title = sanitize_sheet_title(f"Отчет {group_code}")
    ws = wb.active
    ws.title = sheet_title

    # Header styles
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center")

    # Column titles
    headers = [
        "№", "ФИО студента", "Подгруппа",
        "Присутствовал", "Опоздал", "По уважительной", "Отсутствовал",
        "Всего занятий", "% посещаемости"
    ]
    ws.append(headers)
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment

    # Fill data
    for idx, student in enumerate(data, start=2):
        row = [
            idx-1,
            student['full_name'],
            student['subgroup'],
            student['present'],
            student['late'],
            student['excused'],
            student['absent'],
            student['total'],
            student['percent']
        ]
        ws.append(row)

    # Auto-size columns
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            try:
                if cell.value:
                    max_len = max(max_len, len(str(cell.value)))
            except:
                pass
        adjusted_width = min(max_len + 2, 30)
        ws.column_dimensions[col_letter].width = adjusted_width

    # Output to bytes
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output

def generate_pdf_report(data, group_code, start_date, end_date):
    """
    Generate PDF report as BytesIO object.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=36, leftMargin=36,
                            topMargin=36, bottomMargin=36)

    styles = getSampleStyleSheet()
    # Создаём стили с нужным шрифтом
    if PDF_FONT_NAME != 'Helvetica':
        styles.add(ParagraphStyle(name='CyrillicNormal', fontName=PDF_FONT_NAME, fontSize=10))
        styles.add(ParagraphStyle(name='CyrillicHeading', fontName=PDF_FONT_NAME, fontSize=12, alignment=1))
        styles.add(ParagraphStyle(name='CyrillicTitle', fontName=PDF_FONT_NAME, fontSize=14, alignment=1, spaceAfter=12))
    else:
        # fallback
        styles.add(ParagraphStyle(name='CyrillicNormal', fontName='Helvetica', fontSize=10))
        styles.add(ParagraphStyle(name='CyrillicHeading', fontName='Helvetica', fontSize=12, alignment=1))
        styles.add(ParagraphStyle(name='CyrillicTitle', fontName='Helvetica', fontSize=14, alignment=1, spaceAfter=12))

    story = []

    # Title
    title = f"Отчет о посещаемости группы {group_code}"
    story.append(Paragraph(title, styles['CyrillicTitle']))
    story.append(Paragraph(f"Период: {start_date} — {end_date}", styles['CyrillicNormal']))
    story.append(Spacer(1, 12))

    # Table data
    table_data = [
        ['№', 'ФИО', 'Подгр.', 'Присут.', 'Опозд.', 'Уваж.', 'Отсут.', 'Всего', '%']
    ]
    for idx, s in enumerate(data, 1):
        table_data.append([
            str(idx),
            s['full_name'],
            s['subgroup'],
            str(s['present']),
            str(s['late']),
            str(s['excused']),
            str(s['absent']),
            str(s['total']),
            f"{s['percent']}%"
        ])

    # Create table
    table = Table(table_data, colWidths=[30, 110, 40, 40, 40, 40, 40, 40, 50])
    table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), PDF_FONT_NAME),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#366092')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BOX', (0,0), (-1,-1), 0.5, colors.black),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('TOPPADDING', (0,0), (-1,0), 8),
    ]))
    story.append(table)
    story.append(Spacer(1, 20))
    story.append(Paragraph("Отчет сгенерирован автоматически", styles['CyrillicNormal']))

    doc.build(story)
    buffer.seek(0)
    return buffer