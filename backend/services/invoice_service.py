"""Invoice PDF generation service using reportlab."""
from __future__ import annotations

import io
import urllib.request
from typing import Any, Dict, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image,
)
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER


def _fetch_logo(url: str, max_w: float = 40 * mm, max_h: float = 14 * mm):
    """Fetch an image from a URL and return a reportlab Image or None."""
    try:
        with urllib.request.urlopen(url, timeout=4) as resp:
            data = resp.read()
        img = Image(io.BytesIO(data))
        # Scale proportionally
        ratio = img.imageWidth / img.imageHeight
        if img.imageWidth > max_w:
            img.drawWidth = max_w
            img.drawHeight = max_w / ratio
        if img.drawHeight > max_h:
            img.drawHeight = max_h
            img.drawWidth = max_h * ratio
        return img
    except Exception:
        return None


def _safe_str(v: Any, fallback: str = "—") -> str:
    return str(v) if v not in (None, "", []) else fallback


def generate_partner_invoice_pdf(
    order: Dict[str, Any],
    partner_org: Dict[str, Any],
    invoice_settings: Optional[Dict[str, Any]] = None,
    platform_name: str = "Automate Accounts",
) -> bytes:
    """Generate a professional A4 PDF invoice for a partner order.

    Returns raw PDF bytes.
    """
    if invoice_settings is None:
        invoice_settings = {}

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Invoice {order.get('order_number', '')}",
    )

    W = A4[0] - 40 * mm  # usable width

    styles = getSampleStyleSheet()

    # ── Custom styles ──────────────────────────────────────────────────────────
    h1 = ParagraphStyle("h1", parent=styles["Normal"], fontSize=26, textColor=colors.HexColor("#0f172a"),
                         spaceAfter=2, fontName="Helvetica-Bold", alignment=TA_LEFT)
    h3 = ParagraphStyle("h3", parent=styles["Normal"], fontSize=10, textColor=colors.HexColor("#0f172a"),
                         fontName="Helvetica-Bold")
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=9, leading=14,
                           textColor=colors.HexColor("#334155"))
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8, leading=12,
                            textColor=colors.HexColor("#64748b"))
    right = ParagraphStyle("right", parent=styles["Normal"], fontSize=9, leading=14,
                            textColor=colors.HexColor("#334155"), alignment=TA_RIGHT)
    right_bold = ParagraphStyle("right_bold", parent=styles["Normal"], fontSize=10, leading=14,
                                 textColor=colors.HexColor("#0f172a"), alignment=TA_RIGHT,
                                 fontName="Helvetica-Bold")
    label_style = ParagraphStyle("label", parent=styles["Normal"], fontSize=7, leading=10,
                                  textColor=colors.HexColor("#94a3b8"), fontName="Helvetica-BoldOblique",
                                  spaceAfter=2)

    ACCENT = colors.HexColor("#0ea5e9")   # sky-500
    LIGHT_BG = colors.HexColor("#f8fafc")  # slate-50
    BORDER = colors.HexColor("#e2e8f0")

    # ── Data helpers ───────────────────────────────────────────────────────────
    inv_date = (order.get("invoice_date") or order.get("created_at") or "")[:10]
    due_date = (order.get("due_date") or "")[:10]
    order_number = order.get("order_number", "—")
    amount = float(order.get("amount") or 0)
    currency = order.get("currency", "GBP")
    description = order.get("description") or "Subscription billing"
    plan_name = order.get("plan_name", "")

    partner_name = partner_org.get("name", order.get("partner_name", "—"))
    partner_addr = partner_org.get("address") or {}
    partner_email = partner_org.get("admin_email", "")

    payment_terms = invoice_settings.get("payment_terms") or "Due on receipt"
    footer_notes = invoice_settings.get("footer_notes") or ""
    company_email = invoice_settings.get("company_email") or ""
    company_phone = invoice_settings.get("company_phone") or ""
    company_address = invoice_settings.get("company_address") or ""
    vat_number = invoice_settings.get("vat_number") or ""
    logo_url = invoice_settings.get("logo_url") or ""
    bank_details: Dict[str, str] = invoice_settings.get("bank_details") or {}
    prefix = invoice_settings.get("prefix") or "PINV"

    invoice_number = f"{prefix}-{order_number}"

    # ── Build story ────────────────────────────────────────────────────────────
    story = []

    # ── Header row: INVOICE title + company name/logo ─────────────────────────
    logo_img = _fetch_logo(logo_url) if logo_url else None
    company_cell = logo_img if logo_img else Paragraph(platform_name, h3)

    header_data = [
        [Paragraph("INVOICE", h1), company_cell],
    ]
    header_tbl = Table(header_data, colWidths=[W * 0.6, W * 0.4])
    header_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
    ]))
    story.append(header_tbl)
    # Show company name below logo if logo present
    if logo_img:
        story.append(Paragraph(f'<para alignment="right"><font size="8" color="#64748b">{platform_name}</font></para>', body))
    story.append(HRFlowable(width=W, thickness=2, color=ACCENT, spaceAfter=6))

    # ── Invoice meta + Bill To ─────────────────────────────────────────────────
    bill_to_lines = [Paragraph("BILL TO", label_style)]
    bill_to_lines.append(Paragraph(f"<b>{partner_name}</b>", body))
    if partner_email:
        bill_to_lines.append(Paragraph(partner_email, small))
    if partner_addr.get("line1"):
        bill_to_lines.append(Paragraph(partner_addr["line1"], small))
    city_line = ", ".join(filter(None, [partner_addr.get("city"), partner_addr.get("region"), partner_addr.get("postal")]))
    if city_line:
        bill_to_lines.append(Paragraph(city_line, small))
    if partner_addr.get("country"):
        bill_to_lines.append(Paragraph(partner_addr["country"], small))

    meta_lines = [
        Paragraph("INVOICE NO.", label_style),
        Paragraph(f"<b>{invoice_number}</b>", body),
        Spacer(1, 6),
        Paragraph("INVOICE DATE", label_style),
        Paragraph(inv_date or "—", body),
        Spacer(1, 6),
        Paragraph("DUE DATE", label_style),
        Paragraph(due_date or payment_terms, body),
    ]

    meta_data = [[bill_to_lines, meta_lines]]
    meta_tbl = Table(meta_data, colWidths=[W * 0.55, W * 0.45])
    meta_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
        ("PADDING", (0, 0), (-1, -1), 12),
    ]))
    story.append(Spacer(1, 8))
    story.append(meta_tbl)
    story.append(Spacer(1, 16))

    # ── Line items table ───────────────────────────────────────────────────────
    item_header = [
        Paragraph("DESCRIPTION", label_style),
        Paragraph("PLAN", label_style),
        Paragraph("AMOUNT", ParagraphStyle("lbl_r", parent=label_style, alignment=TA_RIGHT)),
    ]
    item_row = [
        Paragraph(description, body),
        Paragraph(plan_name or "—", small),
        Paragraph(f"<b>{currency} {amount:,.2f}</b>", right_bold),
    ]

    items_tbl = Table(
        [item_header, item_row],
        colWidths=[W * 0.55, W * 0.2, W * 0.25],
    )
    items_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 1), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white]),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
    ]))
    story.append(items_tbl)

    # ── Totals ─────────────────────────────────────────────────────────────────
    totals_data = [
        [Paragraph("Subtotal", right), Paragraph(f"{currency} {amount:,.2f}", right)],
        [Paragraph("Tax", right), Paragraph("—", right)],
        [Paragraph("<b>TOTAL DUE</b>", right_bold), Paragraph(f"<b>{currency} {amount:,.2f}</b>", right_bold)],
    ]
    totals_tbl = Table(totals_data, colWidths=[W * 0.75, W * 0.25])
    totals_tbl.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEABOVE", (0, 2), (-1, 2), 1, colors.HexColor("#0f172a")),
        ("BACKGROUND", (0, 2), (-1, 2), LIGHT_BG),
    ]))
    story.append(totals_tbl)
    story.append(Spacer(1, 20))

    # ── Payment terms + footer ─────────────────────────────────────────────────
    story.append(HRFlowable(width=W, thickness=0.5, color=BORDER, spaceAfter=8))

    # Bank details block
    bd_fields = [
        ("Bank", bank_details.get("bank_name")),
        ("Account Name", bank_details.get("account_name")),
        ("Account Number", bank_details.get("account_number")),
        ("Sort Code", bank_details.get("sort_code")),
        ("IBAN", bank_details.get("iban")),
        ("BIC / SWIFT", bank_details.get("bic")),
    ]
    bd_rows = [(label, val) for label, val in bd_fields if val]
    if bd_rows:
        story.append(Paragraph("<b>Bank Details</b>", ParagraphStyle("bd_hdr", parent=small, fontName="Helvetica-Bold", textColor=colors.HexColor("#0f172a"))))
        story.append(Spacer(1, 3))
        bd_table_data = [[Paragraph(f"<b>{lbl}:</b>", small), Paragraph(val, small)] for lbl, val in bd_rows]
        bd_tbl = Table(bd_table_data, colWidths=[W * 0.25, W * 0.75])
        bd_tbl.setStyle(TableStyle([
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(bd_tbl)
        story.append(Spacer(1, 8))
        story.append(HRFlowable(width=W, thickness=0.5, color=BORDER, spaceAfter=8))

    if payment_terms:
        story.append(Paragraph(f"<b>Payment Terms:</b> {payment_terms}", small))
        story.append(Spacer(1, 4))
    if vat_number:
        story.append(Paragraph(f"VAT Registration No: {vat_number}", small))
        story.append(Spacer(1, 4))
    if company_email or company_phone:
        contact = " · ".join(filter(None, [company_email, company_phone]))
        story.append(Paragraph(contact, small))
        story.append(Spacer(1, 4))
    if company_address:
        story.append(Paragraph(company_address, small))
        story.append(Spacer(1, 4))
    if footer_notes:
        story.append(Spacer(1, 8))
        story.append(Paragraph(footer_notes, small))

    doc.build(story)
    return buf.getvalue()
