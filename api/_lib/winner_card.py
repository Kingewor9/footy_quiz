import io
import os
import re
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
SIZE = 1080
INK, MUTED, GOLD = (255, 255, 255), (170, 178, 214), (255, 205, 86)


def _font(name: str, size: int):
    try:
        return ImageFont.truetype(os.path.join(FONT_DIR, name), size)
    except Exception:
        return ImageFont.load_default(size)


def clean_name(name: str) -> str:
    """The bundled font is Latin only; drop emoji and unsupported scripts rather than draw boxes."""
    return re.sub(r"\s+", " ", "".join(c for c in name if ord(c) < 0x2000)).strip()


def fmt_time(ms: int) -> str:
    s = max(0, ms // 1000)
    return f"{s // 60}m {s % 60:02d}s" if s >= 60 else f"{s}s"


def _fit(draw, text, font_name, start, max_w):
    size = start
    while size > 28:
        f = _font(font_name, size)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 4
    return _font(font_name, 28)


def _circle(img: Image.Image, d: int) -> Image.Image:
    img = img.convert("RGB")
    side = min(img.size)
    img = img.crop(((img.width - side) // 2, (img.height - side) // 2, (img.width + side) // 2, (img.height + side) // 2))
    img = img.resize((d, d), Image.LANCZOS)
    mask = Image.new("L", (d, d), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, d - 1, d - 1), fill=255)
    out = Image.new("RGBA", (d, d))
    out.paste(img, (0, 0), mask)
    return out


def _initials_avatar(name: str, d: int) -> Image.Image:
    im = Image.new("RGB", (d, d), (90, 108, 240))
    ini = "".join(w[0] for w in name.split()[:2]).upper() or "?"
    dr = ImageDraw.Draw(im)
    f = _font("Poppins-Bold.ttf", d // 2)
    w = dr.textlength(ini, font=f)
    dr.text(((d - w) / 2, d * 0.16), ini, font=f, fill=INK)
    return _circle(im, d)


def build_card(name: str, points: int, time_ms: int, day_label: str, photo: Optional[bytes], footer: str = "") -> bytes:
    name = clean_name(name) or "Champion"
    img = Image.new("RGB", (SIZE, SIZE))
    px = ImageDraw.Draw(img)
    top, bottom = (22, 26, 58), (70, 80, 190)
    for y in range(SIZE):  # vertical gradient
        t = y / SIZE
        px.line([(0, y), (SIZE, y)], fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    # pitch markings: centre circle + halfway line, kept faint
    lines = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lines)
    ld.line([(0, SIZE * 0.62), (SIZE, SIZE * 0.62)], fill=(255, 255, 255, 28), width=6)
    ld.ellipse((SIZE / 2 - 260, SIZE * 0.62 - 260, SIZE / 2 + 260, SIZE * 0.62 + 260), outline=(255, 255, 255, 28), width=6)
    img = Image.alpha_composite(img.convert("RGBA"), lines)
    d = ImageDraw.Draw(img)

    d.text((SIZE / 2, 110), "DAILY QUIZ CHAMPION", font=_font("Poppins-Bold.ttf", 54), fill=GOLD, anchor="mm")
    d.text((SIZE / 2, 172), day_label, font=_font("Poppins-Medium.ttf", 34), fill=MUTED, anchor="mm")

    dia, cx, cy = 400, SIZE // 2, 450
    d.ellipse((cx - dia / 2 - 14, cy - dia / 2 - 14, cx + dia / 2 + 14, cy + dia / 2 + 14), fill=GOLD)
    avatar = None
    if photo:
        try:
            avatar = _circle(Image.open(io.BytesIO(photo)), dia)
        except Exception:
            avatar = None
    avatar = avatar or _initials_avatar(name, dia)
    img.paste(avatar, (cx - dia // 2, cy - dia // 2), avatar)
    d = ImageDraw.Draw(img)

    d.text((SIZE / 2, 720), name, font=_fit(d, name, "Poppins-Bold.ttf", 84, SIZE - 160), fill=INK, anchor="mm")
    d.text((SIZE / 2, 818), f"{points} points  |  {fmt_time(time_ms)}", font=_font("Poppins-Medium.ttf", 46), fill=MUTED, anchor="mm")
    if footer:
        d.text((SIZE / 2, 990), footer, font=_font("Poppins-Medium.ttf", 34), fill=MUTED, anchor="mm")

    out = io.BytesIO()
    img.convert("RGB").save(out, "PNG", optimize=True)
    return out.getvalue()
