#!/usr/bin/env python3
"""生成 assets/app.ico（品牌色 #1b5e4b + 勾形）。"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "app.ico"


def main() -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        import subprocess
        import sys

        subprocess.check_call([sys.executable, "-m", "pip", "install", "pillow", "-q"])
        from PIL import Image, ImageDraw, ImageFont

    brand = (27, 94, 75)  # #1b5e4b
    paper = (255, 254, 251)
    accent = (180, 83, 9)

    sizes = [16, 24, 32, 48, 64, 128, 256]
    images: list[Image.Image] = []

    for size in sizes:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        pad = max(1, size // 10)
        draw.rounded_rectangle(
            [pad, pad, size - pad - 1, size - pad - 1],
            radius=max(2, size // 5),
            fill=brand,
        )
        # check mark
        w = size - 2 * pad
        pts = [
            (pad + int(w * 0.22), pad + int(w * 0.52)),
            (pad + int(w * 0.42), pad + int(w * 0.72)),
            (pad + int(w * 0.78), pad + int(w * 0.28)),
        ]
        stroke = max(2, size // 8)
        draw.line(pts[:2], fill=paper, width=stroke, joint="curve")
        draw.line(pts[1:], fill=paper, width=stroke, joint="curve")
        # small accent dot (book / highlight)
        r = max(2, size // 10)
        draw.ellipse(
            [size - pad - r * 2, pad + 2, size - pad, pad + 2 + r * 2],
            fill=accent,
        )
        images.append(img)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(
        OUT,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[1:],
    )
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
