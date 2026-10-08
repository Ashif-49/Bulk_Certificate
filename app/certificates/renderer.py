import io
import os
from pathlib import Path
from typing import Dict, Any, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Determine font availability and register Unicode TrueType font
FONTS_DIR = Path(__file__).parent / "fonts"
PRIMARY_FONT = "Helvetica"
PRIMARY_FONT_BOLD = "Helvetica-Bold"

def init_fonts():
    """Register TTF fonts for Unicode compatibility, with fallback to standard PDF fonts."""
    global PRIMARY_FONT, PRIMARY_FONT_BOLD
    
    arial_path = FONTS_DIR / "Arial.ttf"
    vera_path = FONTS_DIR / "Vera.ttf"
    vera_bold_path = FONTS_DIR / "VeraBd.ttf"

    try:
        if arial_path.exists():
            pdfmetrics.registerFont(TTFont("CertUnicode", str(arial_path)))
            PRIMARY_FONT = "CertUnicode"
            PRIMARY_FONT_BOLD = "CertUnicode"
        elif vera_path.exists() and vera_bold_path.exists():
            pdfmetrics.registerFont(TTFont("CertUnicode", str(vera_path)))
            pdfmetrics.registerFont(TTFont("CertUnicode-Bold", str(vera_bold_path)))
            PRIMARY_FONT = "CertUnicode"
            PRIMARY_FONT_BOLD = "CertUnicode-Bold"
    except Exception:
        # Fallback to built-in standard PDF fonts
        PRIMARY_FONT = "Helvetica"
        PRIMARY_FONT_BOLD = "Helvetica-Bold"

init_fonts()


