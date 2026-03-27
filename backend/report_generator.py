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
    system = platform.system()
    possible_paths = []
    if system == "Windows":
        possible_paths = [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/times.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
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
    for path in possible_paths:
        if os.path.exists(path):
            return path
    # Если системные не найдены, пробуем DejaVu в папке проекта
    project_dejavu = os.path.join(os.path.dirname(__file__), 'DejaVuSans.ttf')
    if os.path.exists(project_dejavu):
        return project_dejavu
    return None

def get_bold_font_path(regular_path):
    if not regular_path:
        return None
    dirname = os.path.dirname(regular_path)
    basename = os.path.basename(regular_path)
    name, ext = os.path.splitext(basename)
    bold_name = name.replace('Regular', 'Bold').replace('Sans', 'Sans-Bold')
    bold_path = os.path.join(dirname, bold_name + ext)
    if os.path.exists(bold_path):
        return bold_path
    if 'arial' in basename.lower():
        bold_path = os.path.join(dirname, 'arialbd.ttf')
        if os.path.exists(bold_path):
            return bold_path
    if 'times' in basename.lower():
        bold_path = os.path.join(dirname, 'timesbd.ttf')
        if os.path.exists(bold_path):
            return bold_path
    return None

PDF_FONT_NAME = 'Helvetica'
font_path = get_system_font_path()
if font_path:
    try:
        pdfmetrics.registerFont(TTFont('CyrillicFont', font_path))
        PDF_FONT_NAME = 'CyrillicFont'
        bold_path = get_bold_font_path(font_path)
        if bold_path:
            pdfmetrics.registerFont(TTFont('CyrillicFont-Bold', bold_path))
            addMapping('CyrillicFont', 0, 0, 'CyrillicFont')
            addMapping('CyrillicFont', 1, 0, 'CyrillicFont-Bold')
    except Exception as e:
        print(f"Не удалось загрузить шрифт {font_path}: {e}")

def sanitize_sheet_title(title):
    invalid_chars = r'[]:*?/\\'
    for ch in invalid_chars:
        title = title.replace(ch, '_')
    if len(title) > 31:
        title = title[:31]
    return title

def generate_excel_report(data, group_code, start_date, end_date,
                          total_lessons, total_students, total_present,
                          total_late, total_excused, total_absent, total_possible):
    """
    Генерация отчета в Excel.
    data: список студентов с ключами: full_name, subgroup, present, late, excused, absent, total, percent
    total_lessons: количество уроков в группе за период
    total_students: количество активных студентов
    total_present, total_late, total_excused, total_absent: суммы по всем студентам
    total_possible: суммарное количество возможных посещений (sum студент.total)
    """
    wb = Workbook()
    sheet_title = sanitize_sheet_title(f"Отчет {group_code}")
    ws = wb.active
    ws.title = sheet_title

    # Стили
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center")
    border = Border(left=Side(style='thin'), right=Side(style='thin'),
                    top=Side(style='thin'), bottom=Side(style='thin'))

    # Заголовок
    ws.merge_cells('A1:I1')
    title_cell = ws.cell(row=1, column=1, value=f"Отчет о посещаемости")
    title_cell.font = Font(bold=True, size=14)
    title_cell.alignment = Alignment(horizontal='center')

    ws.merge_cells('A2:I2')
    group_cell = ws.cell(row=2, column=1, value=f"Группа: {group_code}")
    group_cell.font = Font(size=12)
    group_cell.alignment = Alignment(horizontal='center')

    ws.merge_cells('A3:I3')
    period_cell = ws.cell(row=3, column=1, value=f"Период: {start_date} - {end_date}")
    period_cell.font = Font(size=12)
    period_cell.alignment = Alignment(horizontal='center')

    # Общая статистика
    ws.cell(row=5, column=1, value="Всего пар:").font = Font(bold=True)
    ws.cell(row=5, column=2, value=total_lessons)
    ws.cell(row=6, column=1, value="Всего студентов:").font = Font(bold=True)
    ws.cell(row=6, column=2, value=total_students)

    # Таблица статистики
    stats_headers = ["", "Присутствовало", "Опоздало", "По уважительной", "Без уважительной"]
    stats_values = ["Всего", total_present, total_late, total_excused, total_absent]

    for col, header in enumerate(stats_headers, start=4):
        cell = ws.cell(row=8, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = border

    for col, value in enumerate(stats_values, start=4):
        cell = ws.cell(row=9, column=col, value=value)
        cell.alignment = Alignment(horizontal='center')
        cell.border = border

    # Анализ посещаемости
    ws.cell(row=11, column=1, value="Анализ посещаемости").font = Font(bold=True, size=12)

    attendance_rate = total_present / total_possible * 100 if total_possible else 0
    excused_rate = total_excused / total_possible * 100 if total_possible else 0
    absent_rate = total_absent / total_possible * 100 if total_possible else 0
    late_rate = total_late / total_possible * 100 if total_possible else 0

    ws.cell(row=12, column=1, value="Общая посещаемость:").font = Font(bold=True)
    ws.cell(row=12, column=2, value=f"{attendance_rate:.1f}%")
    ws.cell(row=13, column=1, value="Пропуски по уважительной причине:").font = Font(bold=True)
    ws.cell(row=13, column=2, value=f"{excused_rate:.1f}% ({total_excused})")
    ws.cell(row=14, column=1, value="Пропуски без уважительной причины:").font = Font(bold=True)
    ws.cell(row=14, column=2, value=f"{absent_rate:.1f}% ({total_absent})")
    ws.cell(row=15, column=1, value="Опоздания:").font = Font(bold=True)
    ws.cell(row=15, column=2, value=f"{late_rate:.1f}% ({total_late})")

    # Детализация по студентам
    ws.cell(row=17, column=1, value="Детализация по студентам").font = Font(bold=True, size=12)

    detail_headers = ["Студент", "Присут.", "Опозд.", "Уваж.", "Без уваж.", "% Посещ."]
    for col, header in enumerate(detail_headers, start=1):
        cell = ws.cell(row=18, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = border

    row = 19
    for student in data:
        ws.cell(row=row, column=1, value=student['full_name']).border = border
        ws.cell(row=row, column=2, value=student['present']).border = border
        ws.cell(row=row, column=3, value=student['late']).border = border
        ws.cell(row=row, column=4, value=student['excused']).border = border
        ws.cell(row=row, column=5, value=student['absent']).border = border
        ws.cell(row=row, column=6, value=student['percent']).border = border
        row += 1

    # Автоширина колонок
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

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output

# report_generator.py — обновлённая функция с датой формирования

from datetime import datetime

def generate_pdf_report(data, group_code, start_date, end_date,
                        total_lessons, total_students, total_present,
                        total_late, total_excused, total_absent, total_possible):
    """Генерация отчета в PDF с увеличенными шрифтами и таблицами на всю ширину."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=36, leftMargin=36,
                            topMargin=36, bottomMargin=36)

    # Стили
    styles = getSampleStyleSheet()
    if PDF_FONT_NAME != 'Helvetica':
        styles.add(ParagraphStyle(name='CyrillicNormal', fontName=PDF_FONT_NAME, fontSize=12, leading=14))
        styles.add(ParagraphStyle(name='CyrillicAnalysis', fontName=PDF_FONT_NAME, fontSize=14, leading=16))
        styles.add(ParagraphStyle(name='CyrillicHeader', fontName=PDF_FONT_NAME, fontSize=18, leading=22, fontWeight='bold'))
        styles.add(ParagraphStyle(name='CyrillicHeading', fontName=PDF_FONT_NAME, fontSize=16, leading=18, spaceAfter=8, fontWeight='bold'))
        styles.add(ParagraphStyle(name='CyrillicBold', fontName=PDF_FONT_NAME, fontSize=14, leading=16, fontWeight='bold'))
        styles.add(ParagraphStyle(name='DateStyle', fontName=PDF_FONT_NAME, fontSize=10, leading=12, alignment=2, textColor=colors.gray))
    else:
        styles.add(ParagraphStyle(name='CyrillicNormal', fontName='Helvetica', fontSize=12, leading=14))
        styles.add(ParagraphStyle(name='CyrillicAnalysis', fontName='Helvetica', fontSize=14, leading=16))
        styles.add(ParagraphStyle(name='CyrillicHeader', fontName='Helvetica', fontSize=18, leading=22, fontWeight='bold'))
        styles.add(ParagraphStyle(name='CyrillicHeading', fontName='Helvetica', fontSize=16, leading=18, spaceAfter=8, fontWeight='bold'))
        styles.add(ParagraphStyle(name='CyrillicBold', fontName='Helvetica', fontSize=14, leading=16, fontWeight='bold'))
        styles.add(ParagraphStyle(name='DateStyle', fontName='Helvetica', fontSize=10, leading=12, alignment=2, textColor=colors.gray))

    story = []

    # Шапка (простой текст)
    story.append(Paragraph(f"Группа: {group_code}", styles['CyrillicHeader']))
    story.append(Paragraph(f"Период: {start_date} - {end_date}", styles['CyrillicHeader']))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"Всего пар: {total_lessons}", styles['CyrillicHeader']))
    story.append(Paragraph(f"Всего студентов: {total_students}", styles['CyrillicHeader']))
    story.append(Spacer(1, 16))

    # Общая статистика (вертикальная таблица, шрифт 12pt)
    story.append(Paragraph("## Общая статистика", styles['CyrillicHeading']))
    stats_data = [
        ["Присутствовало", str(total_present)],
        ["Опоздало", str(total_late)],
        ["По уважительной", str(total_excused)],
        ["Без уважительной", str(total_absent)],
    ]
    stats_table = Table(stats_data, colWidths=[doc.width * 0.3, doc.width * 0.7])
    stats_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), PDF_FONT_NAME),
        ('FONTSIZE', (0,0), (-1,-1), 12),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('FONTNAME', (0,0), (-1,0), PDF_FONT_NAME),
        ('FONTWEIGHT', (0,0), (-1,0), 'BOLD'),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
    ]))
    story.append(stats_table)
    story.append(Spacer(1, 16))

    # Анализ посещаемости (шрифт 14pt)
    attendance_rate = total_present / total_possible * 100 if total_possible else 0
    excused_rate = total_excused / total_possible * 100 if total_possible else 0
    absent_rate = total_absent / total_possible * 100 if total_possible else 0
    late_rate = total_late / total_possible * 100 if total_possible else 0

    if attendance_rate >= 80:
        analysis_text = "Высокая посещаемость. Уровень хороший."
    elif attendance_rate >= 50:
        analysis_text = "Средняя посещаемость. Есть потенциал для улучшения."
    else:
        analysis_text = "Низкая посещаемость. Требуются срочные меры по улучшению ситуации."

    story.append(Paragraph("## Анализ посещаемости", styles['CyrillicHeading']))
    story.append(Paragraph(f"☒ {analysis_text}", styles['CyrillicAnalysis']))
    story.append(Spacer(1, 8))
    story.append(Paragraph("Детали:", styles['CyrillicBold']))
    story.append(Paragraph(f"• Общая посещаемость: {attendance_rate:.0f}%", styles['CyrillicAnalysis']))
    story.append(Paragraph(f"• Пропуски по уважительной причине: {total_excused} ({excused_rate:.0f}%)", styles['CyrillicAnalysis']))
    story.append(Paragraph(f"• Пропуски без уважительной причины: {total_absent} ({absent_rate:.0f}%)", styles['CyrillicAnalysis']))
    story.append(Paragraph(f"• Опоздания: {total_late} ({late_rate:.0f}%)", styles['CyrillicAnalysis']))
    story.append(Spacer(1, 16))

    # Детализация по студентам (шрифт 11pt)
    story.append(Paragraph("## Детализация по студентам", styles['CyrillicHeading']))
    detail_data = [["Студент", "Присут.", "Опозд.", "Уваж.", "Без уваж.", "% Посещ."]]
    for s in data:
        detail_data.append([
            s['full_name'],
            str(s['present']),
            str(s['late']),
            str(s['excused']),
            str(s['absent']),
            f"{s['percent']}%"
        ])

    detail_table = Table(detail_data, colWidths=[doc.width * 0.40, doc.width * 0.12, doc.width * 0.12, doc.width * 0.12, doc.width * 0.12, doc.width * 0.12])
    detail_style = [
        ('FONTNAME', (0,0), (-1,-1), PDF_FONT_NAME),
        ('FONTSIZE', (0,0), (-1,-1), 11),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('FONTNAME', (0,0), (-1,0), PDF_FONT_NAME),
        ('FONTWEIGHT', (0,0), (-1,0), 'BOLD'),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
    ]
    for i in range(1, len(detail_data)):
        if i % 2 == 0:
            detail_style.append(('BACKGROUND', (0,i), (-1,i), colors.whitesmoke))
    detail_table.setStyle(TableStyle(detail_style))
    story.append(detail_table)

    # Дата формирования
    current_datetime = datetime.now().strftime("%d.%m.%Y %H:%M")
    story.append(Spacer(1, 20))
    story.append(Paragraph(f"Отчет сформирован: {current_datetime}", styles['DateStyle']))

    doc.build(story)
    buffer.seek(0)
    return buffer