"""Deterministic 2x2 photo-grid cover image generator: bold white title text
with a black outline directly over the photos, plus an optional white
"pill" location badge underneath - the common XHS cover style.

Pure Pillow image compositing - no AI involved, so it's fast and free to
re-run. The pin icon is hand-drawn (not an emoji glyph) because color emoji
rendering in Pillow's text drawing is unreliable across fonts/platforms.
"""
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

CANVAS_SIZE = (1080, 1440)  # XHS-recommended 3:4 cover ratio

FONT_CANDIDATES = [
    (r"C:\Windows\Fonts\msyhbd.ttc", 0),  # Microsoft YaHei Bold - best CJK coverage
    (r"C:\Windows\Fonts\simhei.ttf", 0),
    (r"C:\Windows\Fonts\arialbd.ttf", 0),
]


def _load_font(size):
    for path, index in FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size, index=index)
            except OSError:
                continue
    return ImageFont.load_default()


def _fit_cell(img, cell_w, cell_h):
    return ImageOps.fit(img, (cell_w, cell_h), method=Image.LANCZOS, centering=(0.5, 0.5))


def _wrap_text(draw, text, font, max_width):
    lines = []
    current = ""
    for ch in text:
        trial = current + ch
        if not current or draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = ch
    if current:
        lines.append(current)
    return lines


def _line_height(draw, line, font):
    bbox = draw.textbbox((0, 0), line, font=font)
    return bbox[3] - bbox[1]


def _draw_pin_icon(draw, center_x, center_y, size, color):
    """A simple map-pin teardrop, hand-drawn so it renders consistently
    regardless of emoji font support."""
    r = size / 2
    draw.ellipse(
        [center_x - r, center_y - r, center_x + r, center_y + r * 0.85], fill=color
    )
    draw.polygon(
        [
            (center_x - r * 0.55, center_y + r * 0.35),
            (center_x + r * 0.55, center_y + r * 0.35),
            (center_x, center_y + r * 1.6),
        ],
        fill=color,
    )
    hole_r = r * 0.32
    draw.ellipse(
        [center_x - hole_r, center_y - hole_r * 1.1, center_x + hole_r, center_y + hole_r * 0.9],
        fill="white",
    )


def create_cover(image_bytes_list, title, subtitle=None, canvas_size=CANVAS_SIZE):
    """image_bytes_list: list of up to 4 raw image bytes (fewer leaves blank cells).
    subtitle: optional short location/tag text shown in a pill badge below the title.

    Returns PNG bytes of the composed cover.
    """
    width, height = canvas_size
    cell_w, cell_h = width // 2, height // 2

    canvas = Image.new("RGB", canvas_size, "white")
    positions = [(0, 0), (cell_w, 0), (0, cell_h), (cell_w, cell_h)]

    for pos, raw in zip(positions, image_bytes_list[:4]):
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        canvas.paste(_fit_cell(img, cell_w, cell_h), pos)

    draw = ImageDraw.Draw(canvas)

    # --- title: bold white text with a black outline, centered around the
    # vertical middle of the canvas, no background band.
    font_size = int(width * 0.115)
    max_text_width = int(width * 0.9)
    font = _load_font(font_size)
    lines = _wrap_text(draw, title, font, max_text_width)
    while len(lines) > 2 and font_size > 28:
        font_size -= 4
        font = _load_font(font_size)
        lines = _wrap_text(draw, title, font, max_text_width)

    stroke_width = max(2, font_size // 11)
    line_heights = [_line_height(draw, line, font) for line in lines]
    line_gap = int(font_size * 0.15)
    total_text_h = sum(line_heights) + line_gap * (len(lines) - 1)

    y = int(height * 0.46) - total_text_h // 2
    for line, lh in zip(lines, line_heights):
        line_w = draw.textlength(line, font=font)
        x = (width - line_w) / 2
        draw.text(
            (x, y), line, font=font, fill="white",
            stroke_width=stroke_width, stroke_fill="black",
        )
        y += lh + line_gap

    # --- optional location pill, centered just below the title.
    if subtitle:
        pill_font_size = int(font_size * 0.42)
        pill_font = _load_font(pill_font_size)
        pin_size = pill_font_size * 0.9
        pad_x, pad_y, gap = int(pill_font_size * 0.7), int(pill_font_size * 0.45), int(pill_font_size * 0.35)

        text_w = draw.textlength(subtitle, font=pill_font)
        text_h = _line_height(draw, subtitle, pill_font)

        pill_w = pad_x * 2 + pin_size + gap + text_w
        pill_h = max(pin_size, text_h) + pad_y * 2
        pill_x = (width - pill_w) / 2
        pill_y = y + int(font_size * 0.25)

        draw.rounded_rectangle(
            [pill_x, pill_y, pill_x + pill_w, pill_y + pill_h],
            radius=pill_h / 2, fill="white",
        )
        _draw_pin_icon(
            draw, pill_x + pad_x + pin_size / 2, pill_y + pill_h / 2 - pin_size * 0.15,
            pin_size, "#FF3B30",
        )
        draw.text(
            (pill_x + pad_x + pin_size + gap, pill_y + (pill_h - text_h) / 2 - text_h * 0.1),
            subtitle, font=pill_font, fill="black",
        )

    out = io.BytesIO()
    canvas.save(out, format="PNG")
    return out.getvalue()
