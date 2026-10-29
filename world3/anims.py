"""Signes graphiques, joues avant une carte.

Chaque dilemme, chaque limite qui detourne la carte, et chaque
evenement du monde a le sien. Symetries, ondes, vibrations, flashs.
preview_anims.py les montre tous.
"""

import math

import numpy as np

from .content import EVENTS, FORKS, ISS_CARD, SHOCKS
from .theme import (
    BG,
    CITY,
    DIM,
    GLASS,
    ICE,
    INK,
    LINE,
    MOSS,
    OCHRE,
    RUST,
    SAND,
    SEA,
    mix,
)

CW, CH = 48, 36
CX, CY = CW // 2, CH // 2
SCALE = 8
REVEAL_DUR = 1.65
REVEAL_HOLD = 0.32

SCENES = {}


def scene(kind, name):
    def deco(fn):
        SCENES[(kind, name)] = fn
        return fn

    return deco


def seg(t, a, b):
    if t <= a:
        return 0.0
    if t >= b:
        return 1.0
    return (t - a) / (b - a)


def lerp(a, b, u):
    return a + (b - a) * u


def settle(t, a=0.84):
    if t <= a:
        return 1.0
    u = (t - a) / (1.0 - a)
    if u >= 1.0:
        return 0.0
    return 1.0 - u * u


def shake(t, hz=8.0, amp=1.5, phase=0.0, until=0.84):
    return math.sin((t * hz + phase) * math.tau) * settle(t, until) * amp


def pulse(t, at, w=0.07):
    d = abs(t - at)
    if d >= w or w <= 0.0:
        return 0.0
    x = 1.0 - d / w
    return x * x


def pulses(t, ats, w=0.05):
    return max(pulse(t, a, w) for a in ats)


def strobe(t, hz=8.0, duty=0.42, until=0.88):
    if t >= until:
        return False
    return (t * hz) % 1.0 < duty


def fade(color, k):
    if k <= 0.0:
        return BG
    if k >= 1.0:
        return color
    return mix(BG, color, k)


class Board:
    def __init__(self, surf):
        self.s = surf

    def rect(self, x, y, w, h, color):
        w = int(round(w))
        h = int(round(h))
        if w <= 0 or h <= 0:
            return
        self.s.fill(color, (int(round(x)), int(round(y)), w, h))

    def px(self, x, y, color):
        self.rect(x, y, 1, 1, color)

    def disc(self, cx, cy, rad, color):
        rad = int(round(rad))
        if rad < 0:
            return
        cx = int(round(cx))
        cy = int(round(cy))
        rr = rad * rad
        for yy in range(-rad, rad + 1):
            for xx in range(-rad, rad + 1):
                if xx * xx + yy * yy <= rr:
                    self.px(cx + xx, cy + yy, color)

    def line(self, x0, y0, x1, y1, color, thick=1):
        x0, y0, x1, y1 = float(x0), float(y0), float(x1), float(y1)
        steps = int(max(abs(x1 - x0), abs(y1 - y0)))
        if steps <= 0:
            self.rect(x0, y0, thick, thick, color)
            return
        span = min(steps, 64)
        for i in range(span + 1):
            u = i / span
            self.rect(x0 + (x1 - x0) * u, y0 + (y1 - y0) * u, thick, thick, color)


def clear(b, x, y, w, h):
    b.rect(x, y, w, h, BG)


def poly(b, pts, color):
    for i in range(len(pts) - 1):
        b.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], color)


def circle(b, cx, cy, r, color):
    cx = int(round(cx))
    cy = int(round(cy))
    r = int(round(r))
    if r < 1:
        b.px(cx, cy, color)
        return
    x = r
    y = 0
    err = 1 - x
    while y <= x:
        b.px(cx + x, cy + y, color)
        b.px(cx + y, cy + x, color)
        b.px(cx - y, cy + x, color)
        b.px(cx - x, cy + y, color)
        b.px(cx - x, cy - y, color)
        b.px(cx - y, cy - x, color)
        b.px(cx + y, cy - x, color)
        b.px(cx + x, cy - y, color)
        y += 1
        if err < 0:
            err += 2 * y + 1
        else:
            x -= 1
            err += 2 * (y - x) + 1


def arc(b, cx, cy, r, a0, a1, color):
    r = float(r)
    if r < 1.0:
        b.px(cx, cy, color)
        return
    span = a1 - a0
    n = max(2, int(abs(span) * r * 1.35))
    for i in range(n + 1):
        a = a0 + span * i / n
        b.px(cx + math.cos(a) * r, cy + math.sin(a) * r, color)


def diamond(b, cx, cy, r, color):
    r = max(1, int(round(r)))
    cx, cy = int(round(cx)), int(round(cy))
    poly(b, [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy), (cx, cy - r)], color)


def square(b, cx, cy, r, color):
    r = max(1, int(round(r)))
    cx, cy = int(round(cx)), int(round(cy))
    poly(
        b,
        [(cx - r, cy - r), (cx + r, cy - r), (cx + r, cy + r), (cx - r, cy + r), (cx - r, cy - r)],
        color,
    )


def rsquare(b, cx, cy, r, rot, color):
    rad = float(r) * math.sqrt(2.0)
    pts = []
    for i in range(4):
        a = rot + math.pi / 4.0 + i * math.pi / 2.0
        pts.append((cx + math.cos(a) * rad, cy + math.sin(a) * rad))
    pts.append(pts[0])
    poly(b, pts, color)


def plus(b, cx, cy, r, color):
    r = int(round(r))
    cx, cy = int(round(cx)), int(round(cy))
    b.line(cx - r, cy, cx + r, cy, color)
    b.line(cx, cy - r, cx, cy + r, color)


def cross(b, cx, cy, r, color):
    r = int(round(r))
    cx, cy = int(round(cx)), int(round(cy))
    b.line(cx - r, cy - r, cx + r, cy + r, color)
    b.line(cx - r, cy + r, cx + r, cy - r, color)


def chevron(b, x, y, s, color, ang=0.0, spread=0.72):
    c, sn = math.cos(ang), math.sin(ang)

    def rot(px, py):
        return (x + px * c - py * sn, y + px * sn + py * c)

    poly(b, [rot(-s, -s * spread), (x, y), rot(-s, s * spread)], color)


def box(b, x, y, w, h, color):
    x, y = int(round(x)), int(round(y))
    w, h = int(round(w)), int(round(h))
    poly(b, [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)], color)


