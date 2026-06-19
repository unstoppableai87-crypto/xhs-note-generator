"""Deterministic 2x2 photo-grid cover image generator with a centered title band.

Pure Pillow image compositing - no AI involved, so it's fast and free to re-run.
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


def create_cover(image_bytes_list, title, canvas_size=CANVAS_SIZE):
    """image_bytes_list: list of up to 4 raw image bytes (fewer leaves blank cells).

    Returns PNG bytes of the composed cover: 2x2 photo grid + centered title band.
    """
    width, height = canvas_size
    cell_w, cell_h = width // 2, height // 2

    canvas = Image.new("RGB", canvas_size, "white")
    positions = [(0, 0), (cell_w, 0), (0, cell_h), (cell_w, cell_h)]

    for pos, raw in zip(positions, image_bytes_list[:4]):
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        canvas.paste(_fit_cell(img, cell_w, cell_h), pos)

    overlay = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    band_h = int(height * 0.22)
    band_top = (height - band_h) // 2
    draw.rectangle([(0, band_top), (width, band_top + band_h)], fill=(255, 255, 255, 235))

    font_size = int(band_h * 0.42)
    max_text_width = int(width * 0.86)
    font = _load_font(font_size)
    lines = _wrap_text(draw, title, font, max_text_width)
    while len(lines) > 2 and font_size > 24:
        font_size -= 4
        font = _load_font(font_size)
        lines = _wrap_text(draw, title, font, max_text_width)

    line_metrics = [draw.textbbox((0, 0), line, font=font) for line in lines]
    line_heights = [bbox[3] - bbox[1] for bbox in line_metrics]
    total_text_h = sum(line_heights) + (len(lines) - 1) * 10
    y = band_top + (band_h - total_text_h) // 2
    for line, lh in zip(lines, line_heights):
        line_w = draw.textlength(line, font=font)
        x = (width - line_w) / 2
        draw.text((x, y), line, font=font, fill=(20, 20, 20, 255))
        y += lh + 10

    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")

    out = io.BytesIO()
    canvas.save(out, format="PNG")
    return out.getvalue()
