"""Simple enquiry submission PDF generation using ReportLab."""
from __future__ import annotations

import io
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle,
)

FIELD_LABELS: Dict[str, str] = {
    "name": "Name",
    "email": "Email",
    "company": "Company",
    "phone": "Phone",
    "message": "Message",
    "project_summary": "Project Summary",
    "desired_outcomes": "Desired Outcomes",
    "apps_involved": "Apps Involved",
    "timeline_urgency": "Timeline / Urgency",
    "budget_range": "Budget Range",
    "additional_notes": "Additional Notes",
}


def generate_enquiry_pdf(
    order_number: str,
    created_at: str,
    customer_name: str,
    customer_email: str,
    products: List[str],
    scope_form_data: Dict[str, Any],
    status: str = "",
) -> bytes:
    """Generate a simple labelled-field PDF for an enquiry submission."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "EnqTitle",
        parent=styles["Heading1"],
        fontSize=18,
        spaceAfter=4,
        textColor=colors.HexColor("#0f172a"),
        fontName="Helvetica-Bold",
    )
    subtitle_style = ParagraphStyle(
        "EnqSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=12,
    )
    label_style = ParagraphStyle(
        "EnqLabel",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#94a3b8"),
        spaceBefore=8,
        spaceAfter=2,
        fontName="Helvetica-Bold",
        leading=10,
    )
    value_style = ParagraphStyle(
        "EnqValue",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=4,
        leading=14,
    )

    story = []

    story.append(Paragraph("Enquiry Submission", title_style))
    story.append(Paragraph(f"Reference: {order_number}", subtitle_style))
    story.append(
        HRFlowable(
            width="100%", thickness=1,
            color=colors.HexColor("#e2e8f0"), spaceAfter=12,
        )
    )

    created_str = (
        created_at[:16].replace("T", " ") if created_at else "—"
    )
    meta_data = [
        ["Customer", customer_name or "—"],
        ["Email", customer_email or "—"],
        ["Date", created_str],
        ["Status", status.replace("_", " ").title() if status else "—"],
        ["Products", ", ".join(products) if products else "—"],
    ]
    meta_table = Table(meta_data, colWidths=[40 * mm, 130 * mm])
    meta_table.setStyle(
        TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#64748b")),
            ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#1e293b")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1),
             [colors.HexColor("#f8fafc"), colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ])
    )
    story.append(meta_table)
    story.append(Spacer(1, 8 * mm))

    story.append(Paragraph("SUBMITTED FORM DATA", label_style))
    story.append(
        HRFlowable(
            width="100%", thickness=0.5,
            color=colors.HexColor("#e2e8f0"), spaceAfter=6,
        )
    )

    fd = scope_form_data or {}
    rows: List[tuple] = []
    for key, label in FIELD_LABELS.items():
        val = fd.get(key)
        if val:
            rows.append((label, str(val)))
    for key, val in (fd.get("extra_fields") or {}).items():
        if val:
            label = key.replace("_", " ").title()
            rows.append((label, str(val)))

    if rows:
        for label, value in rows:
            story.append(Paragraph(label.upper(), label_style))
            story.append(Paragraph(value, value_style))
    else:
        story.append(Paragraph("No form data was submitted.", value_style))

    doc.build(story)
    return buffer.getvalue()
