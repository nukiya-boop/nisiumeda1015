"""西梅田 禅園 Instagram リール用 PR 動画（1080x1920 / 30秒 / 30fps）を生成する。

使い方:
    python3 video/make_reel.py               # video/zenen_reel.mp4 を出力
    python3 video/make_reel.py --preview DIR # 指定秒のフレームを PNG で書き出すだけ

必要: Python3 + Pillow + numpy, ffmpeg, Noto Serif CJK フォント
"""
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG_DIR = os.path.join(ROOT, "images")
OUT = os.path.join(ROOT, "video", "zenen_reel.mp4")

W, H = 1080, 1920
FPS = 30
DURATION = 30.0
SRC_H = 2304  # 事前縮小後の高さ（ズーム余白込み）

FONT_PATH = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"
FONT_BOLD = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"

IVORY = (244, 238, 226)
GOLD = (205, 176, 122)


# ---------------------------------------------------------------- easing
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_io(t):  # easeInOutCubic
    t = clamp(t)
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_out(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_sine(t):
    t = clamp(t)
    return -(math.cos(math.pi * t) - 1) / 2


def lerp(a, b, t):
    return a + (b - a) * t


# ---------------------------------------------------------------- shots
# file, start, end, (cx0, cy0, zoom0) -> (cx1, cy1, zoom1)
SHOTS = [
    ("DSC00686.jpg", 0.0, 4.6, (0.655, 0.56, 1.04), (0.675, 0.54, 1.16)),   # お出迎え
    ("DSC00732.jpg", 3.9, 8.6, (0.36, 0.52, 1.08), (0.62, 0.52, 1.08)),     # ビーズカーテン越しのフロア
    ("DSC00738.jpg", 7.9, 12.4, (0.60, 0.48, 1.16), (0.54, 0.50, 1.02)),    # カウンター
    ("DSC00741.jpg", 11.7, 16.2, (0.50, 0.55, 1.00), (0.55, 0.55, 1.12)),   # テーブル席
    ("DSC00734.jpg", 15.5, 20.4, (0.44, 0.55, 1.04), (0.64, 0.52, 1.10)),   # 個室（麻の葉）
    ("DSC00736.jpg", 19.7, 24.4, (0.30, 0.46, 1.14), (0.36, 0.50, 1.00)),   # 個室（書）
    ("DSC00676.jpg", 23.7, 30.0, (0.40, 0.50, 1.10), (0.46, 0.50, 1.00)),   # ご案内 → エンドカード
]
TRANSITIONS = ["fusuma", "blur", "whip", "goldwipe", "zoom", "leak"]


def grade(img):
    """暗めの写真をスマホ向けに少し持ち上げ、温かみを足す。"""
    a = np.asarray(img).astype(np.float32) / 255.0
    a = a ** 0.86  # シャドウを持ち上げ
    a[..., 0] *= 1.04
    a[..., 2] *= 0.95
    return Image.fromarray(np.clip(a * 255, 0, 255).astype(np.uint8))


def load_sources():
    srcs = []
    for f, *_ in SHOTS:
        im = Image.open(os.path.join(IMG_DIR, f)).convert("RGB")
        w = round(im.width * SRC_H / im.height)
        im = im.resize((w, SRC_H), Image.LANCZOS)
        srcs.append(grade(im))
    return srcs


SRCS = None


def render_shot(i, T, extra_zoom=1.0):
    f, s, e, k0, k1 = SHOTS[i]
    p = ease_sine((T - s) / (e - s))
    cx, cy, z = (lerp(k0[j], k1[j], p) for j in range(3))
    z *= extra_zoom
    src = SRCS[i]
    sw, sh = src.size
    ch = sh / z
    cw = ch * W / H
    x0 = clamp(cx * sw - cw / 2, 0, sw - cw)
    y0 = clamp(cy * sh - ch / 2, 0, sh - ch)
    return src.transform((W, H), Image.EXTENT, (x0, y0, x0 + cw, y0 + ch), Image.BILINEAR)


# ---------------------------------------------------------------- transitions
YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)
DIAG = (XX * 0.55 + YY * 0.835)  # 斜め方向の距離場
DIAG = (DIAG - DIAG.min()) / (DIAG.max() - DIAG.min())
RADIAL = np.sqrt(((XX - W * 0.75) / W) ** 2 + ((YY - H * 0.3) / H) ** 2)