def dot(b, x, y, color, s=2):
    x, y = int(round(x)), int(round(y))
    if s <= 1:
        b.px(x, y, color)
        return
    h = s // 2
    b.rect(x - h, y - h, s, s, color)


def dashes(b, x0, y0, x1, y1, color, on=3, off=3):
    steps = int(max(abs(x1 - x0), abs(y1 - y0)))
    if steps <= 0:
        b.px(x0, y0, color)
        return
    span = max(1, on + off)
    for i in range(steps + 1):
        if (i % span) >= on:
            continue
        u = i / steps
        b.px(x0 + (x1 - x0) * u, y0 + (y1 - y0) * u, color)


def wave(b, y, x0, x1, amp, freq, phase, color):
    x0, x1 = int(round(x0)), int(round(x1))
    if x1 <= x0:
        return
    prev = None
    for x in range(x0, x1 + 1):
        yy = y + math.sin(x * freq * math.tau + phase) * amp
        if prev is not None:
            b.line(prev[0], prev[1], x, yy, color)
        prev = (x, yy)


def rays(b, cx, cy, n, r0, r1, rot, color):
    for i in range(n):
        a = rot + i * math.tau / n
        c, sn = math.cos(a), math.sin(a)
        b.line(cx + c * r0, cy + sn * r0, cx + c * r1, cy + sn * r1, color)


def ring_dots(b, cx, cy, n, r, rot, color, skip=(), size=2):
    for i in range(n):
        if i in skip:
            continue
        a = rot + i * math.tau / n
        dot(b, cx + math.cos(a) * r, cy + math.sin(a) * r, color, size)


def burst(b, cx, cy, k, color=ICE, reach=9.0):
    if k <= 0.04:
        return
    if k > 0.7:
        b.disc(cx, cy, 2 if reach > 6 else 1, color)
    circle(b, cx, cy, 1.6 + (1.0 - k) * reach, fade(color, 0.3 + 0.7 * k))


def spark(b, cx, cy, k, color=ICE):
    if k <= 0.05:
        return
    if k > 0.6:
        dot(b, cx, cy, color, 3)
    else:
        circle(b, cx, cy, 2 + (1.0 - k) * 3, fade(color, k))


# --- Dilemmes -------------------------------------------------------------


@scene("dilemma", "greniers")
def _greniers(b, t):
    # Un diamant se fend en deux, de part et d'autre de l'axe.
    j = shake(t, 7, 0.8, until=0.7)
    dashes(b, CX + j, 5, CX + j, 31, DIM, 2, 3)
    if t < 0.24:
        diamond(b, CX, CY, 6, OCHRE)
        dot(b, CX, CY, CITY, 2)
    else:
        u = seg(t, 0.24, 0.66)
        d = lerp(8, 12, u)
        diamond(b, CX - d, CY, 5, INK)
        diamond(b, CX + d, CY, lerp(5, 7, u), OCHRE)
        dot(b, CX + d, CY, CITY, 2)
        burst(b, CX, CY, pulse(t, 0.24, 0.08), OCHRE)


def _mini_iss(b, x, y, wing, body):
    x, y = int(round(x)), int(round(y))
    b.rect(x - 8, y - 2, 3, 4, wing)
    b.rect(x + 5, y - 2, 3, 4, wing)
    b.rect(x - 3, y - 1, 6, 2, body)


@scene("dilemma", "iss")
def _iss(b, t):
    # La station tourne. Puis une reste, l'autre tombe.
    circle(b, CX, CY, 7, DIM)
    if t < 0.52:
        ang = -t * math.tau * 1.2
        _mini_iss(b, CX + math.cos(ang) * 14, CY + math.sin(ang) * 8, SEA, INK)
        return
    u = seg(t, 0.52, 0.9)
    ang0 = -0.52 * math.tau * 1.2
    stay = ang0 - u * 1.35
    _mini_iss(b, CX + math.cos(stay) * 14, CY + math.sin(stay) * 8, SEA, INK)
    fx = lerp(CX + math.cos(ang0) * 14, CX + 6, u)
    fy = lerp(CY + math.sin(ang0) * 8, CY + 15, u)
    j = shake(t, 16, 1.5 * u, until=0.92)
    _mini_iss(b, fx + j, fy, fade(OCHRE, 1.0 - u * 0.25), fade(RUST, 0.85))
    burst(b, fx, fy, pulse(t, 0.84, 0.08), OCHRE)


@scene("dilemma", "conflit")
def _conflit(b, t):
    # Deux etoiles miroirs. La droite accelere, et le miroir casse.
    accel = seg(t, 0.12, 0.86)
    slow = t * math.tau * 0.42
    fast = t * math.tau * (0.42 + accel * 2.6)
    j = shake(t, 12, 1.8) * accel
    dashes(b, CX, 8, CX, 28, DIM, 2, 3)
    rays(b, 13, CY, 6, 2, 8, slow, INK)
    dot(b, 13, CY, INK, 2)
    rays(b, 35, CY + j, 6, 2, lerp(8, 11, accel), -fast, mix(INK, OCHRE, accel))
    dot(b, 35, CY + j, OCHRE, 2)


@scene("dilemma", "fumee")
def _fumee(b, t):
    # Trois ondes, une fente qui les coupe, une onde qui pousse en bas.
    hurt = seg(t, 0.08, 0.72)
    for i, y in enumerate((9, 16, 23)):
        col = mix(INK, RUST, 0.2 + hurt * 0.75)
        wave(b, y, 2, CW - 3, lerp(1.1, 2.3, hurt), 0.07, t * math.tau * (0.7 + i * 0.18) + i, col)
    if t > 0.4:
        clear(b, CX - 2, 5, 5, 22)
        b.line(CX, 4, CX, 28, GLASS)
        burst(b, CX, 14, pulse(t, 0.42, 0.07), GLASS)
    half = seg(t, 0.48, 0.9) * 15
    if half > 1.5:
        wave(b, 32, CX - half, CX + half, 1.3, 0.16, t * math.tau * 0.55, MOSS)


