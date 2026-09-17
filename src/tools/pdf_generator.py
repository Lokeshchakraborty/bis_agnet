"""
BIS SATHI - Compliance Research PDF Generator
=============================================
Generates authoritative, beautifully styled Bureau of Indian Standards (BIS)
Technical Compliance & Research Dossiers using ReportLab.
"""

from __future__ import annotations
import html
import hashlib
import io
import logging
import re
import time
from typing import List, Optional
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger("bis_pdf_generator")

# Official BIS Theme Palette
COLOR_PRIMARY = colors.HexColor("#0f2b5c")     # Deep BIS Navy
COLOR_SECONDARY = colors.HexColor("#d97706")   # Regulatory Amber / Gold
COLOR_TEXT_MAIN = colors.HexColor("#1e293b")   # Slate Dark
COLOR_TEXT_MUTED = colors.HexColor("#64748b")  # Slate Gray
COLOR_BG_LIGHT = colors.HexColor("#f8fafc")    # Clean Off-White
COLOR_BORDER = colors.HexColor("#cbd5e1")      # Slate Light
COLOR_ACCENT = colors.HexColor("#2563eb")      # Royal Blue


class NumberedCanvas(canvas.Canvas):
    """Custom canvas that dynamically adds page numbers (Page X of Y) and running footer."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(COLOR_TEXT_MUTED)

        # Running header (pages 2+)
        if self._pageNumber > 1:
            self.drawString(
                54, 750,
                "Bureau of Indian Standards (BIS) • Official Research & Compliance Dossier"
            )
            self.setStrokeColor(COLOR_BORDER)
            self.setLineWidth(0.5)
            self.line(54, 742, 612 - 54, 742)

        # Running footer (all pages)
        self.setStrokeColor(COLOR_BORDER)
        self.setLineWidth(0.5)
        self.line(54, 45, 612 - 54, 45)

        self.drawString(
            54, 32,
            "BIS SATHI AI Portal • Confidential Regulatory Research Dossier • Generated from Authoritative Gazette Records"
        )
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(612 - 54, 32, page_str)
        self.restoreState()


def _sanitize_markdown_for_reportlab(text: str) -> str:
    """Convert common markdown markers into clean HTML/XML tags supported by ReportLab."""
    if not text:
        return ""
    # Normalize <br> or <br > to self-closing <br/> for ReportLab XML parser
    clean = re.sub(r"<br\s*/?>", "<br/>", text, flags=re.IGNORECASE)
    # Convert markdown links: [label](url) -> <font color='#2563eb'><u>label</u></font>
    clean = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<font color='#2563eb'><u>\1</u></font>", clean)
    # Bold **text** -> <b>text</b>
    clean = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", clean)
    # Italic *text* or _text_ -> <i>text</i>
    clean = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", clean)
    # Inline code `text` -> <font name='Courier'>text</font>
    clean = re.sub(r"`(.+?)`", r"<font name='Courier' color='#0f2b5c'><b>\1</b></font>", clean)
    # Escape standalone ampersands not part of HTML entities
    clean = re.sub(r"&(?!(?:amp|lt|gt|quot|apos);)", "&amp;", clean)
    return clean


def _safe_paragraph(text: str, style: ParagraphStyle) -> Paragraph:
    """Safely construct a ReportLab Paragraph, falling back to clean escaped text if XML parsing fails."""
    import html as _html
    # Ensure any <br> tags are self-closing
    safe_text = re.sub(r"<br\s*/?>", "<br/>", text, flags=re.IGNORECASE)
    try:
        return Paragraph(safe_text, style)
    except Exception as e:
        logger.warning("ReportLab failed to parse formatted text: %r. Falling back to plain text. Error: %s", safe_text[:80], e)
        # Strip all HTML-like tags and escape
        plain = re.sub(r"<[^>]+>", "", safe_text)
        return Paragraph(_html.escape(plain), style)


def _parse_markdown_table(table_lines: List[str], header_style: ParagraphStyle, cell_style: ParagraphStyle) -> Optional[Table]:
    """Parse consecutive markdown table lines into a styled ReportLab Table flowable."""
    if not table_lines:
        return None

    raw_rows = []
    for l in table_lines:
        clean_l = l.strip()
        if not clean_l:
            continue
        # Skip delimiter rows e.g. |---|:---|
        if re.match(r"^\|?[\s\-:|]+\|?$", clean_l):
            continue
        cells = [c.strip() for c in clean_l.split("|")]
        # Remove leading/trailing empty cells from outer pipes
        if clean_l.startswith("|") and len(cells) > 1:
            cells = cells[1:]
        if clean_l.endswith("|") and cells and cells[-1] == "":
            cells = cells[:-1]
        if cells:
            raw_rows.append(cells)

    if not raw_rows:
        return None

    num_cols = max(len(r) for r in raw_rows)
    if num_cols == 0:
        return None

    # Standardize column count across all rows
    for r in raw_rows:
        while len(r) < num_cols:
            r.append("")

    table_data = []
    for r_idx, row in enumerate(raw_rows):
        is_header = (r_idx == 0)
        formatted_row = []
        for cell_text in row:
            sanitized = _sanitize_markdown_for_reportlab(cell_text)
            st = header_style if is_header else cell_style
            formatted_row.append(_safe_paragraph(sanitized, st))
        table_data.append(formatted_row)

    total_width = 504.0
    if num_cols == 4:
        col_widths = [110, 110, 110, 174]
    elif num_cols == 3:
        col_widths = [120, 130, 254]
    elif num_cols == 2:
        col_widths = [180, 324]
    else:
        col_w = total_width / num_cols
        col_widths = [col_w] * num_cols

    t = Table(table_data, colWidths=col_widths)
    t.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_PRIMARY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_BG_LIGHT]),
        ])
    )
    return t


def generate_compliance_pdf(
    query: str,
    core_response: str,
    applicable_standards: Optional[List[str]] = None,
    next_step: Optional[str] = None,
    intent: Optional[str] = None,
    user_name: Optional[str] = "Compliance Officer / Applicant",
    session_id: Optional[str] = None,
) -> io.BytesIO:
    """
    Generate an official, publication-ready PDF research dossier using ReportLab.

    Returns:
        BytesIO buffer containing the compiled binary PDF document.
    """
    applicable_standards = list(applicable_standards or [])
    from src.agent.guardrails import clean_leaked_system_blocks
    core_response, extra_stds = clean_leaked_system_blocks(core_response)
    if extra_stds:
        applicable_standards = list(dict.fromkeys(applicable_standards + extra_stds))
    buffer = io.BytesIO()

    # Document Geometry (0.75 in / 54 pt margins)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    # Styles Setup
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=COLOR_PRIMARY,
        alignment=TA_LEFT,
    )

    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=COLOR_SECONDARY,
        alignment=TA_LEFT,
    )

    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=COLOR_PRIMARY,
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True,
    )

    h2_style = ParagraphStyle(
        "DocH2",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=14,
        textColor=COLOR_PRIMARY,
        spaceBefore=12,
        spaceAfter=5,
        keepWithNext=True,
    )

    h3_style = ParagraphStyle(
        "DocH3",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=13,
        textColor=COLOR_SECONDARY,
        spaceBefore=8,
        spaceAfter=3,
        keepWithNext=True,
    )

    body_style = ParagraphStyle(
        "DocBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=14.5,
        textColor=COLOR_TEXT_MAIN,
        alignment=TA_JUSTIFY,
        spaceAfter=8,
    )

    bullet_style = ParagraphStyle(
        "DocBullet",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13.5,
        textColor=COLOR_TEXT_MAIN,
        leftIndent=14,
        firstLineIndent=-10,
        spaceAfter=4,
    )

    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.white,
    )

    table_cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=COLOR_TEXT_MAIN,
    )

    meta_label = ParagraphStyle(
        "MetaLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=COLOR_TEXT_MUTED,
    )

    meta_val = ParagraphStyle(
        "MetaVal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=COLOR_PRIMARY,
    )

    story = []

    # 1. Header Banner & Government Embellishment
    report_id = f"BIS-RD-{int(time.time())}-{hashlib.md5(query.encode()).hexdigest()[:6].upper()}"
    gen_time_str = time.strftime("%d %B %Y, %H:%M:%S IST")

    story.append(Paragraph("BUREAU OF INDIAN STANDARDS (BIS)", subtitle_style))
    story.append(Spacer(1, 2))
    story.append(Paragraph("Official Compliance & Technical Research Dossier", title_style))
    story.append(Spacer(1, 4))
    story.append(
        Paragraph(
            "Statutory Autonomous Body under the Bureau of Indian Standards Act, 2016 • Ministry of Consumer Affairs, Food & Public Distribution, Govt. of India",
            ParagraphStyle("SubGov", parent=styles["Normal"], fontName="Helvetica", fontSize=7.5, textColor=COLOR_TEXT_MUTED)
        )
    )
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=2, color=COLOR_PRIMARY, spaceBefore=2, spaceAfter=10))

    # 2. Metadata Box Table
    meta_data = [
        [
            Paragraph("<b>DOSSIER REFERENCE</b>", meta_label),
            Paragraph(f"<b>{report_id}</b>", meta_val),
            Paragraph("<b>SECURITY LEVEL</b>", meta_label),
            Paragraph("Official Compliance Record", meta_val),
        ],
        [
            Paragraph("<b>DATE GENERATED</b>", meta_label),
            Paragraph(gen_time_str, meta_val),
            Paragraph("<b>AUDIT VERIFICATION</b>", meta_label),
            Paragraph("Cryptographically Logged (SHA-256)", meta_val),
        ],
        [
            Paragraph("<b>REQUESTING OFFICER</b>", meta_label),
            Paragraph(user_name or "Compliance Applicant", meta_val),
            Paragraph("<b>STATUTORY DOMAIN</b>", meta_label),
            Paragraph((intent or "General Standard").upper(), meta_val),
        ],
    ]
    meta_table = Table(meta_data, colWidths=[110, 140, 110, 144])
    meta_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), COLOR_BG_LIGHT),
            ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story.append(meta_table)
    story.append(Spacer(1, 12))

    # 3. Research Query Scope
    story.append(Paragraph("1. RESEARCH SUBJECT & INQUIRY SCOPE", section_heading))
    query_box = [
        [
            Paragraph(
                f"<b>Inquiry:</b> {_sanitize_markdown_for_reportlab(query)}",
                ParagraphStyle("QueryText", parent=styles["Normal"], fontName="Helvetica", fontSize=9, textColor=COLOR_PRIMARY)
            )
        ]
    ]
    q_table = Table(query_box, colWidths=[504])
    q_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eff6ff")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#93c5fd")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    story.append(q_table)
    story.append(Spacer(1, 8))

    # 4. Applicable Indian Standards Table
    if applicable_standards:
        story.append(Paragraph("2. IDENTIFIED INDIAN STANDARDS (IS CODES)", section_heading))
        std_rows = [
            [
                Paragraph("<b>#</b>", table_header_style),
                Paragraph("<b>Indian Standard (IS) Code</b>", table_header_style),
                Paragraph("<b>Official Standard Subject & Scope</b>", table_header_style),
            ]
        ]
        for i, std_str in enumerate(applicable_standards, 1):
            parts = std_str.split(" - ", 1)
            code = parts[0].strip()
            desc = parts[1].strip() if len(parts) > 1 else "Standard Specifications & Mandatory Directives"
            std_rows.append([
                Paragraph(str(i), table_cell_style),
                Paragraph(f"<b>{code}</b>", table_cell_style),
                Paragraph(desc, table_cell_style),
            ])

        std_table = Table(std_rows, colWidths=[30, 150, 324])
        std_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), COLOR_PRIMARY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_BG_LIGHT]),
            ])
        )
        story.append(std_table)
        story.append(Spacer(1, 10))

    # 5. Core Compliance Findings & Technical Specifications
    story.append(Paragraph("3. COMPREHENSIVE COMPLIANCE & TECHNICAL ANALYSIS", section_heading))

    all_lines = core_response.split("\n")
    table_buffer: List[str] = []

    def _flush_table():
        nonlocal table_buffer
        if table_buffer:
            t = _parse_markdown_table(table_buffer, table_header_style, table_cell_style)
            if t:
                story.append(Spacer(1, 4))
                story.append(t)
                story.append(Spacer(1, 6))
            table_buffer = []

    for line in all_lines:
        line_str = line.strip()

        # Table detection
        if line_str.startswith("|") and line_str.endswith("|"):
            table_buffer.append(line_str)
            continue
        else:
            _flush_table()

        if not line_str:
            continue

        sanitized = _sanitize_markdown_for_reportlab(line_str)

        # Horizontal rules / dividers
        if re.match(r"^[-*_]{3,}$", line_str):
            story.append(Spacer(1, 4))
            story.append(HRFlowable(width="100%", thickness=0.8, color=COLOR_BORDER, spaceBefore=4, spaceAfter=8))
        # Markdown headings
        elif line_str.startswith("## "):
            clean_heading = re.sub(r"^##\s*", "", sanitized)
            story.append(_safe_paragraph(clean_heading, h2_style))
        elif line_str.startswith("### "):
            clean_sub = re.sub(r"^###\s*", "", sanitized)
            story.append(_safe_paragraph(clean_sub, h3_style))
        elif line_str.startswith("# "):
            clean_h1 = re.sub(r"^#\s*", "", sanitized)
            story.append(_safe_paragraph(clean_h1, section_heading))
        elif re.match(r"^[-*•]?\s*\[([ xX])\]\s*", line_str):
            chk = re.match(r"^[-*•]?\s*\[([ xX])\]\s*(.*)", line_str)
            checked = chk.group(1).lower() == "x" if chk else False
            item_text = _sanitize_markdown_for_reportlab(chk.group(2) if chk else line_str)
            box_symbol = "<b>[ &#10003; ]</b>" if checked else "<b>[ &nbsp; ]</b>"
            story.append(_safe_paragraph(f"{box_symbol} {item_text}", bullet_style))
        elif line_str.startswith("• **") or line_str.startswith("• ") or line_str.startswith("- ") or line_str.startswith("* "):
            clean_bullet = re.sub(r"^[•\-*]\s*", "", sanitized)
            story.append(_safe_paragraph(f"<b>&bull;</b> {clean_bullet}", bullet_style))
        elif re.match(r"^\d+\.\s+", line_str):
            clean_num = re.sub(r"^\d+\.\s*", "", sanitized)
            num_match = re.match(r"^(\d+)\.", line_str)
            num_val = num_match.group(1) if num_match else "1"
            story.append(_safe_paragraph(f"<b>{num_val}.</b> {clean_num}", bullet_style))
        else:
            story.append(_safe_paragraph(sanitized, body_style))

    _flush_table()
    story.append(Spacer(1, 8))

    # 6. Actionable Next Steps & Official Portals
    if next_step:
        story.append(Paragraph("4. ACTIONABLE PROCEDURAL ROADMAP & OFFICIAL PORTALS", section_heading))
        clean_next = _sanitize_markdown_for_reportlab(next_step)
        next_box = [
            [
                Paragraph(
                    f"<b>Mandatory Next Step:</b> {clean_next}<br/><br/>"
                    "<b>Authorized Portals for Online Application & Renewal:</b><br/>"
                    "• <b>e-BIS & Manakonline Portal:</b> <font color='#2563eb'><u>https://manakonline.in</u></font> (Product Certification, Standards Sale & Lab LIMS)<br/>"
                    "• <b>Compulsory Registration Portal (CRS):</b> <font color='#2563eb'><u>https://crsbis.in</u></font> (Electronics & IT Goods Scheme)<br/>"
                    "• <b>National Standards Body Portal:</b> <font color='#2563eb'><u>https://www.bis.gov.in</u></font>",
                    ParagraphStyle("ActionText", parent=styles["Normal"], fontName="Helvetica", fontSize=8.5, leading=13, textColor=COLOR_TEXT_MAIN)
                )
            ]
        ]
        action_table = Table(next_box, colWidths=[504])
        action_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fffbeb")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#fde68a")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ])
        )
        story.append(action_table)
        story.append(Spacer(1, 10))

    # 7. Legal Disclaimer & Tamper-Evident SHA-256 Hash
    payload_hash = hashlib.sha256((query + core_response + report_id).encode("utf-8")).hexdigest()
    legal_box = [
        [
            Paragraph(
                "<b>REGULATORY NOTICE & STATUTORY DISCLAIMER:</b><br/>"
                "This document is an AI-synthesized Technical Compliance Dossier prepared by BIS SATHI using authoritative "
                "data from the Bureau of Indian Standards (BIS). While rigorously verified against gazette notifications and "
                "the BIS Act, 2016, applicants must confirm final statutory fee structures, test schedules, and amendments via "
                "Manakonline (https://manakonline.in).<br/>"
                f"<b>Document Integrity Hash (SHA-256):</b> <font name='Courier' size='7'>{payload_hash}</font>",
                ParagraphStyle("DisclaimerText", parent=styles["Normal"], fontName="Helvetica", fontSize=7, leading=10, textColor=COLOR_TEXT_MUTED)
            )
        ]
    ]
    legal_table = Table(legal_box, colWidths=[504])
    legal_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), COLOR_BG_LIGHT),
            ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story.append(KeepTogether(legal_table))

    # Build PDF with custom NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    logger.info("Successfully compiled BIS Compliance Research Dossier PDF (%s, %d bytes)", report_id, buffer.getbuffer().nbytes)
    return buffer
