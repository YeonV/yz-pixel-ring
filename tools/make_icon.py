#!/usr/bin/env python
"""Rasterize ui/public/logo.svg into a clean, padded, square icon set.

The brand SVG is landscape with margins; the shipped .ico/.png were cropped tight.
This renders the SVG fresh, keys the art onto transparency as a white silhouette
(ideal for the dark UI and OS taskbars), pads it square, and writes:

  assets/yz-pixel-ring.ico   -> PyInstaller exe icon (multi-size)
  ui/public/favicon.ico      -> clean favicon fallback (overwrites the cropped one)

Run with throwaway deps (keeps the runtime venv clean):

  uv run --with svglib --with reportlab --with pillow python tools/make_icon.py
"""
from io import BytesIO
from pathlib import Path

from PIL import Image
from reportlab.graphics import renderPM
from svglib.svglib import svg2rlg

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "ui" / "public" / "logo.svg"
SUPERSAMPLE = 3          # render scale for crisp downsampling
MARGIN = 0.12            # fraction of the square left as breathing room
ICO_SIZES = [256, 128, 64, 48, 32, 24, 16]


def render_rgba() -> Image.Image:
    d = svg2rlg(str(SRC))
    d.scale(SUPERSAMPLE, SUPERSAMPLE)
    d.width *= SUPERSAMPLE
    d.height *= SUPERSAMPLE
    # Render on black: white art -> bright, transparent gaps -> dark. We then turn
    # luminance into the alpha channel and force the visible colour to white.
    png = renderPM.drawToString(d, fmt="PNG", bg=0x000000)
    flat = Image.open(BytesIO(png)).convert("L")          # luminance = coverage
    out = Image.new("RGBA", flat.size, (255, 255, 255, 0))
    out.putalpha(flat)                                    # white silhouette, AA edges
    return out


def square_with_margin(im: Image.Image) -> Image.Image:
    bbox = im.getbbox()
    if bbox:
        im = im.crop(bbox)
    w, h = im.size
    side = int(round(max(w, h) / (1 - 2 * MARGIN)))
    canvas = Image.new("RGBA", (side, side), (255, 255, 255, 0))
    canvas.paste(im, ((side - w) // 2, (side - h) // 2), im)
    return canvas


def main() -> None:
    art = square_with_margin(render_rgba())
    (ROOT / "assets").mkdir(exist_ok=True)
    targets = [ROOT / "assets" / "yz-pixel-ring.ico", ROOT / "ui" / "public" / "favicon.ico"]
    for t in targets:
        art.save(t, format="ICO", sizes=[(s, s) for s in ICO_SIZES])
        print(f"wrote {t}  ({art.size[0]}px square, sizes {ICO_SIZES})")


if __name__ == "__main__":
    main()