@scene("dilemma", "machines")
def _machines(b, t):
    # Grille carree. Un balayage l'allume. Deux points sortent du cadre.
    n, gap = 4, 6
    ox = CX - (n - 1) * gap / 2.0
    oy = CY - (n - 1) * gap / 2.0
    square(b, CX, CY, (n - 1) * gap / 2.0 + 4, DIM)
    for i in range(n):
        x = ox + i * gap
        y = oy + i * gap
        b.line(ox, y, ox + (n - 1) * gap, y, DIM)
        b.line(x, oy, x, oy + (n - 1) * gap, DIM)
    scan = seg(t, 0.08, 0.8)
    for iy in range(n):
        hot = abs(scan * (n - 1) - iy) < 0.55
        for ix in range(n):
            if t > 0.86:
                col = GLASS if (ix + iy) % 2 == 0 else INK
            elif hot:
                col = ICE
            elif iy <= scan * (n - 1):
                col = GLASS
            else:
                col = LINE
            dot(b, ox + ix * gap, oy + iy * gap, col, 2)
    if seg(t, 0.5, 0.7) > 0:
        dot(b, ox - 8, oy + gap, RUST, 2)
    if seg(t, 0.66, 0.84) > 0:
        dot(b, ox + (n - 1) * gap + 8, oy + gap * 2, OCHRE, 2)
    burst(b, CX, CY, pulse(t, 0.84, 0.06), GLASS)


@scene("dilemma", "filon")
def _d_filon(b, t):
    # Trois diamants emboites. Un trait vibre et descend.
    depth = seg(t, 0.1, 0.8)
    j = shake(t, 14, 1.5)
    for i, r0 in enumerate((12, 8, 4)):
        r = max(2, r0 - depth * (2 + i * 2))
        col = OCHRE if i == 2 else (INK if i == 0 else DIM)
        diamond(b, CX, CY, r, col)
    tip = lerp(4, 29, depth)
    b.line(CX + j, 3, CX + j, tip, GLASS)
    dot(b, CX + j, tip, ICE, 1)
    if 0.15 < t < 0.86 and strobe(t, 9):
        dot(b, CX + 5, tip, OCHRE, 1)
        dot(b, CX - 4, tip + 1, SAND, 1)


@scene("dilemma", "assiettes")
def _assiettes(b, t):
    # Un cercle se vide. En dessous, une onde symetrique grandit.
    circle(b, CX, CY - 2, 11, INK)
    circle(b, CX, CY - 2, 7, DIM)
    spots = ((-4, -3), (4, -3), (0, 0), (-3, 3), (3, 3))
    gone = int(seg(t, 0.16, 0.78) * len(spots) + 0.001)
    for i, (dx, dy) in enumerate(spots):
        if i >= gone:
            dot(b, CX + dx, CY - 2 + dy, OCHRE, 2)
    burst(b, CX, CY - 2, pulse(t, 0.42, 0.07), SAND)
    half = seg(t, 0.4, 0.88) * 16
    if half > 1.5:
        wave(b, 32, CX - half, CX + half, 1.4, 0.15, t * math.tau * 0.5, MOSS)


@scene("dilemma", "age")
def _age(b, t):
    # La ronde grossit, puis il n'en reste que deux, face a face.
    appear = seg(t, 0.0, 0.4)
    n = 4 + 2 * int(appear * 3 + 0.001)
    cut = seg(t, 0.5, 0.84)
    r = 11
    circle(b, CX, CY, r, fade(DIM, 1.0 - cut * 0.7))
    for i in range(n):
        a = i * math.tau / n
        keep = i == 0 or i == n // 2
        if not keep and cut > 0.92:
            continue
        if keep:
            col = INK if i == 0 else OCHRE
            rr = r
        else:
            col = fade(INK, 1.0 - cut)
            rr = r + cut * 5
        j = shake(t, 5, 0.6 if keep else 1.3, phase=i * 0.2) * (1.0 - cut if keep else 1.0)
        dot(b, CX + math.cos(a) * rr, CY + math.sin(a) * rr + j, col, 3 if keep and cut > 0.45 else 2)
    if cut > 0.25:
        dashes(b, CX - 9, CY, CX + 9, CY, fade(INK, cut), 2, 2)
    burst(b, CX, CY, pulse(t, 0.52, 0.08), ICE)


@scene("dilemma", "ecole")
def _ecole(b, t):
    # Un signe entre dans le carre, et s'y dedouble.
    square(b, 32, CY, 8, GLASS)
    u = seg(t, 0.06, 0.6)
    if u < 0.98:
        y = CY + shake(t, 3, 1.0) * (1.0 - u)
        plus(b, lerp(8, 30, u), y, 3, OCHRE)
    else:
        plus(b, 28, CY, 2, INK)
        plus(b, 36, CY, 2, OCHRE)
    burst(b, 32, CY, pulse(t, 0.62, 0.08), ICE)


@scene("dilemma", "sol")
def _sol(b, t):
    # Des lignes droites se fendent. Chaque moitie prend le contretemps.
    crack = seg(t, 0.26, 0.8)
    for i in range(5):
        y = 7 + i * 5
        col = mix(OCHRE, SAND, crack * (0.25 + i * 0.14))
        phase = t * math.tau * 0.5 + i * 0.45
        gap = crack * (3.0 + i)
        amp = crack * 1.6
        if gap < 1.3:
            wave(b, y, 5, 43, amp, 0.055, phase, col)
        else:
            wave(b, y, 5, CX - gap, amp, 0.055, phase, col)
            wave(b, y, CX + gap, 43, amp, 0.055, phase + math.pi, col)
    burst(b, CX, CY, pulse(t, 0.3, 0.07), SAND)


@scene("dilemma", "usure")
def _usure(b, t):
    # Un anneau de points. L'un se detache et tombe.
    spin = t * math.tau * 0.85
    amp = 1.8 * seg(t, 0.05, 0.26) * (1.0 - seg(t, 0.26, 0.4))
    j = math.sin(t * 11 * math.tau) * amp
    circle(b, CX, CY + j, 11, DIM)
    ring_dots(b, CX, CY + j, 6, 11, spin, INK, skip=(0,) if t > 0.4 else ())
    if t > 0.4:
        a0 = 0.4 * math.tau * 0.85
        x = CX + math.cos(a0) * 11
        y0 = CY + math.sin(a0) * 11
        dot(b, x, lerp(y0, 31, seg(t, 0.4, 0.7)), OCHRE, 2)
        burst(b, x, y0, pulse(t, 0.4, 0.07), RUST)


