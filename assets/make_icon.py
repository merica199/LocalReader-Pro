"""
Generate the macOS app icon.

Run:  ../venv/bin/python make_icon.py
Produces icon.png (1024 master) next to this file, and an .icns in the app
bundle if one is passed as the first argument.

The mark is a page whose lower lines have turned into a waveform: text becoming
speech, which is the whole app. Kept to a light page shape and one accent colour
so it still reads at 16px in the Dock.
"""
import sys, os
from PIL import Image, ImageDraw

S = 1024
SS = 3                      # supersample factor, downscaled at the end
W = S * SS

NAVY_TOP    = (30, 44, 71)
NAVY_BOTTOM = (12, 17, 26)
PAGE        = (243, 241, 236)
PAGE_EDGE   = (214, 211, 203)
TEXT_LINE   = (150, 160, 172)
AMBER       = (216, 134, 44)
AMBER_LIGHT = (233, 163, 79)


def gradient(size, top, bottom):
    g = Image.new("RGB", (1, size), top)
    d = ImageDraw.Draw(g)
    for y in range(size):
        t = y / max(1, size - 1)
        d.point((0, y), fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return g.resize((size, size), Image.BICUBIC)


img = Image.new("RGBA", (W, W), (0, 0, 0, 0))

# --- rounded tile ---------------------------------------------------------
inset = int(W * 0.098)                 # macOS leaves visible padding around the tile
tile = (inset, inset, W - inset, W - inset)
radius = int((tile[2] - tile[0]) * 0.2237)   # macOS corner ratio

mask = Image.new("L", (W, W), 0)
ImageDraw.Draw(mask).rounded_rectangle(tile, radius=radius, fill=255)
img.paste(gradient(W, NAVY_TOP, NAVY_BOTTOM), (0, 0), mask)

d = ImageDraw.Draw(img)

# --- the mark -------------------------------------------------------------
# Deliberately only two elements: a pair of page rules and a waveform between
# them. Anything finer (body text, a page outline, a book spine) turns to mush
# at the 16px Dock size, so it is left out rather than drawn and lost.
cx, cy = W // 2, W // 2

rule_w = int(W * 0.42)
rule_h = int(W * 0.030)
for dy in (-int(W * 0.245), int(W * 0.245)):
    d.rounded_rectangle(
        (cx - rule_w // 2, cy + dy - rule_h // 2, cx + rule_w // 2, cy + dy + rule_h // 2),
        radius=rule_h // 2, fill=PAGE)

# shorter second rule, so the top pair reads as text rather than a border
short = int(rule_w * 0.55)
d.rounded_rectangle(
    (cx - rule_w // 2, cy - int(W * 0.245) + int(rule_h * 2.4) - rule_h // 2,
     cx - rule_w // 2 + short, cy - int(W * 0.245) + int(rule_h * 2.4) + rule_h // 2),
    radius=rule_h // 2, fill=(150, 160, 172))

bars = [0.42, 0.74, 1.0, 0.66, 0.34]
bw = int(W * 0.062)
gap = int(W * 0.040)
total = len(bars) * bw + (len(bars) - 1) * gap
bx = cx - total // 2
maxh = int(W * 0.30)
for i, f in enumerate(bars):
    h = max(bw, int(maxh * f))
    x0 = bx + i * (bw + gap)
    col = AMBER if i % 2 == 0 else AMBER_LIGHT
    d.rounded_rectangle((x0, cy - h // 2, x0 + bw, cy + h // 2), radius=bw // 2, fill=col)

icon = img.resize((S, S), Image.LANCZOS)
here = os.path.dirname(os.path.abspath(__file__))
icon.save(os.path.join(here, "icon.png"))
icon.resize((128, 128), Image.LANCZOS).save(os.path.join(here, "icon-preview-128.png"))
icon.resize((32, 32), Image.LANCZOS).resize((128, 128), Image.NEAREST).save(
    os.path.join(here, "icon-preview-32.png"))
print(f"wrote {here}/icon.png")
