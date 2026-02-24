"""
PDF generation service for Terms of Service and other documents.

Uses ReportLab for PDF generation.
"""
from __future__ import annotations

import io
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from html import unescape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)


def strip_html(text: str) -> str:
    """Remove HTML tags and decode entities."""
    if not text:
        return ""
    # Remove HTML tags
    clean = re.sub(r'<[^>]+>', '', text)
    # Decode HTML entities
    clean = unescape(clean)
    # Normalize whitespace
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean


def html_to_paragraphs(html_content: str) -> list[str]:
    """
    Convert HTML content to a list of paragraph texts.
    Handles <h1>, <h2>, <h3>, <p>, <li> tags.
    """
    if not html_content:
        return []
    
    paragraphs = []
    
    # Split by common block tags
    # First, normalize the HTML
    content = html_content.replace('\n', ' ').replace('\r', '')
    
    # Extract headings and paragraphs
    # Match <h1>, <h2>, <h3>, <p>, <li>
    pattern = r'<(h[1-3]|p|li)[^>]*>(.*?)</\1>'
    matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
    
    for tag, text in matches:
        clean_text = strip_html(text).strip()
        if clean_text:
            if tag.lower().startswith('h'):
                paragraphs.append(('heading', clean_text, tag.lower()))
            else:
                paragraphs.append(('text', clean_text, tag.lower()))
    
    # If no structured content found, just strip and return as one block
    if not paragraphs:
        full_text = strip_html(html_content)
        if full_text:
            paragraphs.append(('text', full_text, 'p'))
    
    return paragraphs


def generate_tos_pdf(
    tos_title: str,
    tos_content: str,
    store_name: str,
    order_number: Optional[str] = None,
    customer_name: Optional[str] = None,
    agreed_at: Optional[str] = None,
) -> bytes:
    """
    Generate a PDF of the Terms of Service.
    
    Args:
        tos_title: Title of the ToS document
        tos_content: HTML content of the ToS
        store_name: Name of the store/company
        order_number: Optional order number for reference
        customer_name: Optional customer name who agreed
        agreed_at: Optional timestamp when customer agreed
    
    Returns:
        PDF document as bytes
    """
    buffer = io.BytesIO()
    
    # Create document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=25*mm,
        rightMargin=25*mm,
        topMargin=25*mm,
        bottomMargin=25*mm
    )
    
    # Get styles
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=12,
        textColor=colors.HexColor('#1e293b')
    )
    
    h2_style = ParagraphStyle(
        'CustomH2',
        parent=styles['Heading2'],
        fontSize=14,
        spaceBefore=16,
        spaceAfter=8,
        textColor=colors.HexColor('#334155')
    )
    
    h3_style = ParagraphStyle(
        'CustomH3',
        parent=styles['Heading3'],
        fontSize=12,
        spaceBefore=12,
        spaceAfter=6,
        textColor=colors.HexColor('#475569')
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        spaceAfter=8,
        textColor=colors.HexColor('#475569')
    )
    
    meta_style = ParagraphStyle(
        'Meta',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#64748b')
    )
    
    # Build content
    story = []
    
    # Header with store name
    story.append(Paragraph(store_name, meta_style))
    story.append(Spacer(1, 8))
    
    # Title
    story.append(Paragraph(tos_title or "Terms & Conditions", title_style))
    
    # Metadata if provided
    if order_number or customer_name or agreed_at:
        story.append(Spacer(1, 8))
        meta_lines = []
        if order_number:
            meta_lines.append(f"Order Reference: {order_number}")
        if customer_name:
            meta_lines.append(f"Customer: {customer_name}")
        if agreed_at:
            try:
                dt = datetime.fromisoformat(agreed_at.replace('Z', '+00:00'))
                formatted_date = dt.strftime('%B %d, %Y at %H:%M UTC')
            except:
                formatted_date = agreed_at
            meta_lines.append(f"Agreed on: {formatted_date}")
        
        for line in meta_lines:
            story.append(Paragraph(line, meta_style))
        
        story.append(Spacer(1, 8))
        story.append(HRFlowable(
            width="100%",
            thickness=0.5,
            color=colors.HexColor('#e2e8f0'),
            spaceBefore=8,
            spaceAfter=16
        ))
    
    # Parse and add ToS content
    paragraphs = html_to_paragraphs(tos_content)
    
    for para_type, text, tag in paragraphs:
        if para_type == 'heading':
            if tag == 'h1':
                story.append(Paragraph(text, title_style))
            elif tag == 'h2':
                story.append(Paragraph(text, h2_style))
            else:
                story.append(Paragraph(text, h3_style))
        else:
            # Bullet for list items
            if tag == 'li':
                text = f"• {text}"
            story.append(Paragraph(text, body_style))
    
    # Footer
    story.append(Spacer(1, 24))
    story.append(HRFlowable(
        width="100%",
        thickness=0.5,
        color=colors.HexColor('#e2e8f0'),
        spaceBefore=16,
        spaceAfter=8
    ))
    
    generated_at = datetime.now(timezone.utc).strftime('%B %d, %Y')
    story.append(Paragraph(
        f"Document generated on {generated_at} • © {store_name}",
        meta_style
    ))
    
    # Build PDF
    doc.build(story)
    
    return buffer.getvalue()


async def generate_order_tos_pdf(
    tenant_id: str,
    order_id: str,
    db
) -> Optional[bytes]:
    """
    Generate ToS PDF for a specific order.
    
    Fetches the order, customer, and active ToS from the database,
    then generates a PDF.
    
    Returns None if no ToS is found or order doesn't exist.
    """
    from services.settings_service import SettingsService
    
    # Get order
    order = await db.orders.find_one(
        {"id": order_id, "tenant_id": tenant_id},
        {"_id": 0}
    )
    if not order:
        return None
    
    # Get customer and user
    customer = await db.customers.find_one(
        {"id": order.get("customer_id")},
        {"_id": 0}
    )
    user = None
    if customer and customer.get("user_id"):
        user = await db.users.find_one(
            {"id": customer["user_id"]},
            {"_id": 0, "full_name": 1, "email": 1}
        )
    
    # Get active ToS for tenant
    tos = await db.terms_and_conditions.find_one(
        {"tenant_id": tenant_id, "status": "active"},
        {"_id": 0}
    )
    if not tos:
        return None
    
    # Get store name (global setting or from website_settings for tenant)
    ws = await db.website_settings.find_one({"tenant_id": tenant_id}, {"_id": 0, "store_name": 1})
    store_name = ws.get("store_name") if ws else None
    if not store_name:
        from services.settings_service import SettingsService
        store_name = await SettingsService.get("store_name", "Store")
    
    # Generate PDF
    return generate_tos_pdf(
        tos_title=tos.get("title", "Terms & Conditions"),
        tos_content=tos.get("content", ""),
        store_name=store_name,
        order_number=order.get("order_number"),
        customer_name=user.get("full_name") if user else None,
        agreed_at=order.get("created_at")
    )