@scene("dilemma", "heritage")
def _heritage(b, t):
    # Deux cercles, le grand et le petit. Une onde passe de l'un a l'autre.
    circle(b, CX, CY, 14, DIM)
    circle(b, CX, CY, 5, INK)
    u = seg(t, 0.08, 0.74)
    ring = lerp(14, 5, u)
    circle(b, CX, CY, ring, fade(OCHRE, 0.25 + 0.75 * math.sin(u * math.pi)))
    if u > 0.9:
        dot(b, CX, CY, OCHRE, 2)
    burst(b, CX, CY, pulse(t, 0.74, 0.1), ICE)


@scene("dilemma", "soins")
def _soins(b, t):
    # Une balance. Elle oscille, puis se pose.
    tilt = math.sin(t * math.tau * 1.2) * settle(t, 0.72) * 5
    b.line(8, CY - tilt, 40, CY + tilt, INK)
    b.line(CX, CY + 2, CX - 4, CY + 8, DIM)
    b.line(CX, CY + 2, CX + 4, CY + 8, DIM)
    b.line(CX - 4, CY + 8, CX + 4, CY + 8, DIM)
    left = CY - tilt * 0.55
    plus(b, 12, left - 6, 4, GLASS)
    for i, h in enumerate((6, 10, 5)):
        x = 28 + i * 5
        by = CY + tilt * ((x - CX) / 16.0)
        box(b, x, by - h - 3, 3, h, OCHRE)


@scene("dilemma", "dernier")
def _dernier(b, t):
    # Un arc de temps, presque boucle. Deux signes au centre.
    fill = lerp(0.74, 0.93, seg(t, 0.0, 0.82))
    a0 = -math.pi / 2.0
    a1 = a0 + fill * math.tau
    arc(b, CX, CY, 12, a0, a1, INK)
    for i in range(12):
        a = a0 + i * math.tau / 12.0
        col = OCHRE if (i / 12.0) <= fill else DIM
        c, sn = math.cos(a), math.sin(a)
        b.line(CX + c * 13, CY + sn * 13, CX + c * 15, CY + sn * 15, col)
    diamond(b, CX - 5, CY + 1, lerp(4, 2, seg(t, 0.35, 0.9)), OCHRE)
    circle(b, CX + 5, CY + 1, 3, INK)
    burst(b, CX + math.cos(a1) * 12, CY + math.sin(a1) * 12, pulse(t, 0.8, 0.07), OCHRE)


@scene("dilemma", "fin")
def _fin(b, t):
    # Deux arcs presque fermes, en contretemps. Le cran qui manque tremble.
    j = shake(t, 6, 1.5, until=0.78)
    fill = 0.9
    a0 = -math.pi / 2.0
    a1 = a0 + fill * math.tau
    arc(b, CX, CY - j, 13, a0, a1, GLASS)
    arc(b, CX, CY + j, 10, a0, a1, RUST)
    dot(b, CX + math.cos(a1) * 13, CY - j + math.sin(a1) * 13, INK, 2)


# --- Cartes detournees par la limite qui serre ----------------------------


@scene("fork", "pollution")
def _f_pollution(b, t):
    # L'air est trop plein. Une fenetre essaie de s'ouvrir, puis se ferme.
    k = seg(t, 0.0, 0.7)
    for i, y in enumerate((6, 12, 18, 24, 30)):
        amp = lerp(1.15, 2.15, k)
        freq = lerp(0.045, 0.068, k)
        wave(b, y, 0, CW - 1, amp, freq, t * math.tau * (0.9 + i * 0.14) + i * 0.7, mix(DIM, RUST, 0.4 + k * 0.6))
    w = lerp(9, 0, seg(t, 0.3, 0.88))
    if w >= 2.2:
        clear(b, CX - w, CY - w, w * 2, w * 2)
        square(b, CX, CY, w, GLASS)


@scene("fork", "essor")
def _f_essor(b, t):
    # Carres et diamants qui s'elancent, de plus en plus vite.
    speed = lerp(0.55, 3.4, seg(t, 0.0, 0.88))
    phase = t * speed
    for i in range(3):
        p = (phase + i / 3.0) % 1.0
        r = 3 + p * 13
        col = fade(OCHRE, 1.0 - p * 0.8)
        if i % 2 == 0:
            rsquare(b, CX, CY, r, p * 0.9, col)
        else:
            diamond(b, CX, CY, r * 0.82, col)
    dot(b, CX, CY, OCHRE, 2)
    if t < 0.9 and strobe(t, 8 + speed * 2, until=0.9):
        plus(b, CX, CY, 3, ICE)


@scene("fork", "sol")
def _f_sol(b, t):
    # A gauche les lignes cèdent. A droite le diamant ne bouge pas.
    crack = seg(t, 0.16, 0.8)
    dashes(b, 30, 6, 30, 31, DIM, 2, 3)
    for i in range(4):
        y = 8 + i * 5
        reach = lerp(26, 14, crack)
        wave(b, y, 4, reach, crack * 1.3, 0.08, t * math.tau * 0.45 + i * 0.5, mix(MOSS, SAND, crack))
    diamond(b, 38, 16, 6, OCHRE)
    dot(b, 38, 16, CITY, 2)


@scene("fork", "metal")
def _f_metal(b, t):
    # Un diamant prend des coups. Il retrecit a chaque impact.
    hits = (0.18, 0.4, 0.62, 0.82)
    done = sum(1 for h in hits if t >= h)
    r = lerp(8, 5, done / 4.0)
    j = shake(t, 14, 0.6 + done * 0.3, until=0.9)
    cy = CY + 3
    diamond(b, CX + j * 0.2, cy, r, OCHRE if done < 3 else SAND)
    contact = cy - r
    saw = (t * 4.0) % 1.0
    if t < 0.92:
        if saw < 0.7:
            tip = lerp(3, contact - 1, saw / 0.7)
        else:
            tip = lerp(contact - 1, 3, (saw - 0.7) / 0.3)
        b.line(CX, tip, CX, min(tip + 6, contact), ICE if saw > 0.5 else DIM)
    spark(b, CX, contact, pulses(t, hits, 0.04), OCHRE)


