"""
Report generation module for NAWI OIML R-76 applications.
Provides functions to generate PDF and Word documents.
"""

from io import BytesIO
from pathlib import Path
from typing import Any

from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from jinja2 import Environment, FileSystemLoader

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from app.schemas.models import TestSessionOut, InstrumentOut, ComplianceResult

# Locate the templates directory relative to this file
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def generate_pdf_reportlab(session: TestSessionOut, instrument: InstrumentOut, compliance: ComplianceResult) -> bytes:
    """
    Builds a professional A4 PDF report using pure-Python ReportLab.
    Ensures PDF generation works everywhere on Windows/Linux without external GTK/Pango DLLs.
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=17,
        leading=21,
        textColor=colors.HexColor('#0d3b66')
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor('#555555')
    )
    sec_style = ParagraphStyle(
        'SecHead',
        parent=styles['Heading2'],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#0d3b66')
    )
    th_style = ParagraphStyle(
        'TH',
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.white
    )
    td_style = ParagraphStyle(
        'TD',
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#222222')
    )
    td_bold = ParagraphStyle(
        'TDBold',
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#222222')
    )

    story = []

    # Title & Subtitle
    story.append(Paragraph("<b>LEGAL METROLOGY DIRECTORATE</b>", title_style))
    story.append(Paragraph("Non-Automatic Weighing Instruments (NAWI) Verification Report — OIML R-76", subtitle_style))
    story.append(Spacer(1, 10))

    # Overall Verdict Banner
    status_str = compliance.overall.value if compliance.overall else "PENDING"
    banner_color = colors.HexColor('#1e7e34') if status_str == 'PASS' else (colors.HexColor('#b02a2a') if status_str == 'FAIL' else colors.HexColor('#a66a00'))
    banner_bg = colors.HexColor('#e6f4ea') if status_str == 'PASS' else (colors.HexColor('#fdeaea') if status_str == 'FAIL' else colors.HexColor('#fff4e0'))

    verdict_table = Table(
        [[
            Paragraph(f"<b>REPORT ID:</b> {session.id}", td_bold),
            Paragraph(f"<b>STATUS:</b> {session.status.value}", td_bold),
            Paragraph(f"<b>OIML COMPLIANCE:</b> <font color='{banner_color.hexval()}'><b>{status_str}</b></font>", td_bold)
        ]],
        colWidths=[180, 160, 180]
    )
    verdict_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), banner_bg),
        ('GRID', (0, 0), (-1, -1), 1, banner_color),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(verdict_table)
    story.append(Spacer(1, 12))

    # Metadata Grid
    story.append(Paragraph("<b>1. Instrument Specifications & Test Conditions</b>", sec_style))
    d_val = instrument.d_value if instrument.d_value is not None else instrument.e_value
    meta_data = [
        [
            Paragraph("<b>Manufacturer:</b>", td_bold), Paragraph(str(instrument.manufacturer), td_style),
            Paragraph("<b>Tester:</b>", td_bold), Paragraph(str(session.tester), td_style)
        ],
        [
            Paragraph("<b>Model:</b>", td_bold), Paragraph(str(instrument.model), td_style),
            Paragraph("<b>Test Date:</b>", td_bold), Paragraph(str(session.test_date), td_style)
        ],
        [
            Paragraph("<b>Serial Number:</b>", td_bold), Paragraph(str(instrument.serial_number or "N/A"), td_style),
            Paragraph("<b>Lab / Site:</b>", td_bold), Paragraph(str(session.lab_location or "Standard Lab"), td_style)
        ],
        [
            Paragraph("<b>Accuracy Class:</b>", td_bold), Paragraph(str(instrument.accuracy_class.value), td_style),
            Paragraph("<b>Temperature:</b>", td_bold), Paragraph(f"{session.temperature} °C" if session.temperature else "N/A", td_style)
        ],
        [
            Paragraph("<b>Max Capacity:</b>", td_bold), Paragraph(f"{instrument.max_capacity} kg", td_style),
            Paragraph("<b>Humidity:</b>", td_bold), Paragraph(f"{session.humidity} %RH" if session.humidity else "N/A", td_style)
        ],
        [
            Paragraph("<b>Scale Interval (e / d):</b>", td_bold), Paragraph(f"e = {instrument.e_value} kg / d = {d_val} kg", td_style),
            Paragraph("<b>Owner:</b>", td_bold), Paragraph(str(instrument.owner or "N/A"), td_style)
        ],
    ]
    meta_table = Table(meta_data, colWidths=[120, 140, 110, 150])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f9fafb')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d7dbe0')),
        ('PADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 12))

    # Helper for building standard test observation table
    def build_test_table(rows_data, col_widths=[140, 75, 75, 75, 75, 80]):
        table_rows = [[
            Paragraph("Point / Position", th_style),
            Paragraph("Load (kg)", th_style),
            Paragraph("Indication (kg)", th_style),
            Paragraph("Error (kg)", th_style),
            Paragraph("MPE (kg)", th_style),
            Paragraph("Status", th_style)
        ]]
        for r in rows_data:
            err_str = f"{r.error:.3f}" if r.error is not None else "-"
            mpe_str = f"± {r.mpe:.3f}" if r.mpe is not None else "-"
            stat_val = r.status.value if hasattr(r.status, 'value') else str(r.status)
            color_hex = '#1e7e34' if stat_val == 'PASS' else ('#b02a2a' if stat_val == 'FAIL' else '#888888')
            table_rows.append([
                Paragraph(str(r.label), td_style),
                Paragraph(str(r.applied_load if r.applied_load is not None else "-"), td_style),
                Paragraph(str(r.indication if r.indication is not None else "-"), td_style),
                Paragraph(err_str, td_style),
                Paragraph(mpe_str, td_style),
                Paragraph(f"<font color='{color_hex}'><b>{stat_val}</b></font>", td_bold)
            ])
        t = Table(table_rows, colWidths=col_widths)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d3b66')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d7dbe0')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ('PADDING', (0, 0), (-1, -1), 3.5),
        ]))
        return t

    # 2. Eccentricity Test
    story.append(Paragraph(
        f"<b>2. Eccentricity Test (OIML R-76 clause A.4.7)</b> — Load: {session.eccentricity.test_load or 'N/A'} kg | Status: <b>{compliance.eccentricity.status.value}</b>",
        sec_style
    ))
    story.append(build_test_table(compliance.eccentricity.rows))
    story.append(Spacer(1, 10))

    # 3. Repeatability Test
    story.append(Paragraph(
        f"<b>3. Repeatability Test (OIML R-76 clause A.4.4)</b> — Status: <b>{compliance.repeatability.status.value}</b>",
        sec_style
    ))
    rep_rows = [
        [
            Paragraph("Trial", th_style),
            Paragraph("Applied Load", th_style),
            Paragraph("Indication", th_style),
            Paragraph("Observed Range", th_style),
            Paragraph("Allowed MPE", th_style),
            Paragraph("Status", th_style)
        ]
    ]
    for idx, r in enumerate(session.repeatability.rows):
        range_text = f"{compliance.repeatability.range_value:.3f} kg" if idx == 0 and compliance.repeatability.range_value is not None else ""
        mpe_text = f"± {compliance.repeatability.mpe:.3f} kg" if idx == 0 and compliance.repeatability.mpe is not None else ""
        status_text = f"<b>{compliance.repeatability.status.value}</b>" if idx == 0 else ""
        rep_rows.append([
            Paragraph(r.label, td_style),
            Paragraph(str(session.repeatability.test_load or "-"), td_style),
            Paragraph(str(r.indication or "-"), td_style),
            Paragraph(range_text, td_style),
            Paragraph(mpe_text, td_style),
            Paragraph(status_text, td_style),
        ])
    rep_table = Table(rep_rows, colWidths=[140, 75, 75, 75, 75, 80])
    rep_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d3b66')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d7dbe0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ('PADDING', (0, 0), (-1, -1), 3.5),
    ]))
    story.append(rep_table)
    story.append(Spacer(1, 10))

    # 4. Discrimination Test
    disc = session.discrimination
    d_delta = f"{compliance.discrimination.delta:.4f} kg" if compliance.discrimination.delta is not None else "-"
    d_exp = f"{compliance.discrimination.expected_min:.4f} kg" if compliance.discrimination.expected_min is not None else "-"
    story.append(Paragraph(
        f"<b>4. Discrimination Test (OIML R-76 clause A.4.8)</b> — Status: <b>{compliance.discrimination.status.value}</b>",
        sec_style
    ))
    disc_data = [
        [Paragraph("Test Load", th_style), Paragraph("Reading Before", th_style), Paragraph("Small Increment (1.4d)", th_style), Paragraph("Reading After", th_style), Paragraph("Change Observed", th_style), Paragraph("Status", th_style)],
        [
            Paragraph(str(disc.test_load or "-"), td_style),
            Paragraph(str(disc.reading_before or "-"), td_style),
            Paragraph(str(disc.increment or "-"), td_style),
            Paragraph(str(disc.reading_after or "-"), td_style),
            Paragraph(f"{d_delta} (min: {d_exp})", td_style),
            Paragraph(f"<b>{compliance.discrimination.status.value}</b>", td_bold)
        ]
    ]
    disc_table = Table(disc_data, colWidths=[80, 85, 95, 85, 95, 80])
    disc_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d3b66')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d7dbe0')),
        ('PADDING', (0, 0), (-1, -1), 3.5),
    ]))
    story.append(disc_table)
    story.append(Spacer(1, 10))

    # 5. Linearity Test
    story.append(Paragraph(
        f"<b>5. Linearity & Hysteresis Test</b> — Status: <b>{compliance.linearity.status.value}</b>",
        sec_style
    ))
    story.append(build_test_table(compliance.linearity.rows))
    story.append(Spacer(1, 14))

    # Signatures
    sig_table = Table([
        [
            Paragraph("<b>Testing Officer / Metrologist:</b><br/><br/><br/>_______________________________<br/>" + str(session.tester), td_style),
            Paragraph("<b>Authorised Reviewer / Verification Officer:</b><br/><br/><br/>_______________________________<br/>Directorate of Legal Metrology", td_style)
        ]
    ], colWidths=[260, 260])
    sig_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d7dbe0')),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f9fafb')),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(sig_table)

    doc.build(story)
    return buf.getvalue()


def generate_pdf(session: TestSessionOut, instrument: InstrumentOut, compliance: ComplianceResult) -> bytes:
    """
    Generates a PDF report. Attempts WeasyPrint HTML/CSS rendering first;
    seamlessly falls back to pure-Python ReportLab if GTK runtime is unavailable.
    """
    try:
        from weasyprint import HTML
        env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
        template = env.get_template("report.html")

        html_content = template.render(
            session=session,
            instrument=instrument,
            compliance=compliance
        )
        return HTML(string=html_content, base_url=str(TEMPLATES_DIR)).write_pdf()
    except Exception:
        # Seamless pure-python fallback for Windows host
        return generate_pdf_reportlab(session, instrument, compliance)


def generate_docx(session: TestSessionOut, instrument: InstrumentOut, compliance: ComplianceResult) -> bytes:
    """
    Builds a Word document (.docx) using python-docx with test results and returns it as bytes.
    """
    doc = Document()

    # Header
    heading = doc.add_heading('NAWI Test Report - OIML R-76', 0)
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph(f"Report ID: {session.id}")
    doc.add_paragraph(f"Date: {session.test_date}")
    doc.add_paragraph(f"Tester: {session.tester}")
    doc.add_paragraph(f"Laboratory / Location: {session.lab_location}")

    # Instrument Details
    doc.add_heading('Instrument Details', level=1)
    table_inst = doc.add_table(rows=4, cols=2)
    table_inst.style = 'Table Grid'
    
    table_inst.cell(0, 0).text = f"Manufacturer: {instrument.manufacturer}"
    table_inst.cell(0, 1).text = f"Model: {instrument.model}"
    
    table_inst.cell(1, 0).text = f"Serial Number: {instrument.serial_number or 'N/A'}"
    table_inst.cell(1, 1).text = f"Accuracy Class: {instrument.accuracy_class.value}"
    
    table_inst.cell(2, 0).text = f"Max Capacity: {instrument.max_capacity} kg"
    table_inst.cell(2, 1).text = f"e (Verification Scale Interval): {instrument.e_value} kg"
    
    d_val = instrument.d_value if instrument.d_value is not None else instrument.e_value
    table_inst.cell(3, 0).text = f"d (Scale Interval): {d_val} kg"
    table_inst.cell(3, 1).text = f"Owner: {instrument.owner or 'N/A'}"

    # Environmental Conditions
    doc.add_heading('Environmental Conditions', level=1)
    doc.add_paragraph(f"Temperature: {session.temperature} °C")
    doc.add_paragraph(f"Humidity: {session.humidity} %RH")

    # Helper function for adding test tables
    def add_reading_table(title: str, rows_data: list[Any]):
        doc.add_heading(title, level=2)
        table = doc.add_table(rows=1, cols=6)
        table.style = 'Table Grid'
        hdr_cells = table.rows[0].cells
        headers = ['Point', 'Applied Load', 'Indication', 'Error', 'MPE', 'Status']
        for i, header in enumerate(headers):
            hdr_cells[i].text = header

        for row_data in rows_data:
            row_cells = table.add_row().cells
            row_cells[0].text = str(row_data.label)
            row_cells[1].text = str(row_data.applied_load if row_data.applied_load is not None else "")
            row_cells[2].text = str(row_data.indication if row_data.indication is not None else "")
            row_cells[3].text = str(f"{row_data.error:.3f}" if row_data.error is not None else "")
            row_cells[4].text = str(f"{row_data.mpe:.3f}" if row_data.mpe is not None else "")
            row_cells[5].text = str(row_data.status.value if hasattr(row_data.status, 'value') else row_data.status)

    # Test Results
    doc.add_heading('Test Results', level=1)

    # Eccentricity
    doc.add_paragraph(f"Test Load: {session.eccentricity.test_load} kg")
    add_reading_table("Eccentricity Test", compliance.eccentricity.rows)
    doc.add_paragraph(f"Eccentricity Status: {compliance.eccentricity.status.value}")

    # Repeatability
    doc.add_heading("Repeatability Test", level=2)
    doc.add_paragraph(f"Test Load: {session.repeatability.test_load} kg")
    doc.add_paragraph(f"Calculated Range: {compliance.repeatability.range_value} kg")
    doc.add_paragraph(f"MPE: {compliance.repeatability.mpe} kg")
    doc.add_paragraph(f"Repeatability Status: {compliance.repeatability.status.value}")

    # Discrimination
    doc.add_heading("Discrimination Test", level=2)
    doc.add_paragraph(f"Test Load: {session.discrimination.test_load} kg")
    doc.add_paragraph(f"Reading Before: {session.discrimination.reading_before} kg")
    doc.add_paragraph(f"Increment Added: {session.discrimination.increment} kg")
    doc.add_paragraph(f"Reading After: {session.discrimination.reading_after} kg")
    doc.add_paragraph(f"Calculated Delta: {compliance.discrimination.delta} kg")
    doc.add_paragraph(f"Expected Min Delta: {compliance.discrimination.expected_min} kg")
    doc.add_paragraph(f"Discrimination Status: {compliance.discrimination.status.value}")

    # Linearity
    add_reading_table("Linearity Test", compliance.linearity.rows)
    doc.add_paragraph(f"Linearity Status: {compliance.linearity.status.value}")

    # Overall Verdict
    doc.add_heading('Overall Compliance Verdict', level=1)
    p = doc.add_paragraph()
    run = p.add_run(compliance.overall.value)
    run.bold = True
    run.font.size = Pt(16)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Signature Placeholder
    doc.add_heading('Signatures', level=1)
    sig_table = doc.add_table(rows=2, cols=2)
    sig_table.cell(0, 0).text = "Tester Signature:"
    sig_table.cell(0, 1).text = "Reviewer Signature:"
    sig_table.cell(1, 0).text = "\n\n________________________\n" + str(session.tester)
    sig_table.cell(1, 1).text = "\n\n________________________\n"

    # Save to BytesIO
    f = BytesIO()
    doc.save(f)
    return f.getvalue()
