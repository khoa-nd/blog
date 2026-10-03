"""Render the social share image for blogs/ai-engineering-atlas.html.

Run:  uv run --with pillow tools/og-atlas.py

Writes blogs/ai-engineering-atlas-og.png (1200x630, the size Facebook,
LinkedIn, X and Slack all expect). The graph uses the same geometry and
palette as highlightArt() in js/home.js, so the share card and the home
page thumbnail look like the same picture.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "blogs" / "ai-engineering-atlas-og.png"

S = 2  # supersample, then downscale for smooth curves and text
W, H = 1200, 630

# Palette — matches the Atlas page and .hl-* rules in css/style.css
INK = (11, 18, 32)
PANEL = (22, 33, 58)
FG = (232, 237, 247)
FG2 = (154, 169, 196)
FG3 = (101, 116, 143)
LAYER = [(242, 169, 59), (226, 114, 91), (184, 111, 168), (139, 127, 212)]  # amber, orange-red, magenta, purple

# Graph geometry — identical to highlightArt() (viewBox 240 x 156)
L = [[60, 120, 180], [36, 92, 148, 204], [60, 120, 180], [90, 150]]
Y = [14, 52, 90, 128]
E = [[0,0,0],[0,0,1],[0,1,1],[0,1,2],[0,2,2],[0,2,3],[1,0,0],[1,1,0],[1,1,1],[1,2,1],[1,2,2],[1,3,2],[2,0,0],[2,1,0],[2,1,1],[2,2,1]]
HOT = {(0, 1, 1), (1, 1, 1), (2, 1, 1)}
ON = {(0, 1), (1, 1), (2, 1), (3, 1)}


def font(name, size, index=0):
    for path in (f"/System/Library/Fonts/{name}", f"/System/Library/Fonts/Supplemental/{name}"):
        if Path(path).exists():
            return ImageFont.truetype(path, size * S, index=index)
    return ImageFont.load_default(size * S)


def mix(c, bg, a):
    return tuple(round(c[i] * a + bg[i] * (1 - a)) for i in range(3))


def bezier(p0, p1, p2, p3, n=40):
    pts = []
    for k in range(n + 1):
        t = k / n
        u = 1 - t
        pts.append((
            u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0],
            u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1],
        ))
    return pts


img = Image.new("RGB", (W * S, H * S), INK)
d = ImageDraw.Draw(img)

# Soft panel behind the graph
gx, gy, sc = 596, 128, 2.2          # graph origin and scale (240x156 -> 528x343)
pad = 34
d.rounded_rectangle([(gx - pad) * S, (gy - pad) * S, (gx + 240 * sc + pad) * S, (gy + 156 * sc + pad) * S],
                    radius=18 * S, fill=mix(PANEL, INK, .55))

P = lambda x, y: ((gx + x * sc) * S, (gy + y * sc) * S)

for e in E:
    r, a, b = e
    x1, x2 = L[r][a], L[r + 1][b]
    y1, y2 = Y[r] + 14, Y[r + 1]
    ym = (y1 + y2) / 2
    hot = tuple(e) in HOT
    color = LAYER[r] if hot else mix(FG2, INK, .30)
    d.line([P(*p) for p in bezier((x1, y1), (x1, ym), (x2, ym), (x2, y2))],
           fill=color, width=round((2.4 if hot else 1.5) * sc * S), joint="curve")

for r, row in enumerate(L):
    for c, x in enumerate(row):
        on = (r, c) in ON
        x0, y0 = P(x - 20, Y[r])
        x1, y1 = P(x + 20, Y[r] + 14)
        d.rounded_rectangle([x0, y0, x1, y1], radius=3 * sc * S,
                            fill=LAYER[r] if on else mix(LAYER[r], PANEL, .16),
                            outline=LAYER[r], width=round(1.3 * sc * S))

# Text column
X = 72
kicker = font("Avenir Next.ttc", 22, index=5)      # Demi Bold
d.text((X * S, 120 * S), "INTERACTIVE MAP", font=kicker, fill=LAYER[0])

title_font = font("SFNS.ttf", 64)
try:
    title_font.set_variation_by_name("Bold")
except Exception:
    pass
d.text((X * S, 162 * S), "The AI", font=title_font, fill=FG)
d.text((X * S, 236 * S), "Engineering", font=title_font, fill=FG)
d.text((X * S, 310 * S), "Atlas", font=title_font, fill=LAYER[1])

body = font("SFNS.ttf", 26)
for k, line in enumerate(["78 core concepts, 18 learning", "layers, one dependency graph."]):
    d.text((X * S, (414 + k * 36) * S), line, font=body, fill=FG2)

foot = font("SFNS.ttf", 22)
d.text((X * S, 540 * S), "nguyendangkhoa.info", font=foot, fill=FG3)

img = img.resize((W, H), Image.LANCZOS)
img.save(OUT, optimize=True)
print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")