@scene("fork", "faim")
def _f_faim(b, t):
    # Un cercle vide, qui tremble. L'arc d'en bas n'arrive pas au bout.
    jx = shake(t, 9, 1.1)
    jy = shake(t, 11, 1.4, phase=0.25)
    circle(b, CX + jx * 0.35, CY + jy * 0.25, 13, INK)
    spots = 5
    left = spots - int(seg(t, 0.1, 0.62) * spots + 0.001)
    for i in range(spots):
        a = -math.pi / 2.0 + i * math.tau / spots
        if i < left:
            dot(b, CX + math.cos(a) * 5, CY + math.sin(a) * 5, OCHRE, 2)
    grown = seg(t, 0.38, 0.58)
    if grown > 0.02:
        arc(b, CX, CY, 13, 0.35, 0.35 + grown * 1.15, MOSS)


# --- Evenements du monde --------------------------------------------------


@scene("shock", "iag")
def _iag(b, t):
    # Deux etoiles a quatre branches, en sens inverse. Le cadre se tache.
    accel = seg(t, 0.08, 0.8)
    spin = t * math.tau * (0.28 + accel * 1.6)
    arm = lerp(6, 12, seg(t, 0.06, 0.55)) + shake(t, 5, 0.45, until=0.78)
    rays(b, CX, CY, 4, 2, lerp(3, 5, accel), -spin, DIM)
    rays(b, CX, CY, 4, 3, arm, spin, GLASS)
    if accel > 0.28:
        rays(b, CX, CY, 4, 3, arm * 0.72, spin + math.pi / 4.0, fade(ICE, (accel - 0.28) / 0.72))
    dot(b, CX, CY, OCHRE, 2)
    if t > 0.58:
        k = seg(t, 0.58, 0.86)
        for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            dot(b, CX + sx * 17, CY + sy * 14, fade(RUST, k), 2)
    burst(b, CX, CY, pulse(t, 0.58, 0.07), ICE)


@scene("shock", "fusion")
def _fusion(b, t):
    # Deux points se cherchent, se touchent, et une onde ronde part.
    u = seg(t, 0.06, 0.5)
    d = lerp(16, 0, u)
    j = math.sin(t * (6 + u * 14) * math.tau) * u * (1.0 - u) * 8
    if u < 0.97:
        b.line(CX - d, CY, CX + d, CY, DIM)
        dot(b, CX - d, CY + j, GLASS, 2)
        dot(b, CX + d, CY - j, GLASS, 2)
    else:
        dot(b, CX, CY, OCHRE, 3)
    if t >= 0.5:
        age = seg(t, 0.5, 0.92)
        circle(b, CX, CY, lerp(3, 8, age), fade(GLASS, 0.95 - age * 0.4))
        circle(b, CX, CY, lerp(4, 14, age), fade(OCHRE, 0.75 - age * 0.4))
        dot(b, CX, CY, OCHRE, 3)
    burst(b, CX, CY, pulse(t, 0.5, 0.1), ICE)


@scene("shock", "pandemie")
def _pandemie(b, t):
    # Une trame de points. Un front vertical les eteint.
    cols, rows, gap = 7, 4, 6
    ox = CX - (cols - 1) * gap / 2.0
    oy = 8
    edge = seg(t, 0.1, 0.78) * (cols - 2)
    for iy in range(rows):
        for ix in range(cols):
            if ix < edge - 1.4:
                continue
            x = ox + ix * gap
            y = oy + iy * gap
            if ix < edge:
                y += shake(t, 10, 1.0, phase=ix * 0.2, until=0.8)
                col = RUST
            else:
                col = INK
            dot(b, x, y, col, 2)
    if t < 0.8:
        fx = ox + edge * gap
        b.line(fx, oy - 3, fx, oy + (rows - 1) * gap + 3, RUST)
        burst(b, fx, oy + gap * 1.5, pulse(t, 0.42, 0.08), RUST)


@scene("shock", "climat")
def _climat(b, t):
    # Une onde reguliere, puis une seconde frequence la defait.
    br = seg(t, 0.18, 0.82)
    prev = None
    col = mix(OCHRE, RUST, br)
    for x in range(3, 46):
        y = 22.0
        y += math.sin(x * 0.085 * math.tau + t * math.tau) * (4.4 * (1.0 - br) + 0.5)
        y += math.sin(x * 0.029 * math.tau - t * math.tau * 1.7) * (br * 5.5)
        if prev is not None:
            b.line(prev[0], prev[1], x, y, col)
        prev = (x, y)
    d = br * 11
    circle(b, CX - d, 8, 3, OCHRE)
    circle(b, CX + d, 8, 3, mix(OCHRE, RUST, br))


@scene("shock", "guerre")
def _guerre(b, t):
    # Deux chevrons se foncent dessus. L'impact les disperse.
    u = seg(t, 0.06, 0.46)
    if t < 0.48:
        j = math.sin(t * 9 * math.tau) * (0.35 + u) * 2.4
        chevron(b, CX - lerp(16, 3, u), CY - j, 6, INK, 0.0, 0.8)
        chevron(b, CX + lerp(16, 3, u), CY + j, 6, RUST, math.pi, 0.8)
    else:
        k = seg(t, 0.48, 0.76)
        chevron(b, lerp(CX - 3, 8, k), CY, 5, INK, math.pi, 0.78)
        chevron(b, lerp(CX + 3, CW - 8, k), CY, 5, RUST, 0.0, 0.78)
        if k < 0.42:
            rays(b, CX, CY, 6, 2, lerp(9, 3, k / 0.42), 0.4, fade(OCHRE, 1.0 - k / 0.42))
    burst(b, CX, CY, pulse(t, 0.48, 0.1), OCHRE)


@scene("shock", "paix")
def _paix(b, t):
    # Les chevrons s'aplatissent en une ligne. Un carre se cale.
    u = seg(t, 0.05, 0.5)
    vis = 1.0 - seg(t, 0.4, 0.58)
    y = 25
    if vis > 0.04:
        chevron(b, CX - lerp(16, 2, u), y, 6, fade(INK, vis), 0.0, lerp(0.9, 0.04, u))
        chevron(b, CX + lerp(16, 2, u), y, 6, fade(RUST, vis), math.pi, lerp(0.9, 0.04, u))
    if t > 0.4:
        b.line(8, y, 40, y, fade(INK, seg(t, 0.4, 0.62)))
    if t > 0.5:
        rot = (1.0 - seg(t, 0.5, 0.9)) * 0.7
        rsquare(b, CX, 12, 6, rot, MOSS)
        if seg(t, 0.5, 0.9) > 0.82:
            plus(b, CX, 12, 3, MOSS)
        burst(b, CX, 12, pulse(t, 0.88, 0.07), ICE)


