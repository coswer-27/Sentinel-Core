"""
產生 Sentinel-Core 工具列圖示（與 popup 品牌 shield 一致）。
高解析度繪製後降採樣，輸出 icon16/48/128.png 至 browser_ext/。

執行： python browser_ext/icon_gen.py
依賴： Pillow
"""
from pathlib import Path

from PIL import Image, ImageDraw

OUT_DIR = Path(__file__).parent
MASTER = 512                      # 主畫布尺寸（高解析度）
SIZES = [16, 48, 128]

# 品牌青色漸層（上 → 下）與白色勾
GRAD_TOP = (103, 232, 249)       # #67e8f9
GRAD_BOTTOM = (8, 145, 178)      # #0891b2
CHECK_COLOR = (255, 255, 255, 255)


def _cubic(p0, p1, p2, p3, n):
    """取樣三次貝茲曲線（不含起點，含終點）。"""
    pts = []
    for i in range(1, n + 1):
        t = i / n
        mt = 1 - t
        x = mt**3 * p0[0] + 3 * mt**2 * t * p1[0] + 3 * mt * t**2 * p2[0] + t**3 * p3[0]
        y = mt**3 * p0[1] + 3 * mt**2 * t * p1[1] + 3 * mt * t**2 * p2[1] + t**3 * p3[1]
        pts.append((x, y))
    return pts


# 盾牌外框（24 單位座標，對應 content.js / popup 的 SVG path）
def _shield_points():
    pts = [(12, 3), (19, 6), (19, 11)]
    pts += _cubic((19, 11), (19, 15.4), (16, 18.2), (12, 19.7), 28)
    pts += _cubic((12, 19.7), (8, 18.2), (5, 15.4), (5, 11), 28)
    pts += [(5, 6)]
    return pts


CHECK = [(9, 12), (11, 14), (15, 10)]   # 勾的三個點


def _fit_transform(points, size, margin_ratio=0.07):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    w, h = maxx - minx, maxy - miny
    m = size * margin_ratio
    s = (size - 2 * m) / max(w, h)
    ox = (size - w * s) / 2 - minx * s
    oy = (size - h * s) / 2 - miny * s
    return lambda p: (p[0] * s + ox, p[1] * s + oy), s


def build_master():
    shield = _shield_points()
    tf, scale = _fit_transform(shield, MASTER)
    shield_px = [tf(p) for p in shield]

    # 1) 漸層
    grad = Image.new("RGB", (MASTER, MASTER), GRAD_BOTTOM)
    gd = grad.load()
    for y in range(MASTER):
        t = y / (MASTER - 1)
        r = round(GRAD_TOP[0] + (GRAD_BOTTOM[0] - GRAD_TOP[0]) * t)
        g = round(GRAD_TOP[1] + (GRAD_BOTTOM[1] - GRAD_TOP[1]) * t)
        b = round(GRAD_TOP[2] + (GRAD_BOTTOM[2] - GRAD_TOP[2]) * t)
        for x in range(MASTER):
            gd[x, y] = (r, g, b)

    # 2) 盾牌遮罩
    mask = Image.new("L", (MASTER, MASTER), 0)
    ImageDraw.Draw(mask).polygon(shield_px, fill=255)

    # 3) 漸層套盾牌形狀
    canvas = Image.new("RGBA", (MASTER, MASTER), (0, 0, 0, 0))
    canvas = Image.composite(grad.convert("RGBA"), canvas, mask)

    # 4) 白色勾（圓角線 + 端點圓帽）
    draw = ImageDraw.Draw(canvas)
    check_px = [tf(p) for p in CHECK]
    width = max(2, round(2.6 * scale))
    draw.line(check_px, fill=CHECK_COLOR, width=width, joint="curve")
    r = width / 2
    for cx, cy in (check_px[0], check_px[-1]):
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=CHECK_COLOR)

    return canvas


def main():
    master = build_master()
    for sz in SIZES:
        img = master.resize((sz, sz), Image.LANCZOS)
        img.save(OUT_DIR / f"icon{sz}.png")
        print(f"wrote icon{sz}.png")


if __name__ == "__main__":
    main()
