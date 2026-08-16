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
    heading_font = _font(17 if compact else 19, bold=True)
    body_font = _font(15 if compact else 17)
    footer_font = _font(13, bold=True)
    wrap_width = 82 if compact else 72
    heading_height = 38 if compact else 43
    line_height = 20 if compact else 24
    card_padding = 10 if compact else 14
    card_gap = 7 if compact else 10

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