@scene("shock", "secheresse")
def _secheresse(b, t):
    # Les ondes s'amincissent jusqu'au trait, puis au pointille.
    dry = seg(t, 0.08, 0.72)
    for i, y in enumerate((16, 21, 26)):
        amp = (2.4 - i * 0.3) * (1.0 - dry)
        col = fade(GLASS, 1.0 - dry * 0.85)
        if amp > 0.35:
            wave(b, y - dry * 2, 5, 43, amp, 0.12, t * math.tau * 0.9 + i * 0.7, col)
        elif dry > 0.55:
            dashes(b, 6, int(y), 42, int(y), SAND, 2, 3)
    rays(b, 36, 8, 4, 2, lerp(3, 8, dry), t * math.tau * 0.25, mix(OCHRE, RUST, dry))
    dot(b, 36, 8, mix(OCHRE, RUST, dry), 2)


@scene("shock", "gisement")
def _gisement(b, t):
    # Un diamant s'allume. Les ronds partent, puis une onde rouille reste.
    appear = seg(t, 0.06, 0.28)
    if appear > 0:
        diamond(b, CX, CY + 2, lerp(2, 7, appear), OCHRE)
        dot(b, CX, CY + 2, CITY, 2)
    burst(b, CX, CY + 2, pulse(t, 0.16, 0.1), OCHRE)
    if 0.3 < t < 0.92:
        for i in range(3):
            p = seg(t, 0.3 + i * 0.07, 0.9)
            if p <= 0.0 or p >= 1.0:
                continue
            circle(b, CX, CY + 2, 6 + p * (7 + i * 3), fade(OCHRE, (1.0 - p) * 0.85))
    if t > 0.58:
        a = seg(t, 0.58, 0.88)
        wave(b, 8, 6, 42, lerp(0.5, 2.3, a), 0.09, t * math.tau * 1.25, fade(RUST, 0.4 + a * 0.6))


@scene("shock", "filon")
def _s_filon(b, t):
    # Trois diamants dans un cercle qui se ferme. Ils s'eteignent.
    close = seg(t, 0.12, 0.86)
    circle(b, CX, CY, 13, DIM)
    arc(b, CX, CY, 13, -math.pi / 2.0, -math.pi / 2.0 + close * math.tau, OCHRE)
    gems = ((-5, -2), (4, -4), (0, 4))
    gone = int(close * 3 + 0.001)
    for i, (dx, dy) in enumerate(gems):
        if i < gone:
            continue
        diamond(b, CX + dx, CY + dy, 3, OCHRE)
    if gone >= 3:
        cross(b, CX, CY, 4, fade(RUST, seg(t, 0.78, 0.95)))
    burst(b, CX, CY, pulse(t, 0.84, 0.08), SAND)


@scene("shock", "accord")
def _accord(b, t):
    # Deux ondes viennent l'une vers l'autre. Elles n'en font plus qu'une.
    u = seg(t, 0.05, 0.52)
    j = shake(t, 4, 1.6, until=0.52) * (1.0 - u)
    if t < 0.62:
        vis = 1.0 - seg(t, 0.5, 0.64)
        left = lerp(10, CX - 1, u)
        right = lerp(CW - 10, CX + 1, u)
        wave(b, CY - j, 3, left, 2.8, 0.11, t * math.tau * 1.3, fade(RUST, vis))
        wave(b, CY + j, right, CW - 3, 2.8, 0.11, -t * math.tau * 1.3, fade(RUST, vis))
    if t > 0.48:
        amp = lerp(2.6, 1.45, seg(t, 0.5, 0.9))
        wave(b, CY, 6, CW - 6, amp, 0.08, t * math.tau * 0.55, fade(GLASS, seg(t, 0.48, 0.66)))
    k = pulse(t, 0.52, 0.09)
    if k > 0.05:
        b.line(CX, 6, CX, 30, fade(ICE, k))


@scene("shock", "accident")
def _accident(b, t):
    # Un carre tient. Le flash part a cote, et les ronds le depassent.
    j = 0.0
    if t > 0.38:
        j = shake(t, 15, 1.6, until=0.7) * (1.0 - seg(t, 0.38, 0.75))
    square(b, CX + j, CY, 11, INK)
    square(b, CX + j, CY, 6, DIM)
    ox, oy = CX + 6, CY - 5
    if t > 0.36:
        for i in range(3):
            p = seg(t, 0.36 + i * 0.05, 0.9)
            if p <= 0.0 or p >= 1.0:
                continue
            circle(b, ox, oy, 2 + p * (6 + i * 4), fade(RUST, (1.0 - p) * 0.9))
        circle(b, ox, oy, lerp(3, 6, seg(t, 0.4, 0.75)), fade(RUST, 0.85))
        burst(b, ox, oy, pulse(t, 0.38, 0.09), RUST)


@scene("shock", "ecoles")
def _ecoles(b, t):
    # Trois points entrent dans le carre et s'alignent.
    square(b, 33, CY, 9, GLASS)
    for i in range(3):
        u = seg(t, 0.05 + i * 0.16, 0.36 + i * 0.15)
        y = CY - 5 + i * 5
        if u < 1.0:
            dot(b, lerp(6, 30, u), y, OCHRE if i != 1 else GLASS, 2)
        else:
            dot(b, 30, y, INK, 2)
            spark(b, 33, y, pulse(t, 0.36 + i * 0.15, 0.05), ICE)


@scene("shock", "baby")
def _baby(b, t):
    # Un point se dedouble : deux, quatre, huit.
    marks = (0.22, 0.46, 0.7)
    idx = 0
    for at in marks:
        if t >= at:
            idx += 1
    n = (1, 2, 4, 8)[idx]
    r = (0, 6, 9, 12)[idx]
    if n == 1:
        dot(b, CX, CY, OCHRE, 3)
    else:
        ring_dots(b, CX, CY, n, r, -math.pi / 2.0, OCHRE if idx < 3 else INK, size=2)
    burst(b, CX, CY, pulses(t, marks, 0.06), ICE)


