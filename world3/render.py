"""Dessin de l'ecran 720x720. Pas d'antialiasing : des rectangles."""

import math

import numpy as np
import pygame

from device.widgets import corner_hit, draw_home, home_rect

from .anims import REVEAL_DUR, key_for_dilemma, render_anim
from .content import (
    AIDE,
    FIN,
    INFO,
    INTRO,
    LAWS,
    TURN_LABEL,
    card_info,
    choice_parts,
    iss_visible,
    token_label,
)
from .save import MAX_SEALS
from .sim import (
    SCALES,
    START_YEAR,
    UNITS,
    VITALS,
    TURN_YEARS,
    YEAR_MAX,
    YEAR_MIN,
    format_vital,
    satellite_count,
    vital_phrase,
    vital_tone,
)
from .theme import (
    BG,
    CONDITION,
    DIM,
    GLASS,
    H,
    ICE,
    INK,
    LINE,
    MUTED,
    NAV_H,
    NAV_Y,
    OCHRE,
    PLANET_C,
    PLANET_R,
    RING_R,
    EVENT_WAVE,
    RUST,
    SEA,
    SERIES_COLOR,
    W,
    mix,
    tone_color,
)

# Une bande par série. Le doigt lit l'année sur toute la pile.
# Graphe unique, sous l'en-tête de la planète et au-dessus des mêmes cartes.
_PLOT_X = 24
_PLOT_Y = 128
_PLOT_W = W - 48
_PLOT_H = 440
_PLOT_INSET = 16
_AXIS_Y = _PLOT_Y + _PLOT_H + 6
PLOT_RECT = pygame.Rect(_PLOT_X, _PLOT_Y, _PLOT_W, _PLOT_H)
_ICON = 48


class Hits:
    def __init__(self):
        self.items = []

    def add(self, rect, fn, ident=None):
        self.items.append((pygame.Rect(rect), fn, ident))

    def at(self, pos):
        for rect, fn, ident in reversed(self.items):
            if rect.collidepoint(pos):
                return rect, fn, ident
        return None