def soft_blur(img, r):
    if r < 0.5:
        return img
    small = img.resize((W // 2, H // 2), Image.BILINEAR).filter(ImageFilter.GaussianBlur(r / 2))
    return small.resize((W, H), Image.BILINEAR)


def tr_fusuma(i, T, t):
    """襖が左右に開くように前の画像が割れ、次の画像が現れる。"""
    e = ease_io(t)
    B = render_shot(i + 1, T, extra_zoom=lerp(1.10, 1.0, e))
    A = render_shot(i, T)
    out = Image.eval(B, lambda v: int(v * (0.55 + 0.45 * e)))
    off = int(e * (W // 2 + 40))
    left = A.crop((0, 0, W // 2, H))
    right = A.crop((W // 2, 0, W, H))
    out.paste(left, (-off, 0))
    out.paste(right, (W // 2 + off, 0))
    # 襖の縁の金の細線
    d = ImageDraw.Draw(out)
    if 0 < e < 1:
        for x in (W // 2 - off - 1, W // 2 + off):
            d.line([(x, 0), (x, H)], fill=GOLD, width=3)
    return out


def tr_blur(i, T, t):
    e = ease_io(t)
    r = math.sin(math.pi * t) * 28
    A = soft_blur(render_shot(i, T), r)
    B = soft_blur(render_shot(i + 1, T), r)
    return Image.blend(A, B, e)


def tr_whip(i, T, t):
    """横方向のウィップパン（モーションブラー付き）。"""
    e = ease_io(t)
    A = render_shot(i, T)
    B = render_shot(i + 1, T)
    off = int(e * W)
    out = Image.new("RGB", (W, H))
    out.paste(A, (-off, 0))
    out.paste(B, (W - off, 0))
    k = math.sin(math.pi * t)
    if k > 0.05:
        nw = max(8, int(W / (1 + k * 40)))
        out = out.resize((nw, H), Image.BOX).resize((W, H), Image.BILINEAR)
    return out


def tr_goldwipe(i, T, t):
    """金の光の線が斜めに走り、画面を塗り替える。"""
    e = ease_io(t)
    A = np.asarray(render_shot(i, T)).astype(np.float32)
    B = np.asarray(render_shot(i + 1, T)).astype(np.float32)
    soft = 0.05
    pos = lerp(-soft, 1 + soft, e)
    m = np.clip((pos - DIAG) / soft + 0.5, 0, 1)[..., None]
    out = A * (1 - m) + B * m
    glow = np.exp(-((DIAG - pos) / 0.006) ** 2)[..., None]
    halo = np.exp(-((DIAG - pos) / 0.04) ** 2)[..., None]
    gold = np.array(GOLD, np.float32)
    out = out + glow * (gold * 1.2) + halo * gold * 0.35
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def tr_zoom(i, T, t):
    """奥へ吸い込まれるようなズームスルー。"""
    e = ease_io(t)
    A = render_shot(i, T, extra_zoom=1 + 0.45 * ease_out(t) * e + 0.1 * e)
    B = render_shot(i + 1, T, extra_zoom=lerp(1.3, 1.0, ease_out(t)))
    r = math.sin(math.pi * t) * 16
    return Image.blend(soft_blur(A, r), soft_blur(B, r), e)


def tr_leak(i, T, t):
    """暖色の光が差し込むライトリーク。"""
    e = ease_io(t)
    A = np.asarray(render_shot(i, T)).astype(np.float32)
    B = np.asarray(render_shot(i + 1, T)).astype(np.float32)
    out = A * (1 - e) + B * e
    k = math.sin(math.pi * t) ** 1.5
    leak = np.clip(1.1 - RADIAL * 1.6, 0, 1)[..., None] ** 2
    col = np.array([255, 178, 105], np.float32)
    out = out + leak * col * k * 0.9 + k * 18
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


TR_FUNCS = dict(fusuma=tr_fusuma, blur=tr_blur, whip=tr_whip, goldwipe=tr_goldwipe, zoom=tr_zoom, leak=tr_leak)


def base_frame(T):
    for i in range(len(SHOTS) - 1):
        nxt_s = SHOTS[i + 1][1]
        cur_e = SHOTS[i][2]
        if nxt_s <= T < cur_e:
            return TR_FUNCS[TRANSITIONS[i]](i, T, (T - nxt_s) / (cur_e - nxt_s))
    for i, (_, s, e, *_r) in enumerate(SHOTS):
        if s <= T < e or (i == len(SHOTS) - 1 and T >= s):
            return render_shot(i, T)
    return render_shot(0, T)


# ---------------------------------------------------------------- look (vignette / scrim / grain)
def build_mask():
    v = np.sqrt(((XX - W / 2) / (W * 0.75)) ** 2 + ((YY - H / 2) / (H * 0.75)) ** 2)
    vign = 1 - 0.35 * np.clip(v, 0, 1) ** 2.2
    bottom = 1 - 0.45 * np.clip((YY - H * 0.48) / (H * 0.52), 0, 1) ** 1.3
    top = 1 - 0.25 * np.clip((H * 0.18 - YY) / (H * 0.18), 0, 1)
    return (vign * bottom * top)[..., None].astype(np.float32)


MASK = build_mask()
rng = np.random.default_rng(7)
GRAIN = [rng.normal(0, 3.5, (H, W, 1)).astype(np.float32) for _ in range(6)]


def apply_look(img, n, darken=0.0):
    a = np.asarray(img).astype(np.float32) * MASK
    if darken > 0:
        a *= 1 - darken
    a += GRAIN[n % len(GRAIN)]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


# ---------------------------------------------------------------- typography
_font_cache = {}


def font(size, bold=False):
    key = (size, bold)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(FONT_BOLD if bold else FONT_PATH, size, index=0)
    return _font_cache[key]


PAD = 28


def make_sprite(ch, fnt, color, shadow=0.8):
    asc, desc = fnt.getmetrics()
    w = int(fnt.getlength(ch)) + 2 * PAD + 4
    h = asc + desc + 2 * PAD
    layer = Image.new("L", (w, h), 0)
    ImageDraw.Draw(layer).text((PAD, PAD), ch, font=fnt, fill=255)
    sh = layer.filter(ImageFilter.GaussianBlur(9)).point(lambda v: int(v * shadow))
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    img.putalpha(sh)
    fg = Image.new("RGBA", (w, h), color + (0,))
    fg.putalpha(layer)
    img = Image.alpha_composite(img, fg)
    return img, asc


_scrim_cache = {}


def scrim_sprite(cy, strength, h=560):
    key = (h, strength)
    if key not in _scrim_cache:
        yy, xx = np.mgrid[0:h, 0:W].astype(np.float32)
        r = np.sqrt(((xx - W / 2) / (W * 0.55)) ** 2 + ((yy - h / 2) / (h * 0.5)) ** 2)
        a = np.clip(1 - r, 0, 1) ** 1.6 * 255 * strength
        img = Image.new("RGBA", (W, h), (0, 0, 0, 0))
        img.putalpha(Image.fromarray(a.astype(np.uint8)))
        _scrim_cache[key] = img
    return _scrim_cache[key]


class Glyph:
    def __init__(self, ch, x, y, fnt, color, idx):
        self.sprite, asc = make_sprite(ch, fnt, color)
        # (x, y) = 文字の左上（ベースライン基準ではなく行の上端）
        self.x, self.y = x - PAD, y - PAD
        self.idx = idx


class TextBlock:
    """文字ごとに時間差でふわっと現れるテロップ。"""

    def __init__(self, t0, t1, stagger=0.045, fade=0.55, rise=16, vertical=False, scrim=None):
        self.t0, self.t1, self.stagger, self.fade, self.rise = t0, t1, stagger, fade, rise
        self.scrim = scrim  # (中心y, 濃さ) 文字の背後をふんわり暗くする
        self.vertical = vertical
        self.glyphs = []
        self.lines = []  # (y, x_center, width, appear_time)
        self.n = 0

    def hline(self, text, y, size, color=IVORY, tracking=0.08, bold=False, cx=W // 2):
        fnt = font(size, bold)
        adv = [fnt.getlength(c) + size * tracking for c in text]
        total = sum(adv) - size * tracking
        x = cx - total / 2
        for c, a in zip(text, adv):
            if c != " ":
                self.glyphs.append(Glyph(c, x, y, fnt, color, self.n))
            self.n += 1
            x += a
        return self

    def vline(self, text, x, y, size, color=IVORY, step=1.18):
        fnt = font(size)
        for k, c in enumerate(text):
            cw = fnt.getlength(c)
            self.glyphs.append(Glyph(c, x - cw / 2, y + k * size * step, fnt, color, self.n))
            self.n += 1
        return self

    def rule(self, y, width, delay=0.0, cx=W // 2):
        self.lines.append((y, cx, width, delay))
        return self

    def draw(self, canvas, T):
        if T < self.t0 - 0.01 or T > self.t1:
            return
        out_k = clamp((self.t1 - T) / 0.45)
        if self.scrim:
            k = ease_io((T - self.t0 + 0.2) / 0.8) * out_k
            sc = scrim_sprite(*self.scrim)
            if k < 0.999:
                sc = sc.copy()
                sc.putalpha(sc.getchannel("A").point(lambda v, k=k: int(v * k)))
            canvas.alpha_composite(sc, (0, int(self.scrim[0] - sc.height / 2)))
        for g in self.glyphs:
            ta = self.t0 + g.idx * self.stagger
            p = ease_out((T - ta) / self.fade)
            a = p * out_k
            if a <= 0.003:
                continue
            spr = g.sprite
            if a < 0.999:
                spr = spr.copy()
                spr.putalpha(spr.getchannel("A").point(lambda v, a=a: int(v * a)))
            dy = (1 - p) * self.rise
            if self.vertical:
                canvas.alpha_composite(spr, (int(g.x), int(g.y - dy)))
            else:
                canvas.alpha_composite(spr, (int(g.x), int(g.y + dy)))
        d = ImageDraw.Draw(canvas)
        for (y, cx, width, delay) in self.lines:
            p = ease_io((T - self.t0 - delay) / 0.9)
            if p <= 0:
                continue
            half = width * p / 2
            al = int(230 * out_k)
            d.line([(cx - half, y), (cx + half, y)], fill=GOLD + (al,), width=2)


def build_texts():
    B = []
    # 1. オープニング：縦書きのキャッチコピー（Webサイトのコピーより）
    B.append(TextBlock(0.6, 4.15, stagger=0.07, fade=0.8, rise=18, vertical=True)
             .vline("新たなご縁を結ぶ", 300, 430, 66)
             .vline("心尽くしのおもてなし", 196, 520, 66))
    B.append(TextBlock(1.6, 4.15, stagger=0.03, fade=0.7)
             .hline("NISHI-UMEDA  ZEN-EN", 300, 26, GOLD, tracking=0.32, cx=250))
    # 2. メッセージ
    B.append(TextBlock(4.55, 8.15, stagger=0.06, scrim=(1240, 0.62))
             .hline("おひとり様から", 1090, 74)
             .hline("ご宴会まで", 1200, 74)
             .rule(1340, 120, delay=0.5)
             .hline("全108席　多彩なお席をご用意", 1380, 38, tracking=0.1))
    # 3. カウンター
    B.append(TextBlock(8.55, 11.95, stagger=0.05, scrim=(1240, 0.62))
             .hline("COUNTER", 1110, 28, GOLD, tracking=0.45)
             .hline("カウンター席", 1170, 76, tracking=0.12)
             .rule(1310, 120, delay=0.4)
             .hline("ひとり飲みやデートに", 1350, 38, tracking=0.1))
    # 4. テーブル
    B.append(TextBlock(12.35, 15.75, stagger=0.05, scrim=(1240, 0.62))
             .hline("TABLE", 1110, 28, GOLD, tracking=0.45)
             .hline("テーブル席", 1170, 76, tracking=0.12)
             .rule(1310, 120, delay=0.4)
             .hline("ランチや、気軽なご会食に", 1350, 38, tracking=0.1))
    # 5. 個室
    B.append(TextBlock(16.15, 19.95, stagger=0.05, scrim=(1240, 0.62))
             .hline("PRIVATE ROOM", 1110, 28, GOLD, tracking=0.45)
             .hline("個室　全6室", 1170, 76, tracking=0.12)
             .rule(1310, 120, delay=0.4)
             .hline("ご接待・お顔合わせに", 1350, 38, tracking=0.1))
    # 6. 宴会
    B.append(TextBlock(20.35, 23.95, stagger=0.05, scrim=(1240, 0.62))
             .hline("BANQUET", 1110, 28, GOLD, tracking=0.45)
             .hline("最大20名様まで", 1170, 76, tracking=0.1)
             .rule(1310, 120, delay=0.4)
             .hline("ご法事・各種ご宴会にも", 1350, 38, tracking=0.1))
    # 7. エンドカード
    B.append(TextBlock(25.3, 30.5, stagger=0.06, fade=0.9)
             .hline("懐石・割烹", 640, 34, GOLD, tracking=0.5)
             .hline("西梅田 禅園", 720, 104, tracking=0.16)
             .rule(905, 200, delay=0.6))
    B.append(TextBlock(26.4, 30.5, stagger=0.025, fade=0.8)
             .hline("大阪・梅田　ハービスPLAZA B2F", 950, 34, tracking=0.08)
             .hline("西梅田駅より徒歩5分", 1010, 34, tracking=0.08))
    B.append(TextBlock(27.4, 30.5, stagger=0.03, fade=0.8)
             .hline("ご予約はプロフィールのリンクから", 1180, 36, GOLD, tracking=0.08))
    return B


TEXTS = None


def render_frame(n):
    T = n / FPS
    base = base_frame(T)
    darken = 0.0
    if T > 24.8:  # エンドカード：背景を暗く・ぼかす
        k = ease_io((T - 24.8) / 1.2)
        base = soft_blur(base, 14 * k)
        darken = 0.5 * k
    frame = apply_look(base, n, darken)
    if T < 0.7:  # 黒からフェードイン
        frame = Image.eval(frame, lambda v, k=ease_out(T / 0.7): int(v * k))
    canvas = frame.convert("RGBA")
    for tb in TEXTS:
        tb.draw(canvas, T)
    return canvas.convert("RGB")


def main():
    global SRCS, TEXTS
    SRCS = load_sources()
    TEXTS = build_texts()
    if len(sys.argv) > 2 and sys.argv[1] == "--preview":
        out_dir = sys.argv[2]
        os.makedirs(out_dir, exist_ok=True)
        for t in [float(x) for x in sys.argv[3:]] or [2, 4.25, 6, 8.25, 10, 12, 14, 16, 18, 20, 22, 24, 26.5, 29.5]:
            render_frame(int(t * FPS)).save(os.path.join(out_dir, f"f_{t:05.2f}.jpg"), quality=88)
        return
    total = int(DURATION * FPS)
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-shortest", "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-maxrate", "10M", "-bufsize", "20M", "-profile:v", "high",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart", OUT,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for n in range(total):
        proc.stdin.write(render_frame(n).tobytes())
        if n % 60 == 0:
            print(f"{n}/{total}", flush=True)
    proc.stdin.close()
    proc.wait()
    print("done:", OUT)


if __name__ == "__main__":
    main()