@scene("shock", "medecine")
def _medecine(b, t):
    # Un point s'agite, puis se tient. La croix grandit, l'arc aussi.
    calm = seg(t, 0.08, 0.7)
    j = shake(t, 10, 2.2, until=0.55) * (1.0 - calm)
    dot(b, 8, CY + j, mix(RUST, INK, calm), 2)
    if calm < 0.4 and strobe(t, 7, until=0.4):
        dot(b, 8, CY - 5, RUST, 1)
    plus(b, 28, CY, lerp(3, 6, calm), fade(GLASS, 0.35 + calm * 0.65))
    arc(b, CX, CY, 14, -0.85, -0.85 + calm * 2.15, fade(MOSS, 0.3 + calm * 0.7))


@scene("shock", "insectes")
def _insectes(b, t):
    # Six branches. Les points qui tournent autour s'en vont, et ca ploie.
    leave = seg(t, 0.16, 0.82)
    twist = leave * 0.35
    for i in range(6):
        die = leave if i % 2 else 0.0
        if die > 0.94:
            continue
        length = lerp(11, 2.2, die)
        a = -math.pi / 2.0 + i * math.tau / 6.0 + twist
        c, sn = math.cos(a), math.sin(a)
        col = fade(mix(MOSS, SAND, leave * 0.7), 1.0 - die * 0.15)
        b.line(CX + c * 2, CY + sn * 2, CX + c * length, CY + sn * length, col)
    dot(b, CX, CY, mix(OCHRE, SAND, leave), 2)
    for i in range(3):
        u = seg(t, 0.1 + i * 0.1, 0.58 + i * 0.1)
        if u >= 1.0:
            continue
        a = t * math.tau * (1.15 + i * 0.28) + i * 2.0
        rr = 5 + u * 13
        dot(b, CX + math.cos(a) * rr, CY + math.sin(a) * rr, fade(OCHRE, 1.0 - u), 2)


@scene("shock", "circulaire")
def _circulaire(b, t):
    # Un diamant fait le tour, et revient au meme point.
    circle(b, CX, CY, 12, DIM)
    u = min(1.0, seg(t, 0.04, 0.9))
    steps = int(u * 30)
    for i in range(steps):
        a = -math.pi / 2.0 + i / 30.0 * math.tau
        dot(b, CX + math.cos(a) * 12, CY + math.sin(a) * 12, fade(OCHRE, 0.28 + 0.35 * i / 30.0), 1)
    a = -math.pi / 2.0 + u * math.tau
    diamond(b, CX + math.cos(a) * 12, CY + math.sin(a) * 12, 3, OCHRE)
    if u > 0.98:
        burst(b, CX, CY - 12, pulse(t, 0.9, 0.08), ICE)


@scene("shock", "krach")
def _krach(b, t):
    # Cinq cadres. Ils tremblent, puis s'ecroulent l'un apres l'autre.
    heights = (15, 11, 18, 8, 13)
    dashes(b, 4, 31, 44, 31, DIM, 2, 2)
    for i, h0 in enumerate(heights):
        u = seg(t, 0.16 + i * 0.07, 0.58 + i * 0.05)
        h = lerp(h0, 2, u)
        x = 6 + i * 8
        j = shake(t, 13, 1.1, phase=i * 0.3) * (1.0 - u)
        col = OCHRE if h > 6 else RUST
        box(b, x + j, 31 - h, 4, h, col)
    spark(b, 22, 30, pulse(t, 0.4, 0.06), OCHRE)


@scene("shock", "barrages")
def _barrages(b, t):
    # Un trait vertical. L'eau monte a gauche, file a droite, une onde pousse.
    b.line(16, 6, 16, 32, INK)
    b.line(18, 6, 18, 32, DIM)
    n = int(seg(t, 0.05, 0.42) * 4 + 0.001)
    for i in range(n):
        y = 28 - i * 5
        wave(b, y, 3, 15, 1.05, 0.1, t * math.tau * 1.15 + i * 0.8, SEA if i < 3 else GLASS)
    if t > 0.4:
        reach = lerp(19, 44, seg(t, 0.4, 0.76))
        wave(b, 28, 19, reach, 1.0, 0.16, t * math.tau * 2.0, GLASS)
    grown = seg(t, 0.6, 0.95)
    if grown > 0.04:
        wave(b, 16, 24, lerp(26, 44, grown), 0.6 + grown * 1.6, 0.18, t * math.tau * 0.45, MOSS)


@scene("shock", "charbon")
def _charbon(b, t):
    # Quatre carres. Au-dessus, les ondes s'epaississent.
    k = seg(t, 0.1, 0.78)
    bands = 1 + int(k * 2.2)
    for i, y in enumerate((9, 15)):
        col = mix(DIM, RUST, 0.25 + k * 0.75)
        phase = t * math.tau * (0.75 + k * 0.8) + i * 1.3
        amp = 0.9 + k * 2.0
        for dy in range(bands):
            wave(b, y + dy, 4, 44, amp, 0.075, phase, fade(col, 0.5 + 0.5 * (dy == 0)))
    for i in range(4):
        x = 12 + i * 6
        square(b, x, 28, 2, INK)
        if t < 0.7 and strobe(t, 3.0 + i, until=0.7):
            dot(b, x, 28, OCHRE, 1)


@scene("shock", "batteries")
def _batteries(b, t):
    # Trois colonnes se remplissent. Un diamant s'allume quand elles sont pleines.
    air = 1.0 - seg(t, 0.5, 0.92)
    if air > 0.05:
        wave(b, 31, 3, 45, 1.5 * air, 0.07, t * math.tau, fade(RUST, air))
        wave(b, 34, 3, 45, 0.9 * air, 0.1, t * math.tau + 1.2, fade(RUST, air * 0.75))
    for i in range(3):
        level = seg(t, 0.06 + i * 0.16, 0.34 + i * 0.16)
        x, y, w, h = 6 + i * 9, 6, 6, 18
        if level > 0:
            fh = int(round((h - 1) * level))
            if fh > 0:
                col = GLASS if level > 0.98 else OCHRE
                b.rect(x + 1, y + h - fh, w - 1, fh, col)
        box(b, x, y, w, h, INK)
    if t > 0.7:
        diamond(b, 40, 15, lerp(2, 5, seg(t, 0.7, 0.88)), GLASS)
        burst(b, 40, 15, pulse(t, 0.86, 0.08), ICE)


