"""Generates packaging/icon.icns: a sync-cycle glyph (two curved arrows) on a
rounded-square background, matching macOS app-icon conventions. The app's job
is syncing repos to GitHub; the leak-gate is a safety step inside that, not
the headline feature, so the icon leads with "sync" rather than "security".
Run once (or whenever the design changes); the .icns is committed so building
doesn't require Pillow.
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 1024
OUT_DIR = Path(__file__).resolve().parent
ICONSET = OUT_DIR / "icon.iconset"

BG_TOP = (20, 60, 56)
BG_BOTTOM = (10, 110, 90)
ARROW = (235, 245, 240)


def rounded_square_gradient(size: int, radius: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    grad = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / (size - 1)
        r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t)
        grad.putpixel((0, y), (r, g, b))
    grad = grad.resize((size, size))

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    img.paste(grad, (0, 0), mask)
    return img


def _point_on_circle(cx, cy, r, angle_deg):
    a = math.radians(angle_deg)
    return cx + r * math.cos(a), cy + r * math.sin(a)


def draw_arrow_arc(draw, cx, cy, radius, start_deg, end_deg, width, color, head_size):
    """Thick arc from start_deg to end_deg (PIL angle convention, clockwise
    with y-down), with a triangular arrowhead at the end pointing along the
    direction of travel."""
    draw.arc(
        [cx - radius, cy - radius, cx + radius, cy + radius],
        start=start_deg,
        end=end_deg,
        fill=color,
        width=width,
    )

    tip = _point_on_circle(cx, cy, radius, end_deg)
    tangent = math.radians(end_deg + 90)  # direction of travel at the arc's end
    back = (tip[0] - head_size * math.cos(tangent), tip[1] - head_size * math.sin(tangent))
    perp = tangent + math.pi / 2
    left = (back[0] + head_size * 0.6 * math.cos(perp), back[1] + head_size * 0.6 * math.sin(perp))
    right = (back[0] - head_size * 0.6 * math.cos(perp), back[1] - head_size * 0.6 * math.sin(perp))
    forward_tip = (tip[0] + head_size * 0.35 * math.cos(tangent), tip[1] + head_size * 0.35 * math.sin(tangent))
    draw.polygon([forward_tip, left, right], fill=color)


def draw_sync_glyph(draw, cx, cy, radius, stroke_width, color, gap_deg=34, head_size=110):
    half_gap = gap_deg / 2
    draw_arrow_arc(draw, cx, cy, radius, half_gap, 180 - half_gap, stroke_width, color, head_size)
    draw_arrow_arc(draw, cx, cy, radius, 180 + half_gap, 360 - half_gap, stroke_width, color, head_size)


def build():
    img = rounded_square_gradient(SIZE, radius=180)
    draw = ImageDraw.Draw(img)

    draw_sync_glyph(
        draw,
        cx=SIZE // 2,
        cy=SIZE // 2,
        radius=300,
        stroke_width=92,
        color=ARROW,
        gap_deg=34,
        head_size=150,
    )

    ICONSET.mkdir(exist_ok=True)
    for s in (16, 32, 128, 256, 512):
        img.resize((s, s), Image.LANCZOS).save(ICONSET / f"icon_{s}x{s}.png")
        img.resize((s * 2, s * 2), Image.LANCZOS).save(ICONSET / f"icon_{s}x{s}@2x.png")

    print(f"Wrote iconset to {ICONSET}")


if __name__ == "__main__":
    build()
