from __future__ import annotations

from io import BytesIO
from pathlib import Path
import textwrap

from PIL import Image, ImageDraw, ImageFont


WIDTH = 768
HEIGHT = 1024


def _font(size: int, bold: bool = False):
    candidates = [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/dejavu/DejaVuSans.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def render_kneeboard_png(
    mission_name: str,
    subtitle: str,
    sections: list[tuple[str, list[str]]],
    footer: str = "DCS SIMULATION PLANNING ONLY",
) -> bytes:
    """Render a DCS-friendly 768x1024 kneeboard PNG."""
    image = Image.new("RGB", (WIDTH, HEIGHT), "#08131f")
    draw = ImageDraw.Draw(image)
    title_font = _font(34, bold=True)
    sub_font = _font(17)
    compact = len(sections) >= 7
    very_compact = len(sections) >= 8
    heading_font = _font(15 if very_compact else (17 if compact else 19), bold=True)
    body_font = _font(13 if very_compact else (15 if compact else 17))
    footer_font = _font(13, bold=True)
    wrap_width = 92 if very_compact else (82 if compact else 72)
    heading_height = 30 if very_compact else (38 if compact else 43)
    line_height = 17 if very_compact else (20 if compact else 24)
    card_padding = 7 if very_compact else (10 if compact else 14)
    card_gap = 4 if very_compact else (7 if compact else 10)

    draw.rectangle((0, 0, WIDTH, 12), fill="#d89b38")
    draw.text((30, 30), mission_name[:32] or "vTF-77 MISSION CARD", font=title_font, fill="#f4f7fb")
    draw.text((31, 77), subtitle[:82], font=sub_font, fill="#9fb3c8")

    y = 112
    for heading, lines in sections:
        wrapped: list[str] = []
        for line in lines:
            wrapped.extend(textwrap.wrap(str(line), width=wrap_width) or [""])
        card_height = heading_height + len(wrapped) * line_height + card_padding
        if y + card_height > HEIGHT - 48:
            wrapped = wrapped[: max(1, int((HEIGHT - 64 - y) / line_height))]
            card_height = heading_height + len(wrapped) * line_height + card_padding
        draw.rounded_rectangle((22, y, WIDTH - 22, y + card_height), radius=10, fill="#102336", outline="#29445d", width=2)
        draw.text((38, y + 10), heading.upper(), font=heading_font, fill="#e9b55b")
        line_y = y + heading_height + 1
        for line in wrapped:
            draw.text((40, line_y), line, font=body_font, fill="#edf3f8")
            line_y += line_height
        y += card_height + card_gap
        if y >= HEIGHT - 48:
            break

    draw.rectangle((0, HEIGHT - 36, WIDTH, HEIGHT), fill="#0d1b29")
    draw.text((24, HEIGHT - 28), footer, font=footer_font, fill="#9fb3c8")
    draw.text((WIDTH - 150, HEIGHT - 28), "F-14 EFB", font=footer_font, fill="#e9b55b")
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def render_mission_card_pdf(
    mission_name: str,
    subtitle: str,
    sections: list[tuple[str, list[str]]],
    footer: str = "DCS SIMULATION PLANNING ONLY",
) -> bytes:
    """Render the same operational hierarchy as a clean one-page PDF."""

    try:
        from reportlab.lib.colors import HexColor
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfbase.pdfmetrics import stringWidth
        from reportlab.pdfgen import canvas
    except ImportError as exc:  # pragma: no cover - deployment dependency guard
        raise RuntimeError("Mission-card PDF export requires reportlab.") from exc

    output = BytesIO()
    page_width, page_height = letter
    pdf = canvas.Canvas(output, pagesize=letter, pageCompression=1)
    pdf.setTitle((mission_name or "F-14 EFB Mission Card")[:120])
    navy = HexColor("#08131f")
    panel = HexColor("#102336")
    border = HexColor("#29445d")
    amber = HexColor("#d89b38")
    text_color = HexColor("#edf3f8")
    muted = HexColor("#9fb3c8")

    pdf.setFillColor(navy)
    pdf.rect(0, 0, page_width, page_height, fill=1, stroke=0)
    pdf.setFillColor(amber)
    pdf.rect(0, page_height - 8, page_width, 8, fill=1, stroke=0)
    pdf.setFillColor(text_color)
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(28, page_height - 39, (mission_name or "F-14 EFB MISSION CARD")[:42])
    pdf.setFillColor(muted)
    pdf.setFont("Helvetica", 8.5)
    pdf.drawString(29, page_height - 55, subtitle[:105])

    compact = len(sections) >= 7
    very_compact = len(sections) >= 9
    body_size = 8.0 if very_compact else (9.0 if compact else 10.0)
    line_height = 10.75 if very_compact else (12.5 if compact else 13.5)
    heading_height = 20.0 if very_compact else 23.0
    card_gap = 5.0 if very_compact else 7.0
    card_padding = 8.0 if very_compact else 10.0
    left = 22.0
    right = page_width - 22.0
    content_width = right - left
    wrap_width_points = content_width - 28.0

    def wrap_pdf_line(value: str) -> list[str]:
        words = str(value).split()
        wrapped: list[str] = []
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if stringWidth(candidate, "Helvetica", body_size) <= wrap_width_points:
                current = candidate
            else:
                if current:
                    wrapped.append(current)
                current = word
        if current or not wrapped:
            wrapped.append(current)
        return wrapped

    y = page_height - 72.0
    for heading, lines in sections:
        wrapped_lines: list[str] = []
        for line in lines:
            wrapped_lines.extend(wrap_pdf_line(str(line)))
        card_height = heading_height + len(wrapped_lines) * line_height + card_padding
        if y - card_height < 32.0:
            remaining = max(1, int((y - 45.0 - heading_height) / line_height))
            wrapped_lines = wrapped_lines[:remaining]
            card_height = heading_height + len(wrapped_lines) * line_height + card_padding
        y -= card_height
        pdf.setFillColor(panel)
        pdf.setStrokeColor(border)
        pdf.roundRect(left, y, content_width, card_height, 6, fill=1, stroke=1)
        pdf.setFillColor(amber)
        pdf.setFont("Helvetica-Bold", 9.5 if very_compact else (10.5 if compact else 11.0))
        pdf.drawString(left + 12, y + card_height - 15, heading.upper()[:78])
        pdf.setFillColor(text_color)
        pdf.setFont("Helvetica", body_size)
        line_y = y + card_height - heading_height - 4.0
        for line in wrapped_lines:
            pdf.drawString(left + 14, line_y, line)
            line_y -= line_height
        y -= card_gap
        if y < 32.0:
            break

    pdf.setFillColor(HexColor("#0d1b29"))
    pdf.rect(0, 0, page_width, 25, fill=1, stroke=0)
    pdf.setFillColor(muted)
    pdf.setFont("Helvetica-Bold", 7.5)
    pdf.drawString(20, 9, footer[:78])
    pdf.setFillColor(amber)
    pdf.drawRightString(page_width - 20, 9, "F-14 EFB")
    pdf.showPage()
    pdf.save()
    return output.getvalue()