@scene("shock", "erosion")
def _erosion(b, t):
    # Les lignes glissent, se raccourcissent. Une lame d'eau les traverse.
    u = seg(t, 0.1, 0.84)
    for i in range(5):
        y = 7 + i * 5
        slide = u * (4 + i * 5)
        length = lerp(34, 12, u * (0.25 + i * 0.16))
        col = fade(OCHRE if i % 2 == 0 else SAND, 1.0 - u * 0.25)
        x0 = 4 + slide
        for kseg in range(3):
            x = x0 + kseg * (length / 2.2)
            w = lerp(8, 3.5, u)
            tilt = u * (kseg - 1) * 1.4
            if x < CW - 2:
                b.line(x, y, min(CW - 2, x + w), y + tilt, col)
    front = lerp(4, 44, u)
    wave(b, 18, max(3, front - 12), front, 2.0, 0.11, t * math.tau * 1.4, SEA)


@scene("shock", "vaccin")
def _vaccin(b, t):
    # Des points rouges. Un diamant tombe au centre. Ils s'eteignent.
    dots = ((8, 10), (16, 27), (40, 11), (38, 26), (14, 16), (36, 30))
    kill = seg(t, 0.52, 0.88)
    for i, (x, y) in enumerate(dots):
        if kill > (i + 0.15) / len(dots):
            continue
        j = shake(t, 8, 1.2, phase=i * 0.31, until=0.7) * (1.0 - kill)
        dot(b, x, y + j, fade(RUST, 1.0 - kill * 0.5), 2)
    if t < 0.5:
        y = lerp(8, 17, seg(t, 0.05, 0.5))
        diamond(b, CX, y, 3, ICE)
        b.line(CX, y - 7, CX, y - 3, fade(GLASS, 0.8))
    else:
        plus(b, CX, CY, 5, ICE)
        circle(b, CX, CY, lerp(4, 12, seg(t, 0.5, 0.86)), fade(GLASS, 0.7))
        burst(b, CX, CY, pulse(t, 0.5, 0.1), ICE)


@scene("shock", "spatial")
def _spatial(b, t):
    # A gauche un diamant se calme. A droite, un chevron en apporte un autre.
    calm = seg(t, 0.3, 0.78)
    j = shake(t, 7, 1.3) * (1.0 - calm)
    diamond(b, 11, 26 + j, 5, fade(OCHRE, 1.0 - calm * 0.5))
    u = seg(t, 0.0, 0.6)
    y = lerp(8, 26, u)
    b.line(34, 4, 34, max(4, y - 6), DIM)
    if u < 0.98:
        chevron(b, 34, y, 5, GLASS, math.pi / 2.0, 0.7)
    else:
        diamond(b, 34, 26, 4, OCHRE)
        dot(b, 34, 26, CITY, 2)
    burst(b, 34, 26, pulse(t, 0.62, 0.08), OCHRE)


@scene("shock", "jetable")
def _jetable(b, t):
    # Un carre tremble de plus en plus fort, puis ses quatre coins partent.
    if t < 0.38:
        j = shake(t, lerp(6, 16, t / 0.38), lerp(0.4, 2.2, t / 0.38), until=0.38)
        rsquare(b, CX + j, CY, 7, j * 0.12, INK)
    else:
        u = seg(t, 0.38, 0.72)
        d = lerp(7, 15, u)
        for i, (sx, sy) in enumerate(((-1, -1), (1, -1), (-1, 1), (1, 1))):
            j = shake(t, 9, 0.8, phase=i * 0.25, until=0.8)
            x = CX + sx * d + j
            y = CY + sy * d
            col = OCHRE if i % 2 == 0 else SAND
            b.line(x, y, x - sx * 4, y, col)
            b.line(x, y, x, y - sy * 4, col)
        burst(b, CX, CY, pulse(t, 0.38, 0.08), OCHRE)


def key_for_dilemma(ev):
    title = ev["title"]
    lines = ev["lines"]
    for name, fork in FORKS.items():
        if fork["title"] == title and fork["lines"] == lines:
            return ("fork", name)
    return ("dilemma", ev["id"])


def key_for_shock(shock):
    return ("shock", shock["id"])


def catalog():
    """Toutes les cartes, dans l'ordre ou on les teste."""
    items = []
    for ev in EVENTS:
        items.append(
            {
                "key": ("dilemma", ev["id"]),
                "group": "DILEMMES",
                "title": ev["title"],
                "meta": str(ev["year"]),
                "lines": ev["lines"],
                "effect": "",
            }
        )
    items.append(
        {
            "key": ("dilemma", ISS_CARD["id"]),
            "group": "DILEMMES",
            "title": ISS_CARD["title"],
            "meta": "AVANT",
            "lines": ISS_CARD["lines"],
            "effect": "",
        }
    )
    notes = {
        "pollution": "L'AIR SERRE",
        "essor": "L'ESSOR SERRE",
        "sol": "LE SOL SERRE",
        "metal": "LE MÉTAL SERRE",
        "faim": "LA FAIM SERRE",
    }
    for name, fork in FORKS.items():
        items.append(
            {
                "key": ("fork", name),
                "group": "AUTRE LIMITE",
                "title": fork["title"],
                "meta": notes.get(name, name.upper()),
                "lines": fork["lines"],
                "effect": "",
            }
        )
    for sh in SHOCKS:
        items.append(
            {
                "key": ("shock", sh["id"]),
                "group": "ÉVÉNEMENTS",
                "title": sh["title"],
                "meta": sh["id"].upper(),
                "lines": sh["lines"],
                "effect": sh["effect"],
            }
        )
    return items


def render_anim(dest, key, t, center, scale=SCALE):
    import pygame

    buf = pygame.Surface((CW, CH))
    buf.fill(BG)
    fn = SCENES.get(key)
    if fn is not None:
        tt = 0.0 if t < 0 else 1.0 if t > 1 else t
        fn(Board(buf), tt)
    _zoom(dest, buf, center, scale)


_ZOOM = {}


def _zoom(dest, src, center, scale):
    import pygame

    w, h = src.get_size()
    out = _ZOOM.get((w, h, scale))
    if out is None:
        out = pygame.Surface((w * scale, h * scale))
        _ZOOM[(w, h, scale)] = out
    arr = pygame.surfarray.array3d(src)
    pygame.surfarray.blit_array(out, np.repeat(np.repeat(arr, scale, axis=0), scale, axis=1))
    dest.blit(out, (center[0] - (w * scale) // 2, center[1] - (h * scale) // 2))