def nav_rects():
    """Trois onglets a gauche, un carre a droite pour la roue."""
    side = NAV_H
    rest = W - side
    widths = [rest // 3] * 3
    for i in range(rest % 3):
        widths[i] += 1
    rects = []
    x = 0
    for width in widths:
        rects.append(pygame.Rect(x, NAV_Y, width, NAV_H))
        x += width
    rects.append(pygame.Rect(x, NAV_Y, side, side))
    return rects


_GEARS = {}
_GEAR_KEY = (255, 0, 255)


def draw_gear(surf, center, color, hole):
    """Roue a six dents courtes et larges, collees a un anneau plein."""
    image = _GEARS.get((color, hole))
    if image is None:
        image = _bake_gear(color, hole)
        _GEARS[(color, hole)] = image
    cx, cy = int(center[0]), int(center[1])
    surf.blit(image, (cx - 20, cy - 20))


def _bake_gear(color, hole):
    body_r = 12
    hole_r = 4
    root = 8
    tip = 16
    pixels = {}
    for y in range(-body_r, body_r + 1):
        for x in range(-body_r, body_r + 1):
            if x * x + y * y <= body_r * body_r:
                pixels[(x, y)] = color
    for y in range(-hole_r, hole_r + 1):
        for x in range(-hole_r, hole_r + 1):
            if x * x + y * y <= hole_r * hole_r:
                pixels[(x, y)] = hole
    span = tip - root
    for i in range(6):
        ang = i * math.tau / 6 - math.pi / 2
        ca, sa = math.cos(ang), math.sin(ang)
        for ly in range(root, tip + 1):
            t = (ly - root) / span
            hw = 4.0 - t * 1.4
            lx = -hw
            while lx <= hw + 0.01:
                px = round(ca * ly - sa * lx)
                py = round(sa * ly + ca * lx)
                pixels[(px, py)] = color
                lx += 0.5
    image = pygame.Surface((40, 40))
    image.fill(_GEAR_KEY)
    image.set_colorkey(_GEAR_KEY)
    for (x, y), col in pixels.items():
        image.set_at((20 + x, 20 + y), col)
    if pygame.display.get_surface() is not None:
        image = image.convert()
    return image


def law_button(side):
    if side < 0:
        return pygame.Rect(20, 48, 64, 64)
    return pygame.Rect(W - 84, 48, 64, 64)


# Curseur vertical. Le cran 4 est en haut : le doigt qui monte augmente le niveau.
# La colonne reste étroite : un glissé horizontal, même parti dessus, change de carte.
_NOTCH_BTN = 44
SLIDER_X = 336
SLIDER_TOP = 350
SLIDER_BOT = 478


def slider_y(t):
    t = 0.0 if t < 0 else 4.0 if t > 4 else float(t)
    span = SLIDER_BOT - SLIDER_TOP
    return int(round(SLIDER_BOT - (t / 4.0) * span))


def slider_notch(y):
    span = SLIDER_BOT - SLIDER_TOP
    t = (SLIDER_BOT - float(y)) / float(span) * 4.0
    if t < 0:
        t = 0.0
    elif t > 4:
        t = 4.0
    return int(round(t))


def slider_hit(dx=0):
    """La piste et les cinq valeurs. Le reste de la carte défile à l'horizontale."""
    return pygame.Rect(
        SLIDER_X + int(dx) - 78,
        SLIDER_TOP - 22,
        112,
        SLIDER_BOT - SLIDER_TOP + 44,
    )


def notch_button(side, dx=0):
    """Plus en haut du curseur, moins en bas. Le geste reste vertical."""
    x = SLIDER_X - _NOTCH_BTN // 2 + int(dx)
    if side < 0:
        return pygame.Rect(x, SLIDER_BOT + 14, _NOTCH_BTN, _NOTCH_BTN)
    return pygame.Rect(x, SLIDER_TOP - 14 - _NOTCH_BTN, _NOTCH_BTN, _NOTCH_BTN)


def year_from_plot_x(x, end=YEAR_MAX):
    span = PLOT_RECT.w - 16
    t = (x - (PLOT_RECT.x + 8)) / span
    cap = float(end)
    return min(cap, max(YEAR_MIN, YEAR_MIN + t * (cap - YEAR_MIN)))


def _x_year(year, rect, end=YEAR_MAX, origin=YEAR_MIN):
    cap = float(end)
    start = float(origin)
    span = cap - start
    if span <= 0:
        span = 1.0
    t = (float(year) - start) / span
    return rect.x + 8 + t * (rect.w - 16)


def _y_value(value, scale, rect, inset=_PLOT_INSET):
    # Pas de plafond : au-dessus de l'échelle, la courbe sort du cadre.
    if scale <= 0:
        t = 0.0
    else:
        t = max(0.0, value / scale)
    span = max(1, rect.h - 2 * inset)
    return rect.bottom - inset - t * span


_CURVES = {}


def _curve_points(traj, key, rect, start, end, axis=YEAR_MAX, origin=YEAR_MIN):
    series = traj.column(key)
    scale = SCALES[key]
    cap = float(axis)
    y0 = max(int(origin), int(math.floor(start)))
    y1 = min(int(cap), int(math.ceil(end)))
    ckey = (
        id(series), key, rect.x, rect.y, rect.w, rect.h,
        y0, y1, cap, float(origin), scale,
    )
    hit = _CURVES.get(ckey)
    if hit is not None:
        return hit
    pts = []
    for year in range(y0, y1 + 1):
        i = year - YEAR_MIN
        if i < 0 or i >= len(series):
            continue
        pts.append((
            int(round(_x_year(year, rect, cap, origin))),
            int(round(_y_value(float(series[i]), scale, rect))),
        ))
    if len(_CURVES) > 48:
        _CURVES.clear()
    _CURVES[ckey] = pts
    return pts


def _draw_dashed(surf, pts, color, width, on, off):
    if len(pts) < 2 or on <= 0:
        return
    period = float(on + off)
    traveled = 0.0
    for i in range(len(pts) - 1):
        x0, y0 = float(pts[i][0]), float(pts[i][1])
        x1, y1 = float(pts[i + 1][0]), float(pts[i + 1][1])
        dx, dy = x1 - x0, y1 - y0
        seg = math.hypot(dx, dy)
        if seg < 0.2:
            traveled += seg
            continue
        ux, uy = dx / seg, dy / seg
        pos = 0.0
        while pos < seg - 0.05:
            phase = traveled % period
            if phase < on:
                take = min(on - phase, seg - pos)
                pygame.draw.line(
                    surf,
                    color,
                    (x0 + ux * pos, y0 + uy * pos),
                    (x0 + ux * (pos + take), y0 + uy * (pos + take)),
                    width,
                )
            else:
                take = min(period - phase, seg - pos)
            if take < 0.05:
                take = 0.05
            pos += take
            traveled += take


def _runs_above(pts, y_min):
    """Coupe le trait qui sort par le haut, sans l'aplatir sur le bord."""
    runs = []
    run = []
    prev = None
    for pt in pts:
        x, y = pt
        if prev is None:
            if y >= y_min:
                run.append((x, y))
            prev = pt
            continue
        px, py = prev
        crosses = (py >= y_min) != (y >= y_min)
        if crosses and y != py:
            t = (y_min - py) / float(y - py)
            cut = (int(round(px + (x - px) * t)), y_min)
        else:
            cut = None
        if py >= y_min and y >= y_min:
            run.append((x, y))
        elif py >= y_min:
            if cut is not None:
                run.append(cut)
            if len(run) >= 2:
                runs.append(run)
            run = []
        elif y >= y_min:
            run = []
            if cut is not None:
                run.append(cut)
            run.append((x, y))
        prev = pt
    if len(run) >= 2:
        runs.append(run)
    return runs


def _draw_curve(surf, pts, color, dashed, width=2, dash=(16, 8)):
    if len(pts) < 2:
        return
    # Un trait épais coupé par le bord de l'écran laisse un filet horizontal.
    for run in _runs_above(pts, width):
        if not dashed:
            pygame.draw.lines(surf, color, False, run, width)
        else:
            _draw_dashed(surf, run, color, width, dash[0], dash[1])


def _diff_runs(pts, other, tol=3, bridge=12):
    """Morceaux continus de pts là où l'autre courbe s'écarte.

    Un écart de quelques pixels est le même trait. Un bref retour
    dans cet écart ne coupe pas le gris.
    """
    n = min(len(pts), len(other))
    if n < 2:
        return []
    apart = [abs(pts[i][1] - other[i][1]) >= tol for i in range(n)]
    i = 0
    while i < n:
        if apart[i]:
            i += 1
            continue
        j = i
        while j < n and not apart[j]:
            j += 1
        if i > 0 and j < n and (j - i) <= bridge:
            for k in range(i, j):
                apart[k] = True
        i = j
    runs = []
    run = []
    for i, far in enumerate(apart):
        if far:
            if not run and i > 0:
                run.append(pts[i - 1])
            run.append(pts[i])
        elif run:
            run.append(pts[i])
            if len(run) >= 2:
                runs.append(run)
            run = []
    if len(run) >= 2:
        runs.append(run)
    return runs


def _depart_mark(surf, x, y, color):
    """Chevron de carrés, pointe à droite."""
    cell, gap = 3, 1
    step = cell + gap
    for row, col in enumerate((0, 1, 2, 1, 0)):
        pygame.draw.rect(surf, color, (x + col * step, y + row * step, cell, cell))


def draw_depart_button(surf, font, right, y, year, title, hits, fn, ident, pressed, phase, marks=True):
    """Deux lignes : la date et sa flèche, puis l'appel juste dessous."""
    mark_w, mark_h = 11, 19
    n_marks, mark_gap = 6, 5
    cluster = n_marks * mark_w + (n_marks - 1) * mark_gap if marks else 0
    pad_x, gap = 10, 10
    title_w = font.width(title, 2)
    stamp_w = font.width(year, 3) + 14 if year else 0
    if year:
        head_w = stamp_w + (gap + cluster if marks else 0)
    elif marks:
        head_w = title_w + gap + cluster
    else:
        head_w = title_w
    text_w = max(head_w, title_w if year else head_w)
    block_h = (28 + 6 + font.height(2)) if year else font.height(2)
    width = pad_x + text_w + pad_x
    height = max(64, block_h + 16)
    rect = pygame.Rect(right - width, y, width, height)
    face = rect.move(3, 3) if pressed else pygame.Rect(rect)
    if not pressed:
        pygame.draw.rect(surf, mix(OCHRE, BG, 0.55), rect.move(4, 4))
    pygame.draw.rect(surf, OCHRE, face)
    if not pressed:
        pygame.draw.rect(surf, mix(OCHRE, INK, 0.42), (face.x, face.y, face.w, 3))
        pygame.draw.rect(surf, mix(OCHRE, BG, 0.38), (face.x, face.bottom - 3, face.w, 3))
    text_x = face.x + pad_x
    top = face.y + (face.h - block_h) // 2
    if year:
        stamp = pygame.Rect(text_x, top, stamp_w, 28)
        pygame.draw.rect(surf, BG, stamp)
        font.blit(
            surf, year, stamp.centerx, stamp.centery - font.height(3) // 2,
            3, OCHRE, align="center",
        )
        font.blit(surf, title, text_x, stamp.bottom + 6, 2, BG)
        mark_y = stamp.centery - mark_h // 2
        mark_x = stamp.right + gap
    else:
        font.blit(surf, title, text_x, top, 2, BG)
        mark_y = face.centery - mark_h // 2
        mark_x = text_x + title_w + gap
    if marks:
        lit = int(phase * 3.4) % n_marks
        idle = mix(OCHRE, BG, 0.42)
        for i in range(n_marks):
            _depart_mark(surf, mark_x + i * (mark_w + mark_gap), mark_y, INK if i == lit else idle)
    hits.add(rect, fn, ident)
    return rect


def draw_button(surf, font, rect, label, hits, fn, ident, kind="plain", pressed=False, sub=None, scale=3, enabled=True):
    rect = pygame.Rect(rect)
    face = rect.move(3, 3) if pressed and enabled else pygame.Rect(rect)
    if kind == "invert":
        pygame.draw.rect(surf, INK, face)
        fg = BG
        border = None
    else:
        if enabled and not pressed:
            pygame.draw.rect(surf, LINE, rect.move(4, 4))
        pygame.draw.rect(surf, BG, face)
        if not enabled:
            border = fg = DIM
        elif kind == "rust":
            border = fg = RUST
        elif kind == "on":
            border = fg = OCHRE
        else:
            border = fg = INK
        pygame.draw.rect(surf, border, face, 2)
    if sub:
        font.blit(surf, label, face.centerx, face.y + 18, scale, fg, align="center")
        font.blit(surf, sub, face.centerx, face.bottom - 28, 2, fg if kind == "invert" else MUTED, align="center")
    else:
        font.blit_center(surf, label, face, scale, fg)
    hits.add(rect, fn, ident)


def draw_pips(surf, seals, y, flash):
    size, gap = 14, 6
    n = MAX_SEALS
    total = n * size + (n - 1) * gap
    x = W - 24 - total
    color_on = OCHRE if flash else INK
    for i in range(n):
        rect = pygame.Rect(x + i * (size + gap), y, size, size)
        if i < seals:
            pygame.draw.rect(surf, color_on, rect)
        else:
            pygame.draw.rect(surf, DIM, rect, 2)
    return x


def draw_tokens(surf, font, seals, y, flash):
    left = draw_pips(surf, seals, y, flash)
    label = token_label(seals)
    width = font.width(label, 2)
    text_y = y + 1
    plate = pygame.Rect(left - 16 - width, text_y - 3, width + 12, font.height(2) + 6)
    pygame.draw.rect(surf, BG, plate)
    font.blit(surf, label, left - 10, text_y, 2, INK, align="right")
    return left


def draw_nav(surf, font, screen, hits, goto, pressed):
    pygame.draw.rect(surf, LINE, (0, NAV_Y, W, 2))
    for (sid, label), rect in zip(TABS, nav_rects()):
        on = sid == screen
        if on:
            pygame.draw.rect(surf, INK, rect)
        if sid == "temps":
            gear = BG if on else MUTED
            hole = INK if on else BG
            draw_gear(surf, rect.center, gear, hole)
        elif on:
            font.blit_center(surf, label, rect, 2, BG)
        else:
            font.blit_center(surf, label, rect, 2, MUTED)
        hits.add(rect, lambda s=sid: goto(s), sid)


def draw_status(surf, font, state, seal_flash):
    font.blit(surf, str(int(state.year)), 24, 14, 2, INK)
    draw_tokens(surf, font, state.seals, 16, seal_flash)


def _star_hash(i):
    n = (i + 1) * 747796405 & 0xFFFFFFFF
    n ^= n >> 16
    n = n * 0x7FEB352D & 0xFFFFFFFF
    n ^= n >> 15
    return n


_STAR_CACHE = {"key": None, "rle": None, "scratch": None, "pending": None}
_STAR_KEY = (255, 0, 255)


def _star_scratch():
    scratch = _STAR_CACHE["scratch"]
    if scratch is not None:
        return scratch
    scratch = pygame.Surface((W, H))
    scratch.fill(_STAR_KEY)
    if pygame.display.get_surface() is not None:
        scratch = scratch.convert()
    scratch.set_colorkey(_STAR_KEY)
    _STAR_CACHE["scratch"] = scratch
    return scratch


def _stars(surf, yaw, center):
    # Le décalage de chaque étoile ne prend que cinq crans. Pendant le tour
    # d'une année il change presque à chaque image : reconstruire alors un
    # calque compressé bloquait l'image. On ne le compresse qu'une fois le
    # ciel stabilisé.
    shifts = tuple(int(math.sin(yaw * 0.35 + p) * 2) for p in range(8))
    key = (shifts, center)
    rle = _STAR_CACHE["rle"]
    if key == _STAR_CACHE["key"] and rle is not None:
        surf.blit(rle, (0, 0))
        return
    if key == _STAR_CACHE["pending"]:
        # Deuxième image identique : on fige le ciel, les suivantes ne font qu'un blit.
        layer = _star_scratch()
        layer.fill(_STAR_KEY)
        _paint_stars(layer, yaw, center)
        promoted = layer.copy()
        if pygame.display.get_surface() is not None:
            promoted = promoted.convert()
        promoted.set_colorkey(_STAR_KEY, pygame.RLEACCEL)
        _STAR_CACHE["rle"] = promoted
        _STAR_CACHE["key"] = key
        _STAR_CACHE["pending"] = None
        surf.blit(promoted, (0, 0))
        return
    # Le motif change (la Terre tourne vite) : des carrés, pas un calque plein écran.
    _paint_stars(surf, yaw, center)
    _STAR_CACHE["pending"] = key
    _STAR_CACHE["key"] = key
    _STAR_CACHE["rle"] = None


def _paint_stars(surf, yaw, center):
    # Graine fixe : le ciel ne change pas d'une frame a l'autre.
    # Positions et tailles melangees, au-dela de l'anneau.
    near = RING_R + 56
    sizes = (2, 2, 2, 3, 3, 3, 4, 4, 5, 7)
    cx, cy = center
    top = 10
    span = NAV_Y - 20
    n = 176
    for i in range(n):
        h = _star_hash(i)
        x = 10 + (h % (W - 20))
        y = top + ((h >> 10) % span)
        _star_dot(surf, yaw, cx, cy, near, sizes, h, x, y)
    # Bande sous l'ancienne nav : visible quand la Terre tourne sans barre.
    low = top + span
    room = H - 10 - low
    extra = max(1, int(round(n * room / span)))
    for j in range(extra):
        i = n + j
        h = _star_hash(i)
        x = 10 + (h % (W - 20))
        y = low + ((h >> 10) % room)
        _star_dot(surf, yaw, cx, cy, near, sizes, h, x, y)


def _star_dot(surf, yaw, cx, cy, near, sizes, h, x, y):
    dx = x - cx
    dy = y - cy
    if dx * dx + dy * dy < near * near:
        return
    if y < 58 and x > 430:
        return
    shift = int(math.sin(yaw * 0.35 + (h & 7)) * 2)
    size = sizes[(h >> 20) % len(sizes)]
    if size <= 3:
        color = DIM
    elif size == 4:
        color = MUTED
    else:
        color = INK
    pygame.draw.rect(surf, color, (x + shift - size // 2, y - size // 2, size, size))


def _ring(surf, frac, color, wake=None, center=PLANET_C):
    """Anneau des années. wake : fraction déjà atteinte avant ce tour.

    Les points entre wake et frac sont ceux qui s'allument.
    """
    steps = 80
    cx, cy = center
    lead = -1
    if wake is not None:
        for i in range(steps):
            if wake <= (i / steps) < frac:
                lead = i
    for i in range(steps):
        a = -math.pi / 2 + (i + 0.5) / steps * math.tau
        x = cx + math.cos(a) * RING_R
        y = cy + math.sin(a) * RING_R
        t = i / steps
        if t >= frac:
            ink = DIM
            size = 4
        elif wake is not None and t >= wake:
            ink = OCHRE
            size = 6 if i == lead else 4
        else:
            ink = color
            size = 4
        half = size // 2
        pygame.draw.rect(surf, ink, (int(x) - half, int(y) - half, size, size))


# Limbe du globe en pixels (rayon de la carte, puis agrandi x4).
_LIMB = (40 - 1.6) * 4
# Le degradé s'eteint sur l'anneau des annees (points de 4 px).
_ATMO_OUTER = RING_R + 2
# Meme grain que le globe : des carres de 4, alignes sur sa grille.
_PIXEL = 4
_PAD = 10
_CELLS = 80 + 2 * _PAD
_ATMO_SIDE = _CELLS * _PIXEL
_atmo_cache = {"key": None, "surf": None}


def _air_color(t):
    """Air clair, puis ocre, puis rouille. t va de 0 a 1 avec la pollution.

    La teinte est plus saturee que le liseré vu a l'ecran : l'alpha
    la lave sur le fond noir.
    """
    sky = (72, 176, 196)
    if t < 0.45:
        return mix(sky, OCHRE, t / 0.45)
    return mix(OCHRE, RUST, (t - 0.45) / 0.55)


_ATMO_GEOM = None


def _atmo_geom():
    """Rayon et fondu du halo. Ils ne dépendent pas de la pollution."""
    global _ATMO_GEOM
    if _ATMO_GEOM is not None:
        return _ATMO_GEOM
    coords = ((np.arange(_CELLS) + 0.5) * _PIXEL - (_ATMO_SIDE / 2.0)).astype(np.float32)
    radius = np.hypot(coords[:, None], coords[None, :]).astype(np.float32)
    gap = radius - np.float32(_LIMB - 2.0)
    fade = np.clip((_ATMO_OUTER - radius) / np.float32(6.0), 0.0, 1.0).astype(np.float32)
    inside = (gap >= 0.0) & (radius <= _ATMO_OUTER)
    sheen = np.clip(np.float32(1.0) - gap / np.float32(6.0), 0.0, 1.0).astype(np.float32)
    _ATMO_GEOM = (gap, fade, inside, sheen)
    return _ATMO_GEOM


def _atmosphere_surface(ppolx):
    t = float(np.clip(ppolx / 16.0, 0.0, 1.0))
    # Douze teintes suffisent. L'ancien pas en reconstruisait une à chaque année.
    key = round(t * 12.0)
    if key == _atmo_cache["key"] and _atmo_cache["surf"] is not None:
        return _atmo_cache["surf"]

    gap, fade, inside, sheen_base = _atmo_geom()
    tt = key / 12.0
    sigma = np.float32((7.0 + 12.0 * tt) * 1.5)
    peak = np.float32(0.42 + 0.28 * tt)
    alpha = np.exp(-np.clip(gap, 0.0, None) / sigma) * peak
    alpha = np.where(inside, alpha * fade, np.float32(0.0))
    alpha = np.round(alpha * np.float32(8.0)) / np.float32(16.0)
    sheen = np.round(sheen_base * np.float32(0.28 * (1.0 - 0.45 * tt)) * np.float32(4.0)) / np.float32(4.0)
    base = np.array(_air_color(tt), dtype=np.float32)
    light = base * np.float32(0.7) + np.array((198.0, 228.0, 226.0), np.float32) * np.float32(0.3)
    rgb = base * (np.float32(1.0) - sheen[..., None]) + light * sheen[..., None]
    rgb = np.clip(rgb, 0, 255).astype(np.uint8)
    band = np.clip(alpha * np.float32(255.0), 0, 255).astype(np.uint8)
    # Posé sur le fond, au grain du globe, puis agrandi. Pas de fondu plein cadre.
    cell = np.empty((_CELLS, _CELLS, 3), np.uint8)
    cell[...] = (255, 0, 255)
    visible = band > 8
    cover = (band.astype(np.float32) / np.float32(255.0))[..., None]
    flat = np.array(BG, np.float32) * (np.float32(1.0) - cover) + rgb.astype(np.float32) * cover
    cell[visible] = np.clip(flat[visible], 0, 255).astype(np.uint8)
    big = np.repeat(np.repeat(cell, _PIXEL, axis=0), _PIXEL, axis=1)
    ordered = np.ascontiguousarray(np.transpose(big, (1, 0, 2)))
    layer = _atmo_cache["surf"]
    if layer is None:
        layer = pygame.Surface((_ATMO_SIDE, _ATMO_SIDE))
        if pygame.display.get_surface() is not None:
            layer = layer.convert()
        layer.set_colorkey((255, 0, 255))
        _atmo_cache["surf"] = layer
    pygame.surfarray.blit_array(layer, ordered)
    layer.set_colorkey((255, 0, 255), pygame.RLEACCEL)
    _atmo_cache["key"] = key
    return layer


def _atmosphere(surf, ppolx, center):
    layer = _atmosphere_surface(ppolx)
    surf.blit(
        layer,
        (center[0] - layer.get_width() // 2, center[1] - layer.get_height() // 2),
    )


def _vital_text(key, value):
    text = format_vital(key, value)
    unit = UNITS[key]
    if unit == "%":
        return f"{text}%"
    if unit:
        return f"{text} {unit}"
    return text


def _vital_parts(key, value):
    return format_vital(key, value), UNITS[key]


def draw_icon_button(surf, rect, kind, hits, fn, ident, pressed=False):
    rect = pygame.Rect(rect)
    face = rect.move(2, 2) if pressed else pygame.Rect(rect)
    if not pressed:
        pygame.draw.rect(surf, DIM, rect.move(4, 4))
    pygame.draw.rect(surf, BG, face)
    pygame.draw.rect(surf, INK, face, 2)
    cx, cy = face.centerx, face.centery
    if kind == "pause":
        pygame.draw.rect(surf, INK, (cx - 7, cy - 6, 4, 12))
        pygame.draw.rect(surf, INK, (cx + 3, cy - 6, 4, 12))
    elif kind == "play":
        pygame.draw.polygon(surf, INK, ((cx - 5, cy - 7), (cx - 5, cy + 7), (cx + 8, cy)))
    elif kind == "close":
        pygame.draw.line(surf, INK, (cx - 8, cy - 8), (cx + 8, cy + 8), 3)
        pygame.draw.line(surf, INK, (cx + 8, cy - 8), (cx - 8, cy + 8), 3)
    elif kind == "gear":
        draw_gear(surf, (cx, cy), INK, BG)
    else:
        pygame.draw.circle(surf, INK, (cx, cy), 14, 2)
        pygame.draw.rect(surf, INK, (cx - 2, cy - 8, 4, 4))
        pygame.draw.rect(surf, INK, (cx - 2, cy - 1, 4, 9))
    hits.add(corner_hit(rect), fn, ident)


_PAGE_PAD_X = 14


def draw_page_button(surf, font, rect, label, hits, fn, ident, pressed=False):
    """Pastille ocre : le mot seul, hauteur alignée sur le bouton réglages."""
    rect = pygame.Rect(rect)
    face = rect.move(3, 3) if pressed else pygame.Rect(rect)
    if not pressed:
        pygame.draw.rect(surf, mix(OCHRE, BG, 0.55), rect.move(4, 4))
    pygame.draw.rect(surf, OCHRE, face)
    scale = 3
    font.blit(
        surf, label, face.centerx, face.centery - font.height(scale) // 2,
        scale, BG, align="center",
    )
    hits.add(rect, fn, ident)


def _gear_rect():
    return pygame.Rect(W - 20 - _ICON, 16, _ICON, _ICON)


_INFO_R = 14
_INFO_GAP = 20


def _info_ring(phase, pressed):
    """Le trait s'éteint un peu, puis revient. Environ deux secondes."""
    if pressed:
        return INK
    wave = 0.5 + 0.5 * math.sin(phase * 4.8)
    return mix(DIM, INK, 0.2 + 0.8 * wave)


def draw_info_mark(surf, cx, cy, hits, fn, ident, pressed=False, pulse=0.0):
    """Le i dans un carré. Le contour clignote."""
    shift = 2 if pressed else 0
    x, y = int(cx) + shift, int(cy) + shift
    box = pygame.Rect(x - _INFO_R, y - _INFO_R, _INFO_R * 2, _INFO_R * 2)
    pygame.draw.rect(surf, BG, box)
    pygame.draw.rect(surf, _info_ring(pulse, pressed), box, 2)
    pygame.draw.rect(surf, INK, (x - 2, y - 8, 4, 4))
    pygame.draw.rect(surf, INK, (x - 2, y - 1, 4, 9))
    rect = pygame.Rect(0, 0, _INFO_R * 2 + 8, _INFO_R * 2 + 8)
    rect.center = (int(cx), int(cy))
    hits.add(rect, fn, ident)


def draw_title_with_info(
    surf, font, title, x, y, color, hits, fn, ident, pressed,
    align="left", room=None, pulse=0.0,
):
    """Le titre, et le i juste à sa droite. Centré, le couple reste dans la bande."""
    mark = _INFO_GAP + _INFO_R * 2
    scale = 4 if room is None or font.width(title, 4) + mark <= room else 3
    text_w = font.width(title, scale)
    text_x = x - (text_w + mark) // 2 if align == "center" else x
    font.blit(surf, title, text_x, y, scale, color)
    cx = text_x + text_w + _INFO_GAP + _INFO_R
    cy = y + font.height(scale) // 2
    draw_info_mark(surf, cx, cy, hits, fn, ident, pressed, pulse)


def _gear_corner(surf, hits, app):
    draw_icon_button(
        surf, _gear_rect(), "gear", hits, app.open_settings, "reglages",
        pressed=app.pressed == "reglages",
    )


def _page_corner(surf, font, hits, app, label, fn, ident):
    gear = _gear_rect()
    text_w = font.width(label, 3)
    width = _PAGE_PAD_X + text_w + _PAGE_PAD_X
    button = pygame.Rect(gear.x - 12 - width, gear.y, width, _ICON)
    draw_page_button(
        surf, font, button, label, hits, fn, ident,
        pressed=app.pressed == ident,
    )


def draw_vitals(surf, font, sample, y, bottom=None):
    # Cinq colonnes egales. Le filet et le titre prennent la couleur de la courbe.
    # Le chiffre garde la couleur de son etat.
    n = len(VITALS)
    col = W // n
    if bottom is None:
        bottom = NAV_Y
    pygame.draw.rect(surf, BG, (0, y - 8, W, max(0, bottom - (y - 8))))
    for i, (key, _chip, lines) in enumerate(VITALS):
        left = i * col
        cx = left + col // 2
        color = SERIES_COLOR[key]
        pygame.draw.rect(surf, color, (left + 18, y, col - 36, 2))
        for row, line in enumerate(lines):
            font.blit(surf, line, cx, y + 8 + row * 10, 1, color, align="center")
        font.blit(
            surf,
            _vital_text(key, sample[key]),
            cx,
            y + 32,
            2,
            tone_color(vital_tone(key, sample[key])),
            align="center",
        )


def draw_monde_vitals(surf, font, sample, top, bottom):
    # Cinq cartes. Le chiffre est grand, la couleur est celle de la courbe.
    # Quand la bande se replie, le titre reste en haut et la barre en bas :
    # les valeurs, entre les deux, disparaissent.
    span = max(0, bottom - top)
    pygame.draw.rect(surf, BG, (0, top, W, span))
    pygame.draw.rect(surf, LINE, (0, top, W, 2))
    n = len(VITALS)
    col = W // n
    for i, (key, name, _lines) in enumerate(VITALS):
        left = i * col
        color = SERIES_COLOR[key]
        tone = tone_color(vital_tone(key, sample[key]))
        body = pygame.Rect(left + 3, top + 6, col - 6, max(0, span - 10))
        pygame.draw.rect(surf, mix(BG, color, 0.22), body)
        pygame.draw.rect(surf, color, (body.x, body.y, body.w, 4))
        number, unit = _vital_parts(key, sample[key])
        cx = body.centerx
        font.blit(surf, name, cx, body.y + 12, 2, color, align="center")
        bar_y = body.bottom - 16
        # Le chiffre n'entre que s'il tient entier, pour ne pas couper un glyphe.
        room = bar_y - 4
        num_scale = 4 if font.width(number, 4) <= body.w - 8 else 3
        number_y = body.y + 32
        if number_y + font.height(num_scale) <= room:
            font.blit(surf, number, cx, number_y, num_scale, tone, align="center")
        if unit:
            unit_y = body.y + 66
            if unit_y + font.height(2) <= room:
                font.blit(surf, unit, cx, unit_y, 2, MUTED, align="center")
        scale = SCALES[key]
        frac = 0.0 if scale <= 0 else max(0.0, min(1.0, sample[key] / scale))
        bar_w = body.w - 16
        bar_x = body.x + 8
        pygame.draw.rect(surf, mix(BG, color, 0.48), (bar_x, bar_y, bar_w, 8))
        fill = int(round(frac * bar_w))
        if frac > 0.0 and fill < 2:
            fill = 2
        if fill:
            pygame.draw.rect(surf, color, (bar_x, bar_y, min(fill, bar_w), 8))


def _sat_orbit(i):
    """Rayon, inclinaison, noeud, vitesse, decalage. Fixes pour un indice.

    La plupart entourent l'anneau. Une sur quatre est plus plate :
    son petit axe traverse le disque, le cote proche passant devant.
    """
    h = _star_hash(i + 91)
    radius = 268 + (h % 84)
    if i % 4 == 0:
        close = 44 + (h % 78)
        inc = math.acos(min(0.9, close / float(radius)))
    else:
        clear = RING_R + 28
        limit = math.acos(min(0.97, clear / float(radius)))
        span = max(0.08, limit - 0.16)
        inc = 0.16 + ((h >> 7) % 100) / 100.0 * span
    node = ((h >> 14) % 1000) / 1000.0 * math.tau
    # Tous dans le meme sens : l'ancien tour, horaire a l'ecran. La vitesse seule varie.
    speed = 0.32 + ((h >> 3) % 60) / 100.0
    offset = ((h >> 17) % 1000) / 1000.0 * math.tau
    return radius, inc, node, speed, offset


def _draw_satellite(surf, x, y, far=False):
    # Corps clair, deux ailes bleues coupees en cellules.
    # Le cote lointain reste en aplat, plus sombre.
    ix, iy = int(x), int(y)
    body = pygame.Rect(ix - 3, iy - 3, 6, 6)
    panel = mix(SEA, BG, 0.55) if far else mix(SEA, GLASS, 0.35)
    ink = DIM if far else INK
    for side in (-1, 1):
        wing = pygame.Rect(0, 0, 10, 4)
        wing.centery = iy
        if side < 0:
            wing.right = body.left - 2
        else:
            wing.left = body.right + 2
        pygame.draw.rect(surf, panel, (wing.x, wing.y, 4, 4))
        pygame.draw.rect(surf, panel, (wing.x + 6, wing.y, 4, 4))
    pygame.draw.rect(surf, ink, body)


def _satellite_places(count, phase, yaw, pitch, center):
    """Positions ecran. Le geste (sat_yaw, pitch) tourne les orbites comme la carte."""
    cp, sp = math.cos(pitch), math.sin(pitch)
    cyaw, syaw = math.cos(yaw), math.sin(yaw)
    cx, cy = center
    places = []
    for i in range(count):
        radius, inc, node, speed, offset = _sat_orbit(i)
        theta = phase * speed + offset
        ct, st = math.cos(theta), math.sin(theta)
        ci, si = math.cos(inc), math.sin(inc)
        cn, sn = math.cos(node), math.sin(node)
        # Cercle face a l'ecran. v negatif : le tour est horaire, comme avant.
        u = radius * ct
        v = -radius * st * ci
        w = radius * st * si
        x = u * cn - v * sn
        y = u * sn + v * cn
        z = w
        # Yaw autour de la verticale : la face part a gauche quand le yaw grandit, comme la carte.
        x1 = x * cyaw - z * syaw
        z1 = x * syaw + z * cyaw
        # Pitch inverse du releve de la carte : la face monte quand le pitch grandit.
        y2 = y * cp + z1 * sp
        z2 = -y * sp + z1 * cp
        places.append((cx + x1, cy - y2, z2 >= 0))
    return places


def _paint_satellites(surf, places, near, bottom=NAV_Y):
    # La barre des chiffres masque le bas. Sur les reglages, bottom vaut H.
    bar = pygame.Rect(0, bottom, W, max(0, H - bottom))
    for x, y, front in places:
        if front != near:
            continue
        box = pygame.Rect(int(x) - 15, int(y) - 4, 30, 8)
        if bar.h and box.colliderect(bar):
            continue
        if box.right < 0 or box.left > W or box.bottom < 0 or box.top > bottom:
            continue
        _draw_satellite(surf, x, y, far=not front)


# Orbite basse, inclinee comme la vraie station (51,6 deg).
# Plus pres et plus vite que l'anneau des autres satellites.
_ISS_R = 236.0
_ISS_INC = math.radians(51.6)
_ISS_NODE = 0.62
_ISS_SPEED = 0.85
_ISS_OFF = 1.1


def _iss_xyz(theta):
    ct, st = math.cos(theta), math.sin(theta)
    ci, si = math.cos(_ISS_INC), math.sin(_ISS_INC)
    cn, sn = math.cos(_ISS_NODE), math.sin(_ISS_NODE)
    u = _ISS_R * ct
    v = -_ISS_R * st * ci
    w = _ISS_R * st * si
    return (u * cn - v * sn, u * sn + v * cn, w)


def _vadd(a, b, s=1.0):
    return (a[0] + b[0] * s, a[1] + b[1] * s, a[2] + b[2] * s)


def _vnorm(v):
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
    return (v[0] / n, v[1] / n, v[2] / n)


def _vcross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _cam(x, y, z, yaw, pitch):
    """Meme rotation que les orbites. z2 positif : vers l'ecran."""
    cyaw, syaw = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    x1 = x * cyaw - z * syaw
    z1 = x * syaw + z * cyaw
    y2 = y * cp + z1 * sp
    z2 = -y * sp + z1 * cp
    return x1, -y2, z2


_ISS_GRAIN = 4


def _iss_brick(bag, x, y, z, order, color, n=1):
    """Un ou plusieurs carrés de 4, collés sur la grille du globe."""
    half = n * _ISS_GRAIN / 2.0
    gx = int(round((x - half) / _ISS_GRAIN))
    gy = int(round((y - half) / _ISS_GRAIN))
    for ix in range(n):
        for iy in range(n):
            key = (gx + ix, gy + iy)
            prev = bag.get(key)
            if prev is None or (order, z) >= (prev[0], prev[1]):
                bag[key] = (order, z, color)


# Mast, panneau clair, panneau sombre, aileron, corps.
_ISS_MAST, _ISS_PANEL, _ISS_SHADE, _ISS_FIN, _ISS_BODY = range(5)
_ISS_POSE = {"key": None, "front": False, "lit": False, "cells": ()}


def _iss_pose(phase, yaw, pitch, center):
    """Geometrie de la station, une fois par image. Le cote proche et le cote loin la reutilisent."""
    key = (phase, yaw, pitch, center)
    if _ISS_POSE["key"] == key:
        return _ISS_POSE["front"], _ISS_POSE["lit"], _ISS_POSE["cells"]
    theta = phase * _ISS_SPEED + _ISS_OFF
    origin = _iss_xyz(theta)
    ahead = _iss_xyz(theta + 0.05)
    along = _vnorm(_vadd(ahead, origin, -1.0))
    radial = _vnorm(origin)
    port = _vnorm(_vcross(radial, along))
    tilt = 0.95
    ca, sa = math.cos(tilt), math.sin(tilt)
    hinge = _vadd(_vadd((0.0, 0.0, 0.0), radial, ca), along, sa)
    lit = abs(_cam(*_vnorm(_vcross(port, hinge)), yaw, pitch)[2]) >= 0.4
    front = _cam(*origin, yaw, pitch)[2] >= 0

    def at(p_amt, h_amt, a_amt):
        point = _vadd(_vadd(_vadd(origin, port, p_amt), hinge, h_amt), along, a_amt)
        x, y, z = _cam(*point, yaw, pitch)
        return center[0] + x, center[1] + y, z

    bag = {}

    def put(p_amt, h_amt, a_amt, role, order, n=1):
        x, y, z = at(p_amt, h_amt, a_amt)
        _iss_brick(bag, x, y, z, order, role, n)

    for side in (-1, 1):
        for col in range(4):
            p_amt = side * (14 + col * 8)
            put(p_amt, 0.0, 0.0, _ISS_MAST, 2)
            for sign in (-1, 1):
                for row in range(2):
                    role = _ISS_PANEL if (col + row) % 2 == 0 else _ISS_SHADE
                    put(p_amt, sign * (6 + row * 8), 0.0, role, 1)
        for row in range(2):
            put(side * 8, 0.0, (row - 0.5) * 8, _ISS_FIN, 2)
    for a_amt, n in ((-10, 1), (0, 2), (10, 1)):
        put(0.0, 2.0, a_amt, _ISS_BODY, 3, n)
    cells = []
    for (gx, gy), (order, z, role) in bag.items():
        cells.append((z, order, gx * _ISS_GRAIN + 2, gy * _ISS_GRAIN + 2, _ISS_GRAIN, role))
    cells.sort()
    _ISS_POSE["key"] = key
    _ISS_POSE["front"] = front
    _ISS_POSE["lit"] = lit
    _ISS_POSE["cells"] = cells
    return front, lit, cells


def _iss_colors(far, lit):
    if far:
        panel = mix(SEA, BG, 0.62)
        shade = mix(SEA, BG, 0.78)
        fin = mix(DIM, BG, 0.35)
    elif lit:
        panel = mix(SEA, GLASS, 0.4)
        shade = SEA
        fin = mix(ICE, GLASS, 0.2)
    else:
        panel = mix(SEA, BG, 0.28)
        shade = mix(SEA, BG, 0.5)
        fin = DIM
    return (
        DIM if far else INK,
        panel,
        shade,
        fin,
        DIM if far else ICE,
    )


def _iss_stamps(phase, yaw, pitch, center, far):
    """Carrés de 4, posés selon l'orbite. La perspective les rapproche ou les écarte."""
    front, lit, cells = _iss_pose(phase, yaw, pitch, center)
    colors = _iss_colors(far, lit)
    stamps = [
        (z, order, x, y, size, colors[role])
        for z, order, x, y, size, role in cells
    ]
    return front, stamps


def _paint_iss(surf, app, year, near, bottom, center):
    if not iss_visible(app.state.shocks, year):
        return
    front, stamps = _iss_stamps(
        app.beat, app.view_sat_yaw(), app.view_pitch(), center, far=not near,
    )
    if front != near or not stamps:
        return
    for _z, _order, x, y, size, color in stamps:
        ix = int(round(x - size / 2))
        iy = int(round(y - size / 2))
        if ix + size < 0 or ix > W or iy + size < 0 or iy > bottom:
            continue
        pygame.draw.rect(surf, color, (ix, iy, size, size))


def _rocket_cell(surf, x, y, grain, bottom, color):
    """Un carré accroché à la grille, coupé par la barre du bas."""
    ix = int(round(x / grain)) * grain
    iy = int(round(y / grain)) * grain
    if ix < 0 or iy < 0 or ix + grain > W or iy + grain > bottom:
        return
    pygame.draw.rect(surf, color, (ix, iy, grain, grain))


def _paint_rockets(surf, app, center, bottom):
    """Décollage. Fusée large, fumée au sol, trajectoire qui courbe."""
    if getattr(app, "overlay", None) == "title":
        return
    rockets = getattr(app, "rockets", ())
    if not rockets:
        return
    cx, cy = center
    grain = 4
    # Silhouette locale : avant = -forward, côté = side. Deux fois plus large.
    body = (
        (0, 0, ICE),
        (1, 0, ICE),
        (2, -1, INK),
        (2, 0, INK),
        (2, 1, INK),
        (3, -1, INK),
        (3, 0, GLASS),
        (3, 1, INK),
        (4, -1, INK),
        (4, 0, INK),
        (4, 1, INK),
        (5, -2, MUTED),
        (5, -1, INK),
        (5, 0, INK),
        (5, 1, INK),
        (5, 2, MUTED),
    )
    for rocket in rockets:
        t = rocket["t"]
        # Court temps au sol, puis accélération franche.
        pad = 0.1
        lift = 0.0 if t <= pad else (t - pad) / (1.0 - pad)
        u = lift * lift * (3.0 - 2.0 * lift)
        climb = u * u * (1.15 - 0.15 * u)
        ang0 = rocket["ang"]
        bend = rocket.get("bend", 0.0)
        # Virage après le décollage, comme une vraie poussée.
        turn = max(0.0, climb - 0.12) ** 1.35 * bend
        ang = ang0 + turn
        c, s = math.cos(ang), math.sin(ang)
        px, py = -s, c
        # Arc : le rayon suit l'angle tourné, un peu plus loin qu'avant.
        radius = PLANET_R - 2 + climb * 138
        seed = rocket.get("seed", 1)

        # Fumée au sol : large au décollage, elle s'étale puis s'efface.
        smoke = max(0.0, 1.0 - climb * 2.4)
        if smoke > 0.02:
            base = PLANET_R - 4
            bx = cx + math.cos(ang0) * base
            by = cy + math.sin(ang0) * base
            tx, ty = -math.sin(ang0), math.cos(ang0)
            for i in range(14):
                h = (seed * 1103515245 + i * 12345) & 0x7FFFFFFF
                side = ((h % 200) / 100.0 - 1.0) * (10 + climb * 38)
                out = (h % 17) * 0.35 + climb * (8 + (h % 11))
                age = ((h >> 8) % 100) / 100.0
                fade = smoke * (1.0 - age * 0.55)
                if fade < 0.08:
                    continue
                sx = bx + math.cos(ang0) * out + tx * side
                sy = by + math.sin(ang0) * out + ty * side
                if fade > 0.55:
                    col = mix(MUTED, ICE, 0.35)
                elif fade > 0.28:
                    col = mix(DIM, MUTED, 0.45)
                else:
                    col = mix(BG, DIM, 0.55)
                _rocket_cell(surf, sx, sy, grain, bottom, col)
                if fade > 0.4 and (h & 3) == 0:
                    _rocket_cell(surf, sx + tx * grain, sy + ty * grain, grain, bottom, col)

        # Trainée de flammes derrière la fusée pendant la montée.
        if 0.02 < climb < 0.92:
            flicker = 0.5 + 0.5 * math.sin(t * 28.0 + seed * 0.01)
            for k, col in ((1.0, OCHRE), (1.7, RUST), (2.4, mix(RUST, BG, 0.35))):
                back = 8 * k + flicker * 3
                fx = cx + c * (radius - back) + px * ((k - 1.5) * 2)
                fy = cy + s * (radius - back) + py * ((k - 1.5) * 2)
                _rocket_cell(surf, fx, fy, grain, bottom, col)

        # Corps de la fusée, orienté selon la trajectoire.
        if climb >= 0.98:
            continue
        step = grain
        for back, side, color in body:
            dist = radius - back * step
            if dist < PLANET_R - 20:
                continue
            x = cx + c * dist + px * side * step
            y = cy + s * dist + py * side * step
            _rocket_cell(surf, x, y, grain, bottom, color)
        # Flamme du moteur une fois en l'air (au sol, la fumée suffit).
        if 0.06 < climb < 0.85:
            pulse = 1 + int((math.sin(t * 36.0 + seed) + 1) * 0.5)
            for back, side, color in (
                (6, 0, OCHRE),
                (7, 0, RUST),
                (7, -1, RUST),
                (7, 1, RUST),
                (8 + pulse, 0, mix(RUST, OCHRE, 0.4)),
            ):
                dist = radius - back * step
                if dist < PLANET_R - 12:
                    continue
                x = cx + c * dist + px * side * step
                y = cy + s * dist + py * side * step
                _rocket_cell(surf, x, y, grain, bottom, color)


def _horizon_frac(year, horizon=YEAR_MAX):
    span = float(horizon) - START_YEAR
    if span <= 0:
        return 1.0
    return max(0.0, min(1.0, (year - START_YEAR) / span))


# La barre ouverte mesure 120 px, fermée 60. Le globe reste au milieu.
_STATS_LIFT = 60
_STATS_TOP = 600


def planet_center(app):
    """Centre du globe. Il ne suit pas l'ouverture de la barre."""
    return PLANET_C


def _stats_drop(app):
    """Descente des infos et du bouton quand la barre se ferme."""
    if getattr(app, "overlay", None) is not None:
        return 0
    return int(round(_STATS_LIFT * (1.0 - app.stats_t)))


def _paint_globe(surf, app, year, bottom=NAV_Y, center=None, orbitals=True):
    """Satellites du fond, atmosphere, puis la terre. Les proches se dessinent a part."""
    if center is None:
        center = planet_center(app)
    state = app.state
    sample = app.traj().sample(year)
    places = ()
    if orbitals:
        places = _satellite_places(
            satellite_count(state.notches), app.beat,
            app.view_sat_yaw(), app.view_pitch(), center,
        )
        _paint_satellites(surf, places, False, bottom)
        _paint_iss(surf, app, year, False, bottom, center)
    _atmosphere(surf, sample["ppolx"], center)
    planet = app.planet.render(app.view_yaw(), app.view_pitch(), sample, app.beat)
    surf.blit(planet, (center[0] - planet.get_width() // 2, center[1] - planet.get_height() // 2))
    return sample, places


def _draw_earth(surf, app, year, bottom=None, orbitals=True):
    state = app.state
    horizon = state.horizon
    center = planet_center(app)
    if bottom is None:
        bottom = H
    _stars(surf, app.view_yaw(), center)
    # Pendant le défilement, la teinte du globe change une fois par année,
    # pas à chaque image : la reconstruire coûtait plusieurs dixièmes.
    look = float(math.floor(year)) if app.turn_anim is not None else year
    sample, places = _paint_globe(surf, app, look, bottom, center, orbitals=orbitals)
    wake = _horizon_frac(app.turn_anim[0], horizon) if app.turn_anim else None
    # Le flash d'arrivée est pour l'année du monde. Sur une intro, il
    # colorait d'un coup tous les points déjà comptés.
    arrived = app.year_flash > 0 and app.overlay != "title"
    ring_color = INK if wake is not None else (OCHRE if arrived else INK)
    _ring(surf, _horizon_frac(year, horizon), ring_color, wake, center)
    if orbitals:
        _paint_satellites(surf, places, True, bottom)
        _paint_iss(surf, app, year, True, bottom, center)
        _paint_rockets(surf, app, center, bottom)
    return sample


_VEIL = {"key": None, "surf": None}


def _veiled_planet(planet):
    """Le disque à moitié posé sur le fond. Pas un fondu de tout l'écran."""
    sheet = planet.frame
    key = planet.frame_key
    if key is not None and key == _VEIL["key"] and _VEIL["surf"] is not None:
        return _VEIL["surf"]
    dest = _VEIL["surf"]
    if dest is None or dest.get_size() != sheet.get_size():
        dest = pygame.Surface(sheet.get_size())
        if pygame.display.get_surface() is not None:
            dest = dest.convert()
        _VEIL["surf"] = dest
    dest.fill(BG)
    sheet.set_alpha(128)
    try:
        dest.blit(sheet, (0, 0))
    finally:
        sheet.set_alpha(None)
    dest.set_colorkey(BG)
    _VEIL["key"] = key
    return dest


def _blit_fond_reglages(surf, app, year):
    """Terre voilée. Les étoiles restent nettes, comme sur les intros."""
    center = planet_center(app)
    _stars(surf, app.view_yaw(), center)
    state = app.state
    sample = app.traj().sample(year)
    places = _satellite_places(
        satellite_count(state.notches), app.beat,
        app.view_sat_yaw(), app.view_pitch(), center,
    )
    _paint_satellites(surf, places, False, H)
    _paint_iss(surf, app, year, False, H, center)
    app.planet.render(app.view_yaw(), app.view_pitch(), sample, app.beat)
    planet = _veiled_planet(app.planet)
    surf.blit(planet, (center[0] - planet.get_width() // 2, center[1] - planet.get_height() // 2))
    _paint_satellites(surf, places, True, H)
    _paint_iss(surf, app, year, True, H, center)


def draw_monde(surf, font, app, hits):
    state = app.state
    year = app.shown_year()
    shown = int(round(min(year, state.horizon)))
    year_color = INK
    # Entre deux conseils : l'année seule. Pas le mot, ni les boutons, ni les infos.
    if app.turn_anim is not None:
        _draw_earth(surf, app, year, H)
        font.blit(surf, str(shown), 24, 18, 6, year_color)
        return
    drop = _stats_drop(app)
    bar_top = _STATS_TOP + drop
    sample = _draw_earth(surf, app, year, bar_top)
    font.blit(surf, str(shown), 24, 18, 6, year_color)
    _page_corner(surf, font, hits, app, "COURBES", app.open_graphs, "graphs")

    word = app.word_at(year)
    font.blit(surf, word, 24, 76, 3, CONDITION.get(word, INK))
    lines = app.headlines(year)
    line = lines[app.talk_i % len(lines)]
    height = 64
    button_y = bar_top - 20 - height
    info_scale = 2
    font.blit(
        surf, line, 24, button_y + height - font.height(info_scale),
        info_scale, CONDITION.get(word, INK),
    )
    label = app.action_label()
    if " - " in label:
        year, title = label.split(" - ", 1)
    else:
        year, title = None, label
    ended = app.state.year >= app.state.horizon - 0.01
    draw_depart_button(
        surf, font, W - 20, button_y, year, title, hits,
        app.ask_reset if ended else app.depart,
        "reset" if ended else "avancer",
        app.pressed == ("reset" if ended else "avancer"),
        app.beat,
        marks=not ended,
    )
    draw_monde_vitals(surf, font, sample, bar_top, H)
    hits.add(pygame.Rect(0, bar_top, W, H - bar_top), app.toggle_stats, "stats")


def draw_pause(surf, font, app, hits):
    year = app.shown_year()
    _draw_earth(surf, app, year)
    shown = int(round(min(year, app.state.horizon)))
    font.blit(surf, str(shown), W // 2, 28, 6, INK, align="center")
    draw_button(
        surf, font, (230, 620, 260, 64), "PLAY", hits, app.close_pause, "play",
        pressed=app.pressed == "play", scale=3,
    )


def draw_slider(surf, font, law, knob, value_index, origin_index, dx):
    """Cinq valeurs en colonne. Le carré suit le doigt, l'ocre marque le cran déjà posé."""
    x = SLIDER_X + int(dx)
    top = SLIDER_TOP
    bot = SLIDER_BOT
    ty = slider_y(knob)
    if ty > top:
        pygame.draw.rect(surf, LINE, (x - 2, top, 4, ty - top))
    if bot > ty:
        pygame.draw.rect(surf, DIM, (x - 2, ty, 4, bot - ty))
    for i in range(5):
        y = slider_y(i)
        label = law["fmt"](law["values"][i])
        selected = i == int(value_index)
        font.blit(
            surf, label, x - 18, y - font.height(2) // 2,
            2, INK if selected else MUTED, align="right",
        )
        if not selected:
            pygame.draw.rect(surf, DIM, (x - 4, y - 4, 8, 8))
        if (
            origin_index is not None
            and int(origin_index) == i
            and int(origin_index) != int(value_index)
        ):
            ring = pygame.Rect(0, 0, 16, 16)
            ring.center = (x, y)
            pygame.draw.rect(surf, OCHRE, ring, 1)
    thumb = 16
    pygame.draw.rect(surf, BG, (x - thumb // 2 - 1, ty - thumb // 2 - 1, thumb + 2, thumb + 2))
    pygame.draw.rect(surf, INK, (x - thumb // 2, ty - thumb // 2, thumb, thumb))


def _card_slots(count):
    """Un segment par orientation. Ensemble, ils font exactement la largeur de la carte."""
    left = _PLATE.x
    width = _PLATE.w
    if count <= 0:
        return []
    if count == 1:
        return [pygame.Rect(left, 0, width, 10)]
    gap = 4
    size = (width - (count - 1) * gap) // count
    if size < 4:
        gap = 2
        size = (width - (count - 1) * gap) // count
    if size < 3:
        gap = 0
        size = max(1, width // count)
    extra = width - (count * size + (count - 1) * gap)
    while extra < 0 and size > 1:
        size -= 1
        extra = width - (count * size + (count - 1) * gap)
    slots = []
    x = left
    for i in range(count):
        w = size + (1 if extra > 0 else 0)
        if extra > 0:
            extra -= 1
        slots.append(pygame.Rect(x, 0, max(1, w), 10))
        x += w + gap
    return slots


def _token_marks(surf, slot, spent, y):
    """Les jetons dépensés sur cette carte, répartis sur la largeur du segment."""
    spent = max(0, min(4, int(spent)))
    if spent <= 0:
        return
    gap = 2 if spent > 1 else 0
    tw = (slot.w - (spent - 1) * gap) // spent
    extra = slot.w - (spent * tw + (spent - 1) * gap)
    x = slot.x
    for n in range(spent):
        w = max(1, tw + (1 if n < extra else 0))
        pygame.draw.rect(surf, OCHRE, (x, y, w, 4))
        x += w + gap


# Carte à gauche. Au-delà, le graphe montre le présent et l'avenir.
_PLATE = pygame.Rect(24, 124, 344, 432)
_CARD_CLIP = pygame.Rect(0, 118, 360, 448)
# Le glissé change de carte sur la largeur de la colonne, pas sur tout l'écran.
CARD_STRIDE = _CARD_CLIP.w
_TITLE_Y = 140
_HINT_X = 40
_HINT_Y = 196
_HINT_W = 308
_VALUE_X = 40
_VALUE_Y = 292
_HORIZON_Y = 364
_HORIZON_W = 216


def _column_text(surf, font, paragraphs, x, y, scale, color, max_w, step, bottom):
    for line, _header in _wrap(font, paragraphs, scale, max_w):
        if y >= bottom:
            break
        if line:
            font.blit(surf, line, x, y, scale, color)
        y += step
    return y


_card_fade = None


def _card_fade_surf():
    global _card_fade
    if _card_fade is None:
        _card_fade = pygame.Surface((W, H), pygame.SRCALPHA)
    return _card_fade


def _card_alpha(dx, span=None):
    """Pleine au centre, transparente une largeur de carte plus loin."""
    span = float(CARD_STRIDE if span is None else span)
    if span <= 0:
        return 1.0
    return max(0.0, 1.0 - abs(float(dx)) / span)


_CARD_BAKE = {}
_CARD_REGION = pygame.Rect(0, 110, 400, 470)
_CARD_SCRATCH = None


def _card_scratch():
    global _CARD_SCRATCH
    if _CARD_SCRATCH is None:
        _CARD_SCRATCH = pygame.Surface((W, H))
    return _CARD_SCRATCH


def _draw_orientation(surf, font, app, hits, index, dx, knob=None):
    """La colonne d'une orientation, décalée de dx."""
    law = LAWS[index]
    target = surf
    prev = target.get_clip()
    plate = _PLATE.move(dx, 0)
    pygame.draw.rect(target, LINE, plate.move(4, 4))
    pygame.draw.rect(target, BG, plate)
    pygame.draw.rect(target, INK, plate, 2)
    settled = app.law_anim is None and abs(app.law_pan) < 16 and index == app.law
    pad = hits if settled else Hits()
    title_band = pygame.Rect(plate.x + 16, _TITLE_Y, plate.w - 32, 48)
    title_scale = 4 if font.width(law["title"], 4) + _INFO_GAP + _INFO_R * 2 <= title_band.w else 3
    title_top = title_band.y + (title_band.h - font.height(title_scale)) // 2
    target.set_clip(title_band)
    draw_title_with_info(
        target, font, law["title"], plate.centerx, title_top,
        SERIES_COLOR[law["series"]], pad,
        lambda i=index: app.open_fiche(LAWS[i]["title"], LAWS[i].get("info") or (), "conseil"),
        "fiche", settled and app.pressed == "fiche",
        align="center", room=title_band.w, pulse=app.beat,
    )
    target.set_clip(None)
    _column_text(
        target, font, law["hint"], _HINT_X + dx, _HINT_Y,
        2, MUTED, _HINT_W, 18, _VALUE_Y - 8,
    )
    shown = app._notch_at(index)
    if knob is None:
        knob = app.knob if index == app.law else float(shown)
    num = law["fmt"](law["values"][shown])
    unit = "" if num == "NON" else law["unit"]
    scale = 4 if len(num) <= 4 else 3
    font.blit(target, num, _VALUE_X + dx, _VALUE_Y, scale, INK)
    if unit:
        font.blit(target, unit, _VALUE_X + dx, _VALUE_Y + font.height(scale) + 8, 2, MUTED)
    preview = app.preview_traj()
    note_clip = pygame.Rect(_HINT_X + dx, _HORIZON_Y - 4, _HORIZON_W, 150)
    target.set_clip(note_clip)
    if preview is not None:
        y = _horizon_brief(
            target, font, app.traj(), preview, app.state.year,
            20, _HINT_X + dx, _HORIZON_Y, app.state.horizon,
        )
        _horizon_brief(
            target, font, app.traj(), preview, app.state.year,
            50, _HINT_X + dx, y + 8, app.state.horizon,
        )
    else:
        _column_text(
            target, font, ("UN NIVEAU COÛTE UN JETON.",),
            _HINT_X + dx, _HORIZON_Y, 2, DIM, _HORIZON_W, 18, _HORIZON_Y + 40,
        )
    target.set_clip(None)
    draw_slider(target, font, law, knob, shown, app.state.notches[index], dx)
    draw_button(
        target, font, notch_button(-1, dx), "-", pad,
        lambda: app.bump(-1), "notch-down",
        pressed=app.pressed == "notch-down",
        scale=3,
    )
    draw_button(
        target, font, notch_button(1, dx), "+", pad,
        lambda: app.bump(1), "notch-up",
        pressed=app.pressed == "notch-up",
        scale=3,
    )
    target.set_clip(prev)


def _baked_orientation(app, font, index):
    """Carte opaque, réutilisée tant que le cran ne change pas."""
    shown = app._notch_at(index)
    preview = app.preview_traj()
    key = (index, shown, None if preview is None else id(preview))
    cached = _CARD_BAKE.get(key)
    if cached is not None:
        return cached
    scratch = _card_scratch()
    scratch.fill(BG)
    _draw_orientation(scratch, font, app, Hits(), index, 0, knob=float(shown))
    # Plaque et ombre seulement. Sans couleur clé, le voile reste un blit simple.
    box = pygame.Rect(_PLATE.x, _PLATE.y, _PLATE.w + 4, _PLATE.h + 4)
    image = pygame.Surface(box.size)
    image.blit(scratch, (0, 0), box)
    if pygame.display.get_surface() is not None:
        image = image.convert()
    if len(_CARD_BAKE) > 8:
        _CARD_BAKE.clear()
    _CARD_BAKE[key] = image
    return image


def _blit_faded_card(surf, image, dx, fade):
    """Voile uniforme. La plaque est opaque : le translucide reste peu coûteux."""
    pos = (_PLATE.x + int(dx), _PLATE.y)
    if fade >= 0.98:
        image.set_alpha(None)
        surf.blit(image, pos)
        return
    image.set_alpha(max(0, min(255, int(round(fade * 255)))))
    surf.blit(image, pos)
    image.set_alpha(None)


def _paint_orientation(surf, font, app, hits, index, dx):
    """La carte glisse et s'efface. Au repos, elle est redessinée pour le curseur."""
    fade = _card_alpha(dx)
    if fade < 0.04:
        return
    settled = app.law_anim is None and abs(app.law_pan) < 16 and index == app.law
    if settled and fade >= 0.98:
        _draw_orientation(surf, font, app, hits, index, dx)
        return
    image = _baked_orientation(app, font, index)
    _blit_faded_card(surf, image, dx, fade)


def _page_head(surf, font, label, year):
    """Même bandeau : le type de page, puis l'année, dans un contour."""
    text = f"{label} {int(round(float(year)))}"
    scale = 3
    x, y = 24, 28
    pad_x, pad_y = 10, 8
    ascent = font.ascent(scale)
    descent = font.descent(scale)
    rect = pygame.Rect(
        x - pad_x,
        y - ascent - pad_y,
        font.width(text, scale) + pad_x * 2,
        ascent + font.height(scale) + descent + pad_y * 2,
    )
    pygame.draw.rect(surf, INK, rect, 2)
    font.blit(surf, text, x, y, scale, INK)


def draw_conseil(surf, font, app, hits):
    state = app.state
    token_y = 96
    dots_y = 96
    button = (24, 624, 672, 64)

    _draw_conseil_chart(surf, font, app)
    _page_head(surf, font, "CONSEIL", state.year)
    draw_tokens(surf, font, app.pending_seals(), token_y, app.seal_flash > 0)
    live = app._live_notches()
    pages = app.law_pages()
    pages.sort(key=lambda item: -abs(item[1]))
    for index, offset in pages:
        _paint_orientation(surf, font, app, hits, index, int(round(offset)))

    focus = app.focus_law()
    mark_y = dots_y + 14
    for i, slot in enumerate(_card_slots(len(LAWS))):
        rect = slot.move(0, dots_y)
        if i == focus:
            pygame.draw.rect(surf, INK, rect)
        else:
            pygame.draw.rect(surf, DIM, rect, 1)
        spent = abs(int(live[i]) - int(state.notches[i]))
        _token_marks(surf, rect, spent, mark_y)
        hits.add(rect.inflate(0, 12), lambda i=i: app.set_law(i), f"dot{i}")
    draw_button(
        surf, font, button, "VALIDER LES ORIENTATIONS", hits,
        app.validate_orientations, "valider",
        pressed=app.pressed == "valider", scale=3,
    )


def _horizon_brief(surf, font, committed, preview, now, shift, x, y, cap=YEAR_MAX):
    """Deux lignes à gauche : l'échéance, puis le chiffre qui bouge le plus."""
    target = min(cap, now + shift)
    if target <= now + 0.4:
        return y
    label = f"{int(round(target - now))} ANS"
    if target >= cap - 0.1 and shift > (cap - now):
        label = str(int(cap))
    a = committed.sample(target)
    b = preview.sample(target)
    best = max(VITALS, key=lambda item: abs(a[item[0]] - b[item[0]]) / SCALES[item[0]])
    key, name = best[0], best[1]
    font.blit(surf, label, x, y, 2, MUTED)
    if abs(a[key] - b[key]) / SCALES[key] < 0.008:
        font.blit(surf, "PRESQUE RIEN", x + font.width(label, 2) + 12, y, 2, DIM)
        return y + 18
    font.blit(surf, name, x + font.width(label, 2) + 12, y, 2, SERIES_COLOR[key])
    left = format_vital(key, a[key])
    right = format_vital(key, b[key])
    mid = " > "
    y2 = y + 18
    font.blit(surf, left, x, y2, 2, MUTED)
    xx = x + font.width(left, 2)
    font.blit(surf, mid, xx, y2, 2, DIM)
    xx += font.width(mid, 2)
    font.blit(surf, right, xx, y2, 2, tone_color(vital_tone(key, b[key])))
    return y2 + 18


def _year_axis(surf, font, axis):
    rect = PLOT_RECT
    marks = [YEAR_MIN]
    for year in (1950, 2000, 2050, 2100):
        if YEAR_MIN < year < axis - 8:
            marks.append(year)
    if int(round(axis)) != int(marks[-1]):
        marks.append(int(round(axis)))
    last = len(marks) - 1
    for i, year in enumerate(marks):
        label = str(int(year))
        x = _x_year(year, rect, axis)
        if i == 0:
            font.blit(surf, label, rect.x + 8, _AXIS_Y, 2, DIM)
        elif i == last:
            font.blit(surf, label, rect.right - 8, _AXIS_Y, 2, DIM, align="right")
        else:
            font.blit(surf, label, x, _AXIS_Y, 2, DIM, align="center")


def _mark(surf, x, y, color):
    pygame.draw.rect(surf, BG, (x - 5, y - 5, 10, 10))
    pygame.draw.rect(surf, color, (x - 3, y - 3, 6, 6))


def _chart_clip(plot, ghost):
    """Côtés et bas fermés. Le haut est ouvert : la courbe continue sur le fond."""
    box = plot if ghost else plot.inflate(-2, -2)
    return pygame.Rect(box.x, 0, box.w, box.bottom)


def _blend_curve(before, after, weight, origin):
    """Trait tenu entre deux mondes. weight(annee) va de 0 (avant) a 1 (apres)."""
    pts = []
    for i in range(min(len(before), len(after))):
        x, y0 = before[i]
        w = weight(origin + i)
        if w <= 0.0:
            pts.append((x, y0))
            continue
        y1 = after[i][1]
        pts.append((x, int(round(y0 + (y1 - y0) * (1.0 if w >= 1.0 else w)))))
    return pts


def _paint_overlay(
    surf, plot, traj, base, now, read, axis,
    ghost=False, origin=None, now_line=True, sweep=None,
):
    if origin is None:
        origin = YEAR_MIN
    if traj is None:
        return
    if base is None:
        base = traj
    grid = (58, 52, 46)
    if not ghost:
        pygame.draw.rect(surf, (22, 19, 16), plot)
        # Cadre complet ; les courbes sont dessinées après et peuvent sortir par le haut.
        pygame.draw.line(surf, grid, (plot.x, plot.y), (plot.right - 1, plot.y))
        pygame.draw.line(surf, grid, (plot.x, plot.y), (plot.x, plot.bottom - 1))
        pygame.draw.line(surf, grid, (plot.right - 1, plot.y), (plot.right - 1, plot.bottom - 1))
        pygame.draw.line(surf, grid, (plot.x, plot.bottom - 1), (plot.right - 1, plot.bottom - 1))
    prev = surf.get_clip()
    surf.set_clip(_chart_clip(plot, ghost))
    for frac in (0.25, 0.5, 0.75):
        y = int(round(_y_value(frac, 1.0, plot)))
        pygame.draw.line(surf, grid, (plot.x + 6, y), (plot.right - 6, y), 1)
    for year in (1950, 2000, 2050, 2100):
        if origin < year < axis:
            x = int(round(_x_year(year, plot, axis, origin)))
            pygame.draw.line(surf, grid, (x, plot.y + 6), (x, plot.bottom - 6), 1)
    order = [item for item in VITALS if item[0] != "pop"] + [item for item in VITALS if item[0] == "pop"]
    drawn = []
    # Le trait complet une fois, puis coupé à l'année : passé plein, avenir pointillé.
    split = max(0, int(math.ceil(min(now, axis))) - int(origin))
    start = max(0, int(math.floor(now)) - int(origin))
    # Gris continu là où le scénario sans décision s'écarte. Là où il se confond,
    # on ne le trace pas : le pointillé de l'avenir reste lisible.
    for key, _name, _lines in order:
        full = _curve_points(traj, key, plot, origin, axis, axis, origin)
        base_pts = _curve_points(base, key, plot, origin, axis, axis, origin)
        if sweep is not None:
            from_traj, weight = sweep
            from_pts = base_pts if from_traj is base else _curve_points(
                from_traj, key, plot, origin, axis, axis, origin
            )
            full = _blend_curve(from_pts, full, weight, int(origin))
        for run in _diff_runs(base_pts, full):
            _draw_curve(surf, run, DIM, False, 2)
        drawn.append((key, SERIES_COLOR[key], full))
    for key, color, full in drawn:
        _draw_curve(surf, full[: split + 1], color, False, 2)
        _draw_curve(surf, full[start:], color, True, 2, dash=(14, 8))
    if now_line:
        now_x = int(round(_x_year(min(now, axis), plot, axis, origin)))
        pygame.draw.line(surf, OCHRE, (now_x, plot.y + 4), (now_x, plot.bottom - 4), 2)
    if abs(read - now) > 0.4:
        rx = int(round(_x_year(min(read, axis), plot, axis, origin)))
        pygame.draw.line(surf, INK, (rx, plot.y + 4), (rx, plot.bottom - 4), 2)
    surf.set_clip(prev)
    if ghost:
        return
    series_cache = traj
    for key, color, _full in drawn:
        series = series_cache.column(key)
        i = int(round(read)) - YEAR_MIN
        i = max(0, min(len(series) - 1, i))
        mx = int(round(_x_year(min(read, axis), plot, axis, origin)))
        my = int(round(_y_value(float(series[i]), SCALES[key], plot)))
        _mark(surf, mx, my, color)


_ghost_layer = None
# Sous le graphe, au-dessus du bouton. Pas de millésimes.
_CONSEIL_LEGEND_Y = 584


def _ghost_layer_surf():
    global _ghost_layer
    if _ghost_layer is None:
        _ghost_layer = pygame.Surface((W, H))
    return _ghost_layer


def _chart_legend(surf, font, y):
    """Noms colorés des cinq séries. Aucun chiffre."""
    scale = 2
    gap = 16
    items = [(SERIES_COLOR[key], name) for key, name, _lines in VITALS]
    total = sum(font.width(name, scale) for _color, name in items)
    total += gap * (len(items) - 1)
    x = (W - total) // 2
    for color, name in items:
        font.blit(surf, name, x, y, scale, color)
        x += font.width(name, scale) + gap


_GHOST_CACHE = {"key": None}


def _draw_ghost_chart(surf, font, app, traj=None, base=None, now_line=True, sweep=None):
    """Même cadrage que la fenêtre Courbes. Le gris est le scénario sans décision."""
    state = app.state
    shown = app.traj() if traj is None else traj
    ground = app.baseline() if base is None else base
    # Le balayage d'un événement redessine le trait. Le reste du graphe ne bouge pas.
    key = None if sweep is not None else (
        id(shown), id(ground), round(float(state.year), 3), int(state.horizon), bool(now_line),
    )
    layer = _ghost_layer_surf()
    if key is None:
        _GHOST_CACHE["key"] = None
    if key is None or key != _GHOST_CACHE["key"]:
        layer.set_alpha(None)
        layer.fill(BG)
        _paint_overlay(
            layer, PLOT_RECT, shown, ground,
            state.year, state.year, state.horizon, ghost=True, now_line=now_line,
            sweep=sweep,
        )
        layer.set_alpha(128)
        if key is not None:
            _GHOST_CACHE["key"] = key
    surf.blit(layer, (0, 0))
    _chart_legend(surf, font, _CONSEIL_LEGEND_Y)


_CHART_RUN = {}
_MORPH_DUR = 1.35
# Années que le front met à emporter le trait derrière lui.
_SWEEP_SOFT = 8.0


def _chart_settle(slot, token, shown):
    _CHART_RUN[slot] = {
        "token": token,
        "target": shown,
        "settled": shown,
        "origin": None,
        "t0": 0,
    }


def _chart_token(kind, app, mark):
    state = app.state
    return (
        kind,
        mark,
        round(float(state.year), 3),
        tuple(state.schedule),
        tuple(state.shocks),
        int(state.horizon),
    )


def _present_chart(slot, token, wanted, fallback, now, axis):
    """Trajectoire du choix en cours, et le passage depuis la courbe posée.

    Une nouvelle carte ne rejoue pas le graphe de la précédente. Tant que
    le choix affiché n'est pas calculé, la courbe posée reste : on ne part
    pas vers un choix déjà quitté. Au résultat, le trait part de là et le rejoint.
    """
    now = float(now)
    rec = _CHART_RUN.get(slot)
    if rec is None or rec.get("token") != token:
        shown = fallback if wanted is None else wanted
        _chart_settle(slot, token, shown)
        return shown, None

    if wanted is None:
        settled = rec["settled"] if rec.get("settled") is not None else fallback
        if rec.get("origin") is not None or rec.get("target") is not settled:
            _chart_settle(slot, token, settled)
        return settled, None

    if rec.get("target") is not wanted:
        origin = rec.get("settled")
        if origin is None or origin is wanted:
            _chart_settle(slot, token, wanted)
            return wanted, None
        rec = {
            "token": token,
            "target": wanted,
            "settled": origin,
            "origin": origin,
            "t0": pygame.time.get_ticks(),
        }
        _CHART_RUN[slot] = rec

    if rec.get("origin") is None:
        return wanted, None

    age = (pygame.time.get_ticks() - rec["t0"]) / 1000.0
    if age >= _MORPH_DUR:
        _chart_settle(slot, token, wanted)
        return wanted, None

    progress = 1.0 - (1.0 - min(1.0, age / _MORPH_DUR)) ** 3

    def weight(year):
        # Tout l'avenir part ensemble. Un front qui avance depuis l'année
        # ne bouge d'abord que là où l'écart est encore invisible.
        if year <= now:
            return 0.0
        return progress

    return wanted, (rec["origin"], weight)


def _draw_conseil_chart(surf, font, app):
    """Le graphe en fond suit les crans encore sur le curseur."""
    if tuple(app._live_notches()) == tuple(app.state.notches):
        wanted = app.traj()
    else:
        wanted = app.preview_traj()
    shown, sweep = _present_chart(
        "conseil", _chart_token("conseil", app, None),
        wanted, app.traj(), app.state.year, app.state.horizon,
    )
    _draw_ghost_chart(surf, font, app, shown, now_line=False, sweep=sweep)


def _draw_dilemma_chart(surf, font, app):
    """Même fond. Le choix surligné mène le trait. Le gris reste sans décision."""
    ev = app.event or {}
    if not app.pick:
        wanted = app.traj()
    else:
        wanted = app.dilemma_traj()
    shown, sweep = _present_chart(
        "dilemma", _chart_token("dilemma", app, ev.get("id")),
        wanted, app.traj(), app.state.year, app.state.horizon,
    )
    _draw_ghost_chart(surf, font, app, shown, now_line=False, sweep=sweep)


# Boucle du graphe d'événement : l'écart se creuse, tient, puis le trait
# revient et recommence.
_SWEEP_LEAD = 0.55
_SWEEP_RUN = 1.9
_SWEEP_HOLD = 1.6
_SWEEP_BACK = 0.55
_SWEEP_REST = 0.45
_SWEEP_LOOP = _SWEEP_LEAD + _SWEEP_RUN + _SWEEP_HOLD + _SWEEP_BACK + _SWEEP_REST


def sweep_phase(clock):
    """(avancée du front, part de l'écart tenue) à cet instant de la boucle."""
    t = float(clock) % _SWEEP_LOOP
    if t < _SWEEP_LEAD:
        return 0.0, 1.0
    t -= _SWEEP_LEAD
    if t < _SWEEP_RUN:
        u = t / _SWEEP_RUN
        return 1.0 - (1.0 - u) ** 3, 1.0
    t -= _SWEEP_RUN
    if t < _SWEEP_HOLD:
        return 1.0, 1.0
    t -= _SWEEP_HOLD
    if t < _SWEEP_BACK:
        u = t / _SWEEP_BACK
        return 1.0, 1.0 - u * u
    return 0.0, 0.0


def _draw_shock_chart(surf, font, app):
    """Le trait part du monde sans l'événement, montre l'effet, puis revient.

    Le gris tient le chemin quitté pendant que le front avance.
    """
    committed = app.traj() if hasattr(app, "traj") else None
    if committed is None:
        return
    preview = app.shock_traj() if hasattr(app, "shock_traj") else None
    if preview is None:
        _draw_ghost_chart(
            surf, font, app, committed, base=committed, now_line=False,
        )
        return
    now = float(app.state.year)
    axis = float(app.state.horizon)
    progress, level = sweep_phase(getattr(app, "shock_sweep", 0.0))
    front = now + progress * (axis - now + _SWEEP_SOFT)

    def weight(year):
        if year <= now or level <= 0.0:
            return 0.0
        return max(0.0, min(1.0, (front - year) / _SWEEP_SOFT)) * level

    _draw_ghost_chart(
        surf, font, app, preview, base=committed, now_line=False,
        sweep=(committed, weight),
    )


def draw_courbes(surf, font, app, hits):
    state = app.state
    axis = state.horizon
    read = app.read_at()
    shown = int(round(min(read, axis)))
    word = app.word_at(read)
    traj = app.traj()
    sample = traj.sample(read)
    # Le graphe d'abord : ce qui dépasse en haut reste derrière l'en-tête.
    _paint_overlay(surf, PLOT_RECT, traj, app.baseline(), state.year, read, axis)
    _year_axis(surf, font, axis)
    font.blit(surf, str(shown), 24, 18, 6, INK)
    font.blit(surf, word, 24, 76, 3, CONDITION.get(word, INK))
    _page_corner(surf, font, hits, app, "PLANÈTE", app.close_panel, "monde")
    if app.read_pinned:
        draw_button(
            surf, font, (W - 188, 72, 168, 40), "SUIVRE", hits, app.follow_now, "suivre",
            scale=2, pressed=app.pressed == "suivre",
        )
    draw_monde_vitals(surf, font, sample, 600, H)


def _close_corner(surf, hits, fn, pressed):
    rect = _gear_rect()
    draw_icon_button(surf, rect, "close", hits, fn, "fermer", pressed=pressed)


def _home_corner(surf, hits, fn, pressed):
    rect = home_rect()
    draw_home(surf, rect, pressed, ground="dark")
    hits.add(corner_hit(rect), fn, "home")


def _labeled_width(font, label, scale, pad_x, min_w):
    return max(min_w, font.width(label, scale) + pad_x * 2)


def _globe_span():
    """Haut et bas du disque, quand le globe est au milieu de l'écran."""
    limb = int(round(_LIMB))
    return PLANET_C[1] - limb, PLANET_C[1] + limb


def _center_in(top, bottom, size):
    return top + max(0, bottom - top - size) // 2


def _head_box(font):
    """Titre et sous-titre, centrés dans le bandeau au-dessus du disque."""
    gap = 12
    height = font.height(4) + gap + font.height(2)
    earth_top, earth_bot = _globe_span()
    y = _center_in(0, earth_top, height)
    return y, height, earth_top, earth_bot


def draw_reglages(surf, font, app, hits):
    # Le globe reste au centre. Titre et boutons sont centrés dans les bandeaux.
    state = app.state
    _blit_fond_reglages(surf, app, app.shown_year())
    _home_corner(surf, hits, app.go_home, app.pressed == "home")
    _close_corner(surf, hits, app.close_panel, app.pressed == "fermer")
    _title_head(surf, font, "RÉGLAGES", "")
    head_y, head_h, earth_top, earth_bot = _head_box(font)

    son = "SON OUVERT" if state.sound else "SON COUPÉ"
    scale = 2
    pad_x = 16
    height = 48
    gap = 12
    y = _center_in(earth_bot, H, height * 2 + gap)
    rules = (
        "FERMER LE JEU ARRÊTE LE TEMPS.",
        "LE CONSEIL REVIENT TOUS LES DIX ANS.",
        "GLISSEZ LA PLANÈTE POUR LA TOURNER.",
    )
    rule_step, rule_scale = 20, 2
    rule_block = rule_step * (len(rules) - 1) + font.height(rule_scale)
    # Sous le titre, au-dessus du disque : le bandeau du bas reste aux boutons.
    rule_y = head_y + head_h + max(0, (earth_top - head_y - head_h - rule_block) // 2)
    for i, line in enumerate(rules):
        font.blit(surf, line, W // 2, rule_y + i * rule_step, rule_scale, MUTED, align="center")

    row = (
        (son, app.toggle_sound, "sound", "plain"),
        ("AIDE", lambda: app.open_reader("aide"), "aide", "plain"),
        ("CRÉDITS", lambda: app.open_reader("info"), "credits", "plain"),
    )
    widths = [_labeled_width(font, label, scale, pad_x, 132) for label, _fn, _ident, _kind in row]
    total = sum(widths) + gap * (len(row) - 1)
    x = (W - total) // 2
    for width, (label, fn, ident, kind) in zip(widths, row):
        draw_button(
            surf, font, (x, y, width, height), label, hits, fn, ident,
            kind=kind, pressed=app.pressed == ident, scale=scale,
        )
        x += width + gap
    reset_w = _labeled_width(font, "NOUVELLE PARTIE", scale, pad_x, 240)
    draw_button(
        surf, font, ((W - reset_w) // 2, y + height + gap, reset_w, height), "NOUVELLE PARTIE",
        hits, app.ask_reset, "reset",
        kind="rust", pressed=app.pressed == "reset", scale=scale,
    )


def draw_intro(surf, font, app, hits):
    title, lines = INTRO[app.intro_i]
    scale = 6 if app.intro_i == 0 else 4
    earth_top, earth_bot = _globe_span()
    font.blit(
        surf, title, W // 2, _center_in(0, earth_top, font.height(scale)),
        scale, INK, align="center",
    )
    line_scale, step = 3, 40
    if lines:
        block = step * (len(lines) - 1) + font.height(line_scale)
        line_y = _center_in(earth_top, earth_bot, block)
        for i, line in enumerate(lines):
            font.blit(surf, line, W // 2, line_y + i * step, line_scale, MUTED, align="center")
    label = "COMMENCER" if app.intro_i == len(INTRO) - 1 else "SUIVANT"
    btn_h = 72
    btn_y = _center_in(earth_bot, H, btn_h)
    draw_button(
        surf, font, (160, btn_y, 400, btn_h), label, hits, app.intro_next, "intro",
        pressed=app.pressed == "intro", scale=3,
    )
    total = len(INTRO) * 10 + (len(INTRO) - 1) * 12
    x = (W - total) // 2
    pip_y = min(btn_y + btn_h + 20, H - 18)
    for i in range(len(INTRO)):
        rect = pygame.Rect(x + i * 22, pip_y, 10, 10)
        if i == app.intro_i:
            pygame.draw.rect(surf, INK, rect)
        else:
            pygame.draw.rect(surf, DIM, rect, 1)


def draw_catchup(surf, font, app, hits):
    start, end = app.catchup
    n = max(1, int(round(end - start)))
    title = "1 AN A PASSÉ" if n == 1 else f"{n} ANS ONT PASSÉ"
    font.blit(surf, title, W // 2, 48, 4, INK, align="center")
    if app.catch_shock:
        font.blit(surf, app.catch_shock, W // 2, 96, 2, OCHRE, align="center")
    if app.catch_w0 == app.catch_w1:
        font.blit(surf, "PAREIL", W // 2, 120, 2, MUTED, align="center")
        font.blit(surf, app.catch_w0, W // 2, 148, 4, CONDITION.get(app.catch_w0, INK), align="center")
    else:
        c0 = CONDITION.get(app.catch_w0, INK)
        c1 = CONDITION.get(app.catch_w1, INK)
        group = font.width(app.catch_w0, 3) + 28 + font.width(">", 3) + 28 + font.width(app.catch_w1, 3)
        x = (W - group) // 2
        y = 140
        font.blit(surf, app.catch_w0, x, y, 3, c0)
        x += font.width(app.catch_w0, 3) + 28
        font.blit(surf, ">", x, y, 3, MUTED)
        x += font.width(">", 3) + 28
        font.blit(surf, app.catch_w1, x, y, 3, c1)

    if app.catch_line:
        font.blit(surf, app.catch_line, W // 2, 188, 2, OCHRE, align="center")

    for i, (key, _chip, lines) in enumerate(VITALS):
        y = 220 + i * 52
        for row, line in enumerate(lines):
            font.blit(surf, line, 36, y + row * 10, 1, MUTED)
        text_y = y + (6 if len(lines) > 1 else 0)
        left = _vital_text(key, app.catch_a[key])
        right = _vital_text(key, app.catch_b[key])
        font.blit(surf, left, 520, text_y, 2, MUTED, align="right")
        font.blit(surf, ">", 544, text_y, 2, DIM)
        font.blit(surf, right, 568, text_y, 2, tone_color(vital_tone(key, app.catch_b[key])))
    draw_button(surf, font, (160, 540, 400, 72), "CONTINUER", hits, app.dismiss_catchup, "catch", pressed=app.pressed == "catch", scale=3)


def _art(rows):
    """Tampon pixel, centré. '#' est encré, le reste est vide."""
    height = len(rows)
    width = len(rows[0])
    ox = width // 2
    oy = height // 2
    return tuple(
        (x - ox, y - oy)
        for y, row in enumerate(rows)
        for x, mark in enumerate(row)
        if mark == "#"
    )


_GRAIN = 4


def _snap(v):
    """Aligne sur la grille de grain."""
    return int(round(v / _GRAIN)) * _GRAIN


def _rim(inside, x, y, step=1):
    """Vrai si la case est sur le bord d'une forme pleine."""
    return (
        not inside(x + step, y) or not inside(x - step, y)
        or not inside(x, y + step) or not inside(x, y - step)
    )


def _cells(inside, radius, outline):
    """Cases de grain, calées sur la grille. Le bord est un escalier régulier."""
    n = (radius + _GRAIN - 1) // _GRAIN
    pts = []
    half = _GRAIN // 2
    for gy in range(-n, n + 1):
        for gx in range(-n, n + 1):
            cx = gx * _GRAIN + half
            cy = gy * _GRAIN + half
            if not inside(cx, cy):
                continue
            if outline and not _rim(inside, cx, cy, _GRAIN):
                continue
            pts.append((cx, cy))
    return tuple(pts)


def _disk(limit):
    """Rond plein, cases de grain. Le +0,5 évite les petits disques trop carrés."""
    radius = int(limit ** 0.5) + 0.5
    bound = radius * radius

    def inside(x, y):
        return x * x + y * y <= bound

    return _cells(inside, int(radius), False)


def _diamond(radius):
    """Carré à 45°, contour seulement, cases de grain."""
    def inside(x, y):
        return abs(x) + abs(y) <= radius

    return _cells(inside, radius, True)


# Conseil : ronds pixel-art sur anneaux concentriques.
# Chaque cran de grain vers l'extérieur ; l'écart entre anneaux s'ouvre.
# (nombre, rayon, rond, sens, vitesse, décalage)
_COUNCIL = (
    (55, 208, _disk(9), 1, 0.10, 0.0),
    (51, 224, _disk(36), -1, 0.14, 0.35),
    (49, 248, _disk(100), 1, 0.08, 0.8),
    (45, 276, _disk(144), -1, 0.16, 0.2),
    (43, 310, _disk(225), 1, 0.09, 1.15),
    (39, 350, _disk(324), -1, 0.07, 0.55),
    (37, 396, _disk(441), 1, 0.13, 0.95),
    (35, 450, _disk(576), -1, 0.11, 0.15),
    (33, 514, _disk(729), 1, 0.085, 1.3),
    (31, 590, _disk(900), -1, 0.15, 0.45),
    (29, 678, _disk(1089), 1, 0.095, 0.7),
    (27, 782, _disk(1296), -1, 0.12, 1.05),
)
# Orientations : paires petit/grand, de plus en plus grandes vers l'extérieur.
# Tous tournent dans le même sens.
# (rayon de l'anneau, taille du carré, décalé d'un demi-pas)
_ORIENT_N = 36
_ORIENT = (
    (206, 10, True),
    (229, 15, False),
    (254, 11, True),
    (279, 17, False),
    (306, 13, True),
    (335, 20, False),
    (366, 15, True),
    (398, 24, False),
    (432, 18, True),
    (469, 28, False),
    (507, 22, True),
    (547, 34, False),
    (590, 28, True),
    (636, 42, False),
    (684, 35, True),
    (734, 50, False),
    (786, 46, True),
)
_DILEMMA_N = 18
_BAR_LEN = 30
# Écart à l'axe du centre. Un cercle penche d'un côté, l'autre de l'autre.
_BAR_LEAN = math.radians(18)


def _snap_cover(rect):
    """Aligne les bords de la plaque sur la grille de grain."""
    left = _snap(rect.left)
    top = _snap(rect.top)
    right = _snap(rect.right)
    bottom = _snap(rect.bottom)
    if right <= left:
        right = left + _GRAIN
    if bottom <= top:
        bottom = top + _GRAIN
    return pygame.Rect(left, top, right - left, bottom - top)


def _grain_occluded(x, y, covers):
    """Vrai si la case de grain centrée sur (x, y) chevauche une plaque."""
    cell = pygame.Rect(int(x) - _GRAIN // 2, int(y) - _GRAIN // 2, _GRAIN, _GRAIN)
    for rect in covers:
        if cell.colliderect(rect):
            return True
    return False


def _ink(surf, x, y, color):
    """Case de grain centrée sur (x, y)."""
    pygame.draw.rect(
        surf, color,
        (int(x) - _GRAIN // 2, int(y) - _GRAIN // 2, _GRAIN, _GRAIN),
    )


def _paint_pixels(surf, x, y, dots, color, covers):
    """Tampon coupé case par case au bord du masque."""
    ix, iy = int(x), int(y)
    for dx, dy in dots:
        px, py = ix + dx, iy + dy
        if _grain_occluded(px, py, covers):
            continue
        _ink(surf, px, py, color)


_STAMP = {}


def _stamp(dots):
    cached = _STAMP.get(dots)
    if cached is not None:
        return cached
    xs = [p[0] for p in dots]
    ys = [p[1] for p in dots]
    min_x, min_y = min(xs), min(ys)
    pad = _GRAIN // 2
    image = pygame.Surface((max(xs) - min_x + _GRAIN, max(ys) - min_y + _GRAIN))
    image.fill((255, 0, 255))
    image.set_colorkey((255, 0, 255))
    for x, y in dots:
        _ink(image, x - min_x + pad, y - min_y + pad, OCHRE)
    if pygame.display.get_surface() is not None:
        image = image.convert()
    cached = (image, min_x - pad, min_y - pad)
    _STAMP[dots] = cached
    return cached


def _paint_dot(surf, x, y, dots, covers):
    image, ox, oy = _stamp(dots)
    # Position continue arrondie : caler sur la grille saccade la rotation.
    ix, iy = int(round(x)), int(round(y))
    left, top = ix + ox, iy + oy
    box = image.get_rect(topleft=(left, top))
    if box.right < 0 or box.bottom < 0 or box.left >= W or box.top >= H:
        return
    if any(box.colliderect(cover) for cover in covers):
        _paint_pixels(surf, ix, iy, dots, OCHRE, covers)
        return
    surf.blit(image, box)


def _motif_ring(surf, spin, covers, count, radius, dots, phase=0.0, spin_sign=1.0, speed=0.25):
    image, ox, oy = _stamp(dots)
    cx, cy = PLANET_C
    wide, high = image.get_size()
    seq = []
    for i in range(count):
        angle = (i / count) * math.tau + phase + spin * speed * spin_sign
        x = cx + math.cos(angle) * radius
        y = cy + math.sin(angle) * radius
        ix, iy = int(round(x)), int(round(y))
        left, top = ix + ox, iy + oy
        if left >= W or top >= H or left + wide <= 0 or top + high <= 0:
            continue
        box = pygame.Rect(left, top, wide, high)
        # Le carré qui chevauche la plaque est coupé case par case.
        # Le retirer dès que son centre entre le ferait disparaître d'un bloc.
        if any(box.colliderect(cover) for cover in covers):
            _paint_pixels(surf, ix, iy, dots, OCHRE, covers)
            continue
        seq.append((image, (left, top)))
    if seq:
        surf.blits(seq, doreturn=False)


def _paint_radial_bar(surf, x, y, angle, length, color, covers):
    """Trait coupé case par case au bord du masque."""
    ca = math.cos(angle)
    sa = math.sin(angle)
    half_l = (length - 1) / 2.0
    ox, oy = int(round(x)), int(round(y))
    n = int(math.ceil(half_l / _GRAIN))
    for gi in range(-n, n + 1):
        lx = gi * _GRAIN
        sx = ox + _snap(lx * ca)
        sy = oy + _snap(lx * sa)
        if _grain_occluded(sx, sy, covers):
            continue
        _ink(surf, sx, sy, color)


def _motif_bars(surf, spin, covers, count, radius, spin_sign, phase=0.0, lean=0.0, length=None):
    cx, cy = PLANET_C
    length = _BAR_LEN if length is None else length
    margin = length / 2.0 + _GRAIN
    groups = {}
    for i in range(count):
        angle = (i / count) * math.tau + phase + spin * 0.25 * spin_sign
        x = cx + math.cos(angle) * radius
        y = cy + math.sin(angle) * radius
        if x < -margin or y < -margin or x > W + margin or y > H + margin:
            continue
        image, ox, oy = _bar_stamp(length, angle + lean)
        left, top = int(round(x)) + ox, int(round(y)) + oy
        box = image.get_rect(topleft=(left, top))
        if any(box.colliderect(cover) for cover in covers):
            _paint_radial_bar(surf, x, y, angle + lean, length, OCHRE, covers)
            continue
        bucket = groups.get(id(image))
        if bucket is None:
            bucket = [image, []]
            groups[id(image)] = bucket
        bucket[1].append((image, (left, top)))
    for image, seq in groups.values():
        surf.blits(seq, doreturn=False)


_BAR_STAMP = {}


def _bar_stamp(length, angle):
    """Trait unique tourné. Cases calées, angle arrondi au degré."""
    step = int(round(math.degrees(angle))) % 360
    key = (length, step)
    cached = _BAR_STAMP.get(key)
    if cached is not None:
        return cached
    ang = math.radians(step)
    ca, sa = math.cos(ang), math.sin(ang)
    half_l = (length - 1) / 2.0
    reach = int(math.ceil(half_l)) + _GRAIN
    side = reach * 2 + _GRAIN
    image = pygame.Surface((side, side))
    image.fill((255, 0, 255))
    n = int(math.ceil(half_l / _GRAIN))
    for gi in range(-n, n + 1):
        lx = gi * _GRAIN
        px = _snap(lx * ca)
        py = _snap(lx * sa)
        _ink(image, reach + px, reach + py, OCHRE)
    if pygame.display.get_surface() is not None:
        image = image.convert()
    image.set_colorkey((255, 0, 255))
    cached = (image, -reach, -reach)
    _BAR_STAMP[key] = cached
    return cached


def _paint_bar(surf, x, y, angle, length, covers):
    image, ox, oy = _bar_stamp(length, angle)
    left, top = int(round(x)) + ox, int(round(y)) + oy
    box = image.get_rect(topleft=(left, top))
    if any(box.colliderect(cover) for cover in covers):
        _paint_radial_bar(surf, x, y, angle, length, OCHRE, covers)
        return
    surf.blit(image, box)


_SQUARE = {}


def _square_stamp(size, color):
    key = (size, color)
    cached = _SQUARE.get(key)
    if cached is not None:
        return cached
    image = pygame.Surface((size, size))
    image.fill(color)
    if pygame.display.get_surface() is not None:
        image = image.convert()
    _SQUARE[key] = image
    return image


def _quant_color(color):
    return tuple((int(c) // 16) * 16 for c in color)


def _motif_event(surf, spin, covers):
    """Onde de choc. Plusieurs anneaux partent ensemble et s'éteignent au bord."""
    r0 = RING_R + 26
    r1 = 500
    rings = 5
    gap = 16
    cx, cy = PLANET_C
    phase = (spin * EVENT_WAVE) % 1.0
    travel = (r1 - r0) * (phase ** 0.6)
    fade = 0.0 if phase < 0.12 else min(0.84, (phase - 0.12) * 1.2)
    groups = {}
    for wave in range(rings):
        # L'anneau extérieur mène. Les autres suivent, nés au même instant.
        lead = wave / (rings - 1)
        radius = r0 + wave * gap + travel
        if lead > 0.75 and phase < 0.2:
            color = mix(RUST, INK, 0.3)
            size = 6
        else:
            color = mix(RUST, BG, min(0.88, fade + (1.0 - lead) * 0.35))
            size = 5 if lead > 0.4 else 3
        stamp = _square_stamp(size, _quant_color(color))
        bucket = groups.get(id(stamp))
        if bucket is None:
            bucket = [stamp, []]
            groups[id(stamp)] = bucket
        seq = bucket[1]
        half = size / 2.0
        count = max(36, int(math.tau * radius / 16))
        for i in range(count):
            angle = (i / count) * math.tau
            x = cx + math.cos(angle) * radius
            y = cy + math.sin(angle) * radius
            if any(cover.collidepoint(x, y) for cover in covers):
                continue
            seq.append((stamp, (int(x - half), int(y - half))))
    for _image, seq in groups.values():
        if seq:
            surf.blits(seq, doreturn=False)


_DIAMOND_PTS = {}
_GRAIN_OFF = np.array(
    [(dx, dy) for dy in range(-_GRAIN // 2, _GRAIN // 2) for dx in range(-_GRAIN // 2, _GRAIN // 2)],
    np.int16,
)


def _diamond_pts(size):
    pts = _DIAMOND_PTS.get(size)
    if pts is None:
        pts = np.asarray(_diamond(size), np.int16)
        _DIAMOND_PTS[size] = pts
    return pts


def _plot(arr, xs, ys, color, covers=()):
    mask = (xs >= 0) & (xs < W) & (ys >= 0) & (ys < H)
    for cover in covers:
        mask &= ~(
            (xs >= cover.left) & (xs < cover.right)
            & (ys >= cover.top) & (ys < cover.bottom)
        )
    if np.any(mask):
        arr[xs[mask], ys[mask]] = color


def _keep_grains(px, py, covers):
    """Retire les cases qui touchent la plaque. Le reste du carré reste visible."""
    if px.size == 0 or not covers:
        return px, py
    half = _GRAIN // 2
    left = px - half
    top = py - half
    right = left + _GRAIN
    bottom = top + _GRAIN
    keep = np.ones(px.shape, dtype=bool)
    for cover in covers:
        keep &= ~(
            (right > cover.left) & (left < cover.right)
            & (bottom > cover.top) & (top < cover.bottom)
        )
    return px[keep], py[keep]


def _expand_grains(px, py):
    if px.size == 0:
        empty = np.empty(0, np.int32)
        return empty, empty
    xs = (px[:, None] + _GRAIN_OFF[None, :, 0]).astype(np.int32).ravel()
    ys = (py[:, None] + _GRAIN_OFF[None, :, 1]).astype(np.int32).ravel()
    return xs, ys


def _ring_pixels(spin, count, radius, dots, phase, covers, speed=0.25, sign=1.0):
    step = np.arange(count, dtype=np.float32) / np.float32(count)
    ang = step * np.float32(math.tau) + np.float32(phase + spin * speed * sign)
    x = np.float32(PLANET_C[0]) + np.cos(ang) * np.float32(radius)
    y = np.float32(PLANET_C[1]) + np.sin(ang) * np.float32(radius)
    px = np.rint(x[:, None] + dots[None, :, 0]).astype(np.int32).ravel()
    py = np.rint(y[:, None] + dots[None, :, 1]).astype(np.int32).ravel()
    return _expand_grains(*_keep_grains(px, py, covers))


def _bar_pixels(spin, count, radius, sign, phase, lean, length, covers):
    step = np.arange(count, dtype=np.float32) / np.float32(count)
    angle = step * np.float32(math.tau) + np.float32(phase + spin * 0.25 * sign)
    origin_x = np.float32(PLANET_C[0]) + np.cos(angle) * np.float32(radius)
    origin_y = np.float32(PLANET_C[1]) + np.sin(angle) * np.float32(radius)
    bar = angle + np.float32(lean)
    half = (length - 1) / 2.0
    grains = np.arange(-math.ceil(half / _GRAIN), math.ceil(half / _GRAIN) + 1, dtype=np.float32)
    along = grains * np.float32(_GRAIN)
    snapped_x = np.rint(along[None, :] * np.cos(bar)[:, None] / _GRAIN).astype(np.int32) * _GRAIN
    snapped_y = np.rint(along[None, :] * np.sin(bar)[:, None] / _GRAIN).astype(np.int32) * _GRAIN
    cx = np.rint(origin_x[:, None] + snapped_x).astype(np.int32).ravel()
    cy = np.rint(origin_y[:, None] + snapped_y).astype(np.int32).ravel()
    return _expand_grains(*_keep_grains(cx, cy, covers))


def _on_screen(radius, reach):
    """L'anneau entier est hors cadre : inutile de le dessiner."""
    return radius - reach <= math.hypot(W / 2, H / 2) + 28


def _paint_orient_motif(arr, spin, covers):
    half = math.pi / _ORIENT_N
    xs = []
    ys = []
    for radius, size, shifted in _ORIENT:
        if not _on_screen(radius, size):
            continue
        px, py = _ring_pixels(
            spin, _ORIENT_N, radius, _diamond_pts(size),
            half if shifted else 0.0, covers,
        )
        xs.append(px)
        ys.append(py)
    if xs:
        _plot(arr, np.concatenate(xs), np.concatenate(ys), OCHRE)


def _paint_dilemma_motif(arr, spin, covers):
    half = math.pi / _DILEMMA_N
    inner = _ORIENT[0][0]
    outer = 507
    lift = 18
    xs = []
    ys = []
    for index, (radius, _size, _shifted) in enumerate(_ORIENT):
        scale = 1 + 0.3 * (radius - inner) / (outer - inner)
        length = max(_GRAIN * 4, round(_BAR_LEN * scale))
        ring = radius + lift
        if not _on_screen(ring, length / 2 + _GRAIN):
            continue
        turn = index * half
        px, py = _bar_pixels(spin, _DILEMMA_N, ring, 1.0, turn, _BAR_LEAN, length, covers)
        xs.append(px)
        ys.append(py)
        px, py = _bar_pixels(spin, _DILEMMA_N, ring, -1.0, turn + half, -_BAR_LEAN, length, covers)
        xs.append(px)
        ys.append(py)
    if xs:
        _plot(arr, np.concatenate(xs), np.concatenate(ys), OCHRE)


def _paint_event_motif(arr, spin, covers):
    r0 = RING_R + 26
    r1 = 500
    rings = 5
    gap = 16
    phase = (spin * EVENT_WAVE) % 1.0
    travel = (r1 - r0) * (phase ** 0.6)
    fade = 0.0 if phase < 0.12 else min(0.84, (phase - 0.12) * 1.2)
    for wave in range(rings):
        lead = wave / (rings - 1)
        radius = r0 + wave * gap + travel
        if lead > 0.75 and phase < 0.2:
            color = mix(RUST, INK, 0.3)
            size = 6
        else:
            color = mix(RUST, BG, min(0.88, fade + (1.0 - lead) * 0.35))
            size = 5 if lead > 0.4 else 3
        count = max(36, int(math.tau * radius / 16))
        step = np.arange(count, dtype=np.float32) / np.float32(count)
        ang = step * np.float32(math.tau)
        xs = np.rint(np.float32(PLANET_C[0]) + np.cos(ang) * np.float32(radius)).astype(np.int32)
        ys = np.rint(np.float32(PLANET_C[1]) + np.sin(ang) * np.float32(radius)).astype(np.int32)
        half = size // 2
        for oy in range(size):
            for ox in range(size):
                _plot(arr, xs + ox - half, ys + oy - half, color, covers)


def _motif_blits(surf, spin, covers, kind):
    """Repli si la surface ne se laisse pas écrire pixel par pixel."""
    if kind == "orient":
        half = math.pi / _ORIENT_N
        for radius, size, shifted in _ORIENT:
            _motif_ring(
                surf, spin, covers, _ORIENT_N, radius, _diamond(size),
                phase=half if shifted else 0.0,
            )
        return
    if kind == "dilemma":
        half = math.pi / _DILEMMA_N
        inner = _ORIENT[0][0]
        outer = 507
        lift = 18
        for index, (radius, _size, _shifted) in enumerate(_ORIENT):
            scale = 1 + 0.3 * (radius - inner) / (outer - inner)
            length = max(_GRAIN * 4, round(_BAR_LEN * scale))
            ring = radius + lift
            turn = index * half
            _motif_bars(
                surf, spin, covers, _DILEMMA_N, ring, 1.0,
                phase=turn, lean=_BAR_LEAN, length=length,
            )
            _motif_bars(
                surf, spin, covers, _DILEMMA_N, ring, -1.0,
                phase=turn + half, lean=-_BAR_LEAN, length=length,
            )
        return
    _motif_event(surf, spin, covers)


def _motif(surf, spin, covers, kind):
    """Chaque carte d'ouverture a son dessin.

    Les pixels s'écrivent dans l'image déjà dessinée. Un calque plein
    cadre, même avec une couleur clé, coûtait autant qu'une image.
    """
    if kind == "council":
        for count, radius, dots, sign, speed, phase in _COUNCIL:
            _motif_ring(
                surf, spin, covers, count, radius, dots,
                phase=phase, spin_sign=sign, speed=speed,
            )
        return
    try:
        arr = pygame.surfarray.pixels3d(surf)
    except pygame.error:
        _motif_blits(surf, spin, covers, kind)
        return
    try:
        if kind == "orient":
            _paint_orient_motif(arr, spin, covers)
        elif kind == "dilemma":
            _paint_dilemma_motif(arr, spin, covers)
        else:
            _paint_event_motif(arr, spin, covers)
    finally:
        del arr


def _title_plate(font, title, sub):
    """Rectangle du masque sous le titre, calé sur la grille de grain."""
    y, height, _earth_top, _earth_bot = _head_box(font)
    width = max(font.width(title, 4), font.width(sub, 2)) + 24
    return _snap_cover(pygame.Rect((W - width) // 2, y - 10, width, height + 18))


def _intro_covers(plate, button):
    """Masque titre et bouton. Le motif est coupé case par case sur leurs bords."""
    face = pygame.Rect(button)
    return (plate, _snap_cover(face.union(face.move(4, 4))))


def _restore_mask(surf, rect):
    """Plaque opaque sous le titre : pas d'étoiles derrière le texte."""
    pygame.draw.rect(surf, BG, rect)


def _title_head(surf, font, title, sub):
    y, _height, _earth_top, _earth_bot = _head_box(font)
    font.blit(surf, title, W // 2, y, 4, INK, align="center")
    font.blit(surf, sub, W // 2, y + font.height(4) + 12, 2, MUTED, align="center")


def draw_title(surf, font, app, hits):
    kind = app.title or "orient"
    year = int(round(app.state.year))
    _draw_earth(surf, app, app.shown_year(), orbitals=False)
    _y, _height, _earth_top, earth_bot = _head_box(font)
    btn_h = 56
    btn_y = _center_in(earth_bot, H, btn_h)
    if kind == "event":
        title, sub = f"ÉVÉNEMENT {year}", ""
    elif kind == "dilemma":
        title, sub = f"DILEMMES {year}", "LES DILEMMES À ARBITRER"
    else:
        # Conseil et orientations : une seule carte, motif des orientations.
        title = f"CONSEIL DE L'HUMANITÉ {year}"
        sub = f"LES ORIENTATIONS POUR LES {TURN_YEARS} PROCHAINES ANNÉES"
        kind = "orient"
    button = (160, btn_y, 400, btn_h)
    plate = _title_plate(font, title, sub)
    covers = _intro_covers(plate, button)
    _motif(surf, app.motif_phase(), covers, kind)
    _restore_mask(surf, plate)
    _title_head(surf, font, title, sub)
    draw_button(
        surf, font, button, "CONTINUER", hits,
        app.dismiss_title, "titre",
        pressed=app.pressed == "titre", scale=3,
    )


def draw_reveal(surf, app):
    if app.reveal_kind == "shock" and app.shock is not None:
        key = ("shock", app.shock["id"])
    elif app.event is not None:
        key = key_for_dilemma(app.event)
    else:
        return
    dur = REVEAL_DUR if REVEAL_DUR > 0 else 1.0
    render_anim(surf, key, min(1.0, app.reveal_t / dur), (W // 2, H // 2 - 16))


def draw_shock(surf, font, app, hits):
    """Carte d'événement : plaque à gauche, graphe en fond, comme le conseil."""
    sh = app.shock
    _draw_shock_chart(surf, font, app)
    _page_head(surf, font, "ÉVÉNEMENT", sh["year"])
    plate = _PLATE
    pygame.draw.rect(surf, LINE, plate.move(4, 4))
    pygame.draw.rect(surf, BG, plate)
    pygame.draw.rect(surf, INK, plate, 2)
    title = sh["title"]
    title_band = pygame.Rect(plate.x + 16, _TITLE_Y, plate.w - 32, 48)
    title_scale = 4 if font.width(title, 4) + _INFO_GAP + _INFO_R * 2 <= title_band.w else 3
    title_top = title_band.y + (title_band.h - font.height(title_scale)) // 2
    prev = surf.get_clip()
    surf.set_clip(title_band)
    draw_title_with_info(
        surf, font, title, plate.centerx, title_top, INK, hits,
        lambda: app.open_fiche(sh["title"], sh.get("info") or card_info(sh), "shock"),
        "fiche", app.pressed == "fiche",
        align="center", room=title_band.w, pulse=app.beat,
    )
    surf.set_clip(None)
    _column_text(
        surf, font, sh["lines"], _HINT_X, _HINT_Y,
        2, MUTED, _HINT_W, 18, _VALUE_Y - 8,
    )
    effect = sh.get("effect") or ""
    if effect:
        _column_text(
            surf, font, (effect,), _HINT_X, _VALUE_Y,
            2, OCHRE, _HINT_W, 18, _HORIZON_Y - 4,
        )
    preview = app.shock_traj() if hasattr(app, "shock_traj") else None
    committed = app.traj() if hasattr(app, "traj") else None
    note_clip = pygame.Rect(_HINT_X, _HORIZON_Y - 4, _HINT_W, 150)
    surf.set_clip(note_clip)
    if preview is not None and committed is not None:
        now = float(getattr(app.state, "year", sh.get("year") or 0))
        cap = int(getattr(app.state, "horizon", YEAR_MAX))
        y = _horizon_brief(
            surf, font, committed, preview, now, 20, _HINT_X, _HORIZON_Y, cap,
        )
        _horizon_brief(
            surf, font, committed, preview, now, 50, _HINT_X, y + 8, cap,
        )
    else:
        _column_text(
            surf, font, ("LE MONDE DÉCIDE",),
            _HINT_X, _HORIZON_Y, 2, DIM, _HINT_W, 18, _HORIZON_Y + 40,
        )
    surf.set_clip(prev)
    draw_button(
        surf, font, (24, 624, 672, 64), "CONTINUER", hits, app.dismiss_shock, "ack",
        pressed=app.pressed == "ack", scale=3,
    )


def _choice_card(surf, font, rect, label, sub, hits, fn, ident, pressed, on):
    """Réponse du dilemme, colonne de gauche. Le sous-texte se replie."""
    rect = pygame.Rect(rect)
    face = rect.move(3, 3) if pressed else pygame.Rect(rect)
    if not pressed:
        pygame.draw.rect(surf, LINE, rect.move(4, 4))
    pygame.draw.rect(surf, BG, face)
    border = OCHRE if on else INK
    fg = OCHRE if on else INK
    pygame.draw.rect(surf, border, face, 2)
    font.blit(surf, label, face.x + 16, face.y + 17, 3, fg)
    prev = surf.get_clip()
    surf.set_clip(pygame.Rect(face.x + 12, face.y + 43, face.w - 24, face.h - 53))
    _column_text(
        surf, font, (sub,), face.x + 16, face.y + 45,
        2, MUTED, face.w - 32, 16, face.bottom - 8,
    )
    surf.set_clip(prev)
    hits.add(rect, fn, ident)


_DILEMMA_BAKE = {}


def _draw_dilemma(surf, font, app, hits, ev, dx, interactive):
    """Colonne du dilemme, décalée. Le graphe reste en fond."""
    target = surf
    pad = hits if interactive else Hits()
    ox = int(round(dx))
    draw_title_with_info(
        target, font, ev["title"], 24 + ox, 114, INK, pad,
        lambda: app.open_fiche(ev["title"], card_info(ev), "event"),
        "fiche", interactive and app.pressed == "fiche",
        pulse=app.beat,
    )
    y = 152
    for line in ev["lines"]:
        y = _column_text(target, font, (line,), 24 + ox, y, 2, MUTED, 312, 18, 290)
    for key, top in (("a", 312), ("b", 418)):
        label, _index, _delta, sub, _shock = choice_parts(ev[key])
        on = interactive and app.pick == key
        _choice_card(
            target, font, (24 + ox, top, 324, 88), label, sub, pad,
            lambda k=key: app.pick_choice(k), key,
            pressed=interactive and app.pressed == key, on=on,
        )
    ready = interactive and app.pick in ("a", "b")
    draw_button(
        target, font, (24 + ox, 624, 672, 64), "VALIDER", pad,
        app.validate_dilemma, "valider",
        pressed=ready and app.pressed == "valider", scale=3, enabled=ready,
    )


def _baked_dilemma(app, font, ev):
    key = ev.get("id")
    cached = _DILEMMA_BAKE.get(key)
    if cached is not None:
        return cached
    scratch = _card_scratch()
    scratch.fill((255, 0, 255))
    _draw_dilemma(scratch, font, app, Hits(), ev, 0, False)
    image = scratch.copy()
    if pygame.display.get_surface() is not None:
        image = image.convert()
    image.set_colorkey((255, 0, 255))
    if len(_DILEMMA_BAKE) > 4:
        _DILEMMA_BAKE.clear()
    _DILEMMA_BAKE[key] = image
    return image


def _paint_dilemma(surf, font, app, hits, ev, dx, interactive):
    """La carte glisse. On déplace une image déjà dessinée."""
    fade = _card_alpha(dx, W)
    if fade < 0.04 or ev is None:
        return
    if interactive and fade >= 0.98:
        _draw_dilemma(surf, font, app, hits, ev, dx, True)
        return
    image = _baked_dilemma(app, font, ev)
    surf.blit(image, (int(round(dx)), 0))


def draw_event(surf, font, app, hits):
    _draw_dilemma_chart(surf, font, app)
    pan = float(getattr(app, "event_pan", 0.0) or 0.0)
    prev = getattr(app, "event_prev", None)
    if prev is not None and abs(pan) > 1:
        _paint_dilemma(surf, font, app, hits, prev, pan - W, False)
        _paint_dilemma(surf, font, app, hits, app.event, pan, False)
    else:
        _paint_dilemma(surf, font, app, hits, app.event, 0, True)
    ev = app.event
    if ev is not None:
        _page_head(surf, font, "DILEMMES", ev.get("year") or app.state.year)


def draw_fin(surf, font, app, hits):
    title, lines = getattr(app, "_fin_copy", None) or FIN["chute"]
    font.blit(surf, str(int(round(app.state.year))), W // 2, 36, 4, MUTED, align="center")
    font.blit(surf, title, W // 2, 90, 4, INK, align="center")
    if app.fin_word:
        font.blit(surf, app.fin_word, W // 2, 150, 3, CONDITION.get(app.fin_word, INK), align="center")
    y = 210
    for line in lines:
        for part in _wrap(font, (line,), 2, 640):
            text, _header = part
            if text:
                font.blit(surf, text, W // 2, y, 2, MUTED, align="center")
            y += 22
        y += 8
    sample = app.traj().sample(app.state.year)
    draw_vitals(surf, font, sample, 470, 560)
    if app.fin_can:
        draw_button(
            surf, font, (48, 580, 300, 80), "CONTINUER", hits, app.continue_horizon, "suite",
            pressed=app.pressed == "suite", scale=3,
        )
        draw_button(
            surf, font, (372, 580, 300, 80), "LE MONDE", hits, app.close_fin, "monde",
            pressed=app.pressed == "monde", scale=3,
        )
    else:
        draw_button(
            surf, font, (160, 590, 400, 80), "LE MONDE", hits, app.close_fin, "monde",
            pressed=app.pressed == "monde", scale=3,
        )


def draw_confirm(surf, font, app, hits):
    if getattr(app, "confirm", None) == "off":
        font.blit(surf, "ÉTEINDRE", W // 2, 160, 4, INK, align="center")
        font.blit(surf, "LA MACHINE ?", W // 2, 210, 4, INK, align="center")
        font.blit(surf, "LA PARTIE EST GARDÉE.", W // 2, 280, 2, MUTED, align="center")
        draw_button(surf, font, (48, 400, 300, 80), "RESTER", hits, app.cancel_reset, "keep", pressed=app.pressed == "keep", scale=3)
        draw_button(surf, font, (372, 400, 300, 80), "ÉTEINDRE", hits, app.do_poweroff, "off", kind="rust", pressed=app.pressed == "off", scale=3)
        return
    font.blit(surf, "OUBLIER CETTE", W // 2, 160, 4, INK, align="center")
    font.blit(surf, "PLANÈTE ?", W // 2, 210, 4, INK, align="center")
    font.blit(surf, "ON RECOMMENCE EN 2026.", W // 2, 280, 2, MUTED, align="center")
    draw_button(surf, font, (48, 400, 300, 80), "GARDER", hits, app.cancel_reset, "keep", pressed=app.pressed == "keep", scale=3)
    draw_button(surf, font, (372, 400, 300, 80), "OUBLIER", hits, app.do_reset, "forget", kind="rust", pressed=app.pressed == "forget", scale=3)


def draw_toast(surf, font, text, bad=True, center_y=None):
    color = RUST if bad else OCHRE
    width = font.width(text, 2) + 28
    rect = pygame.Rect(0, 0, width, 36)
    rect.center = (W // 2, NAV_Y - 28 if center_y is None else center_y)
    pygame.draw.rect(surf, BG, rect)
    pygame.draw.rect(surf, color, rect, 2)
    font.blit_center(surf, text, rect, 2, color)


def _wrap(font, paragraphs, scale, max_w):
    lines = []
    for para in paragraphs:
        if para == "":
            lines.append(("", False))
            continue
        header = "." not in para and "," not in para and len(para) < 32
        words = para.split()
        cur = ""
        first = True
        for word in words:
            trial = word if not cur else f"{cur} {word}"
            if font.width(trial, scale) <= max_w:
                cur = trial
            else:
                if cur:
                    lines.append((cur, header and first))
                    first = False
                cur = word
        if cur:
            lines.append((cur, header and first))
    return lines


def draw_reader(surf, font, app, hits, title, paragraphs, close=None):
    _close_corner(surf, hits, close or app.close_reader, app.pressed == "fermer")
    font.blit(surf, title, W // 2, 28, 4, INK, align="center")
    view = pygame.Rect(36, 84, 640, H - 84 - 28)
    lines = _wrap(font, paragraphs, 2, view.w - 16)
    step = 22
    span = max(0, len(lines) * step - view.h)
    app.scroll = max(0, min(int(app.scroll), span))
    line_h = font.height(2)
    ascent = font.ascent(2)
    descent = font.descent(2)
    surf.set_clip(pygame.Rect(view.x, view.y - ascent, view.w, view.h + ascent + descent))
    y = view.y - int(app.scroll)
    for line, header in lines:
        if y >= view.bottom:
            break
        if line and y >= view.y and y + line_h <= view.bottom:
            font.blit(surf, line, view.x, y, 2, INK if header else MUTED)
        y += step
    surf.set_clip(None)
    if span > 0:
        track_x = view.right - 6
        pygame.draw.rect(surf, LINE, (track_x, view.y, 4, view.h))
        thumb_h = max(28, int(view.h * view.h / (view.h + span)))
        travel = view.h - thumb_h
        thumb_y = view.y + int(travel * (app.scroll / span))
        pygame.draw.rect(surf, OCHRE, (track_x, thumb_y, 4, thumb_h))


def draw(surf, font, app):
    surf.fill(BG)
    hits = Hits()
    if app.overlay == "intro":
        draw_intro(surf, font, app, hits)
    elif app.overlay == "title":
        draw_title(surf, font, app, hits)
    elif app.overlay == "catchup":
        draw_catchup(surf, font, app, hits)
    elif app.overlay == "reveal":
        draw_reveal(surf, app)
    elif app.overlay == "shock":
        draw_shock(surf, font, app, hits)
    elif app.overlay == "event":
        draw_event(surf, font, app, hits)
    elif app.overlay == "confirm":
        draw_confirm(surf, font, app, hits)
    elif app.overlay == "fiche" and app.fiche:
        draw_reader(surf, font, app, hits, app.fiche[0], app.fiche[1], app.close_fiche)
    elif app.overlay == "aide":
        draw_reader(surf, font, app, hits, "AIDE", AIDE, app.close_reader)
    elif app.overlay == "info":
        draw_reader(surf, font, app, hits, "CRÉDITS", INFO, app.close_reader)
    elif app.overlay == "pause":
        draw_pause(surf, font, app, hits)
    elif app.overlay == "courbes":
        draw_courbes(surf, font, app, hits)
    elif app.overlay == "reglages":
        draw_reglages(surf, font, app, hits)
    elif app.overlay == "conseil":
        draw_conseil(surf, font, app, hits)
    elif app.overlay == "fin":
        draw_fin(surf, font, app, hits)
    else:
        draw_monde(surf, font, app, hits)
    # Pas pendant les intros ni le défilement des années. La croix occupe déjà ce coin.
    if app.turn_anim is None and app.overlay not in (
        "intro", "title", "reglages", "aide", "info", "fiche", "confirm",
    ):
        _gear_corner(surf, hits, app)
    if app.toast_t > 0 and app.toast:
        toast_y = 596 if app.overlay in ("conseil", "event", "shock") else None
        draw_toast(surf, font, app.toast, app.toast_bad, toast_y)
    return hits
