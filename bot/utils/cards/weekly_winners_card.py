from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date

from PIL import Image, ImageDraw, ImageFont


@dataclass(frozen=True, slots=True)
class CardWinner:
    rank: int  # 1..3
    name: str
    points: int


def _try_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """
    Tries common fonts. Falls back to PIL default if truetype not available.
    Works on Windows/Linux without bundling fonts.
    """
    candidates = [
        # Windows common
        "C:\\Windows\\Fonts\\segoeui.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
        # Linux common
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            pass
    return ImageFont.load_default()


def _text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], s: str, font, fill=(20, 20, 20)) -> None:
    draw.text(xy, s, font=font, fill=fill)


def render_weekly_winners_card(
    *,
    week_start: date,
    week_end: date,
    winners: list[CardWinner],
    title: str = "Weekly Winners",
) -> bytes:
    """
    Returns PNG bytes. Simple clean layout, no emoji dependency.
    """

    W, H = 1200, 675  # 16:9
    pad = 48

    img = Image.new("RGB", (W, H), (248, 249, 251))
    draw = ImageDraw.Draw(img)

    # Fonts
    font_title = _try_font(52)
    font_sub = _try_font(28)
    font_row = _try_font(34)
    font_small = _try_font(22)

    # Header card
    header_h = 170
    draw.rounded_rectangle(
        (pad, pad, W - pad, pad + header_h),
        radius=28,
        fill=(255, 255, 255),
        outline=(235, 236, 240),
        width=2,
    )

    _text(draw, (pad + 32, pad + 28), title, font_title, fill=(15, 23, 42))
    _text(
        draw,
        (pad + 32, pad + 100),
        f"Week (UTC): {week_start.isoformat()} → {week_end.isoformat()}",
        font_sub,
        fill=(55, 65, 81),
    )

    # Body container
    body_top = pad + header_h + 26
    draw.rounded_rectangle(
        (pad, body_top, W - pad, H - pad),
        radius=28,
        fill=(255, 255, 255),
        outline=(235, 236, 240),
        width=2,
    )

    # Column headers
    _text(draw, (pad + 36, body_top + 28), "Rank", font_small, fill=(107, 114, 128))
    _text(draw, (pad + 190, body_top + 28), "User", font_small, fill=(107, 114, 128))
    _text(draw, (W - pad - 220, body_top + 28), "Points", font_small, fill=(107, 114, 128))

    # Rows
    row_y = body_top + 72
    row_h = 120

    rank_labels = {1: "🥇 1st", 2: "🥈 2nd", 3: "🥉 3rd"}
    # (emoji may not render on some fonts; still ok – it will just show squares sometimes)

    for i in range(3):
        y1 = row_y + i * row_h
        y2 = y1 + row_h - 12

        # alternating subtle background
        if i % 2 == 0:
            draw.rounded_rectangle(
                (pad + 20, y1, W - pad - 20, y2),
                radius=22,
                fill=(249, 250, 251),
            )

        if i < len(winners):
            w = winners[i]
            rank_txt = rank_labels.get(w.rank, f"{w.rank}")
            _text(draw, (pad + 40, y1 + 34), rank_txt, font_row, fill=(15, 23, 42))
            _text(draw, (pad + 190, y1 + 34), w.name, font_row, fill=(15, 23, 42))
            _text(draw, (W - pad - 220, y1 + 34), str(w.points), font_row, fill=(15, 23, 42))
        else:
            _text(draw, (pad + 40, y1 + 34), "-", font_row, fill=(156, 163, 175))
            _text(draw, (pad + 190, y1 + 34), "—", font_row, fill=(156, 163, 175))
            _text(draw, (W - pad - 220, y1 + 34), "0", font_row, fill=(156, 163, 175))

    # Footer note
    _text(
        draw,
        (pad + 36, H - pad - 34),
        "Generated automatically • TG Engagement Bot",
        font_small,
        fill=(156, 163, 175),
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()