def render_certificate(data: Dict[str, Any]) -> bytes:
    """
    Pure function rendering an elegant A4 landscape certificate PDF from input data.
    
    Why: Pure function returning bytes ensures easy isolated unit testing and mocking
    without disk I/O side effects. The service handles atomic file writing.
    
    Data keys:
        - recipient_name: str
        - event_name: str
        - issuer_name: str
        - issue_date: str
        - certificate_number: str
        - course_title: Optional[str]
    """
    recipient_name = data.get("recipient_name", "").strip() or "Valued Participant"
    event_name = data.get("event_name", "").strip() or "Special Event"
    issuer_name = data.get("issuer_name", "").strip() or "Authorized Issuer"
    issue_date = data.get("issue_date", "").strip() or "2026-01-01"
    certificate_number = data.get("certificate_number", "").strip() or "CERT-0000"
    course_title = data.get("course_title")

    buffer = io.BytesIO()
    # pageCompression=0 ensures PDF text streams can be inspected directly or via pypdf
    c = canvas.Canvas(buffer, pagesize=landscape(A4), pageCompression=0)
    width, height = landscape(A4)

    # 1. Background Fill: subtle warm ivory/cream
    c.setFillColor(colors.HexColor("#FCFDFD"))
    c.rect(0, 0, width, height, fill=1, stroke=0)

    # 2. Decorative Double Border
    # Outer dark slate border
    c.setStrokeColor(colors.HexColor("#1E293B"))
    c.setLineWidth(3.0)
    c.rect(24, 24, width - 48, height - 48)

    # Inner warm amber/gold border
    c.setStrokeColor(colors.HexColor("#D97706"))
    c.setLineWidth(1.2)
    c.rect(32, 32, width - 64, height - 64)

    # Corner decorative marks (small accent squares)
    corner_size = 6
    c.setFillColor(colors.HexColor("#D97706"))
    for cx in [32, width - 32 - corner_size]:
        for cy in [32, height - 32 - corner_size]:
            c.rect(cx, cy, corner_size, corner_size, fill=1, stroke=0)

    # 3. Top Header / Title
    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont(PRIMARY_FONT_BOLD, 26)
    c.drawCentredString(width / 2.0, height - 100, "CERTIFICATE OF COMPLETION")

    # Thin decorative line below title
    c.setStrokeColor(colors.HexColor("#CBD5E1"))
    c.setLineWidth(1)
    c.line(width / 2.0 - 140, height - 114, width / 2.0 + 140, height - 114)

    # Subtitle: "This is to certify that"
    c.setFillColor(colors.HexColor("#475569"))
    c.setFont(PRIMARY_FONT, 13)
    c.drawCentredString(width / 2.0, height - 142, "THIS IS PROUDLY PRESENTED TO")

    # 4. Recipient Name with dynamic auto-shrink to prevent overflow
    max_name_width = width - 160
    name_font_size = 34
    
    # Measure and scale down font size if name is very long
    measured_width = c.stringWidth(recipient_name, PRIMARY_FONT_BOLD, name_font_size)
    if measured_width > max_name_width:
        ratio = max_name_width / measured_width
        name_font_size = max(14, int(name_font_size * ratio))

    c.setFillColor(colors.HexColor("#1E3A8A"))  # Deep royal blue
    c.setFont(PRIMARY_FONT_BOLD, name_font_size)
    c.drawCentredString(width / 2.0, height - 200, recipient_name)

    # Name underline
    name_line_w = min(max(measured_width, 180), max_name_width)
    c.setStrokeColor(colors.HexColor("#93C5FD"))
    c.setLineWidth(1.5)
    c.line(width / 2.0 - name_line_w / 2.0, height - 212, width / 2.0 + name_line_w / 2.0, height - 212)

    # 5. Course / Event description
    c.setFillColor(colors.HexColor("#475569"))
    c.setFont(PRIMARY_FONT, 13)
    c.drawCentredString(width / 2.0, height - 248, "for successfully participating in and completing")

    # Event Name
    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont(PRIMARY_FONT_BOLD, 18)
    c.drawCentredString(width / 2.0, height - 280, event_name)

    # Optional Course Title
    curr_y = height - 310
    if course_title:
        c.setFillColor(colors.HexColor("#334155"))
        c.setFont(PRIMARY_FONT, 14)
        c.drawCentredString(width / 2.0, curr_y, f"Specialization: {course_title}")
        curr_y -= 25

    # 6. Bottom metadata: Date (left) and Issuer signature (right)
    col_left_x = 100
    col_right_x = width - 240
    meta_y = 100

    # Date Section
    c.setFillColor(colors.HexColor("#64748B"))
    c.setFont(PRIMARY_FONT, 10)
    c.drawString(col_left_x, meta_y + 20, "DATE OF ISSUANCE")
    
    c.setFillColor(colors.HexColor("#1E293B"))
    c.setFont(PRIMARY_FONT_BOLD, 12)
    c.drawString(col_left_x, meta_y + 4, issue_date)

    c.setStrokeColor(colors.HexColor("#94A3B8"))
    c.setLineWidth(0.8)
    c.line(col_left_x, meta_y, col_left_x + 160, meta_y)

    # Signature & Issuer Section
    c.setStrokeColor(colors.HexColor("#94A3B8"))
    c.setLineWidth(0.8)
    c.line(col_right_x, meta_y, col_right_x + 160, meta_y)

    c.setFillColor(colors.HexColor("#1E293B"))
    c.setFont(PRIMARY_FONT_BOLD, 12)
    c.drawString(col_right_x, meta_y - 14, issuer_name)

    c.setFillColor(colors.HexColor("#64748B"))
    c.setFont(PRIMARY_FONT, 10)
    c.drawString(col_right_x, meta_y - 28, "AUTHORIZED SIGNATURE")

    # 7. Certificate ID and Verification Footer
    footer_y = 48
    c.setFillColor(colors.HexColor("#94A3B8"))
    c.setFont(PRIMARY_FONT, 9)
    c.drawString(48, footer_y, f"CERTIFICATE ID: {certificate_number}")
    c.drawRightString(width - 48, footer_y, "Verified Document • Bulk Certificate Generator")

    c.showPage()
    c.save()

    buffer.seek(0)
    return buffer.getvalue()
