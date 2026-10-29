"""L-systèmes : réécriture parallèle, puis tortue dans l'espace.

Le cas plan (F, f, +, -, crochets) est celui des grammaires de Lindenmayer.
Ici la tortue a un repère complet : cap, gauche, haut. Le contexte ignore
les branches, comme un signal qui suit l'axe et non le rameau. Une règle
peut en cacher une autre, moins précise ; à précision égale, le poids tire
au hasard.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import numpy as np

# Opérateurs de tortue : ils ne comptent pas comme voisins d'un module.
_SKIP = frozenset("+-&^\\/|[]!'{}*,f")
# Lettres laissées en bout de dérivation : un bourgeon qui luit.
_APEX = frozenset("XABIS")
_GOLDEN = math.radians(137.507764)
_MAX_STRING = 8000
_MAX_SEG = 160
_MAX_LEAF = 64
_MAX_BLOOM = 80
_MAX_DAB = 34


@dataclass(frozen=True)
class Rule:
    """`gauche < pred > droite → succ`. None : ce côté n'est pas lu."""

    pred: str
    succ: str
    left: str | None = None
    right: str | None = None
    weight: float = 1.0

    def spec(self) -> int:
        return (self.left is not None) + (self.right is not None)


def left_module(s: str, i: int) -> str:
    """Module précédent sur l'axe. Les crochets sont sautés."""
    return _module(s, i, -1)


def right_module(s: str, i: int) -> str:
    """Module suivant sur l'axe. Une branche `[...]` ne compte pas."""
    return _module(s, i, 1)


def _module(s: str, i: int, step: int) -> str:
    j = i + step
    n = len(s)
    while 0 <= j < n:
        ch = s[j]
        if step > 0 and ch == "[":
            j = _skip_branch(s, j, 1)
            continue
        if step < 0 and ch == "]":
            j = _skip_branch(s, j, -1)
            continue
        if ch in _SKIP or ch in "[]":
            j += step
            continue
        return ch
    return ""


def _skip_branch(s: str, j: int, step: int) -> int:
    depth = 1
    j += step
    n = len(s)
    open_b = "[" if step > 0 else "]"
    close_b = "]" if step > 0 else "["
    while 0 <= j < n and depth:
        if s[j] == open_b:
            depth += 1
        elif s[j] == close_b:
            depth -= 1
        j += step
    return j


def _choose(pool: list[Rule], rng: random.Random) -> Rule:
    best = max(rule.spec() for rule in pool)
    narrow = [rule for rule in pool if rule.spec() == best]
    if len(narrow) == 1:
        return narrow[0]
    total = 0.0
    for rule in narrow:
        total += rule.weight
    pick = rng.random() * total
    acc = 0.0
    for rule in narrow:
        acc += rule.weight
        if pick <= acc:
            return rule
    return narrow[-1]


def rewrite(axiom: str, rules: tuple[Rule, ...], steps: int, rng: random.Random) -> str:
    """Applique toutes les règles en parallèle, `steps` fois."""
    grouped: dict[str, list[Rule]] = {}
    contextual = False
    for rule in rules:
        grouped.setdefault(rule.pred, []).append(rule)
        if rule.left is not None or rule.right is not None:
            contextual = True
    s = axiom
    for _ in range(max(0, steps)):
        if len(s) > _MAX_STRING:
            break
        if contextual:
            s = _apply_context(s, grouped, rng)
        else:
            s = _apply_free(s, grouped, rng)
    return s


def _apply_free(s: str, grouped: dict[str, list[Rule]], rng: random.Random) -> str:
    out = []
    for ch in s:
        pool = grouped.get(ch)
        if not pool:
            out.append(ch)
        elif len(pool) == 1:
            out.append(pool[0].succ)
        else:
            out.append(_choose(pool, rng).succ)
    return "".join(out)


def _apply_context(s: str, grouped: dict[str, list[Rule]], rng: random.Random) -> str:
    out = []
    for i, ch in enumerate(s):
        pool = grouped.get(ch)
        if not pool:
            out.append(ch)
            continue
        matched = []
        left = left_module(s, i) if any(r.left is not None for r in pool) else ""
        right = right_module(s, i) if any(r.right is not None for r in pool) else ""
        for rule in pool:
            if rule.left is not None and rule.left != left:
                continue
            if rule.right is not None and rule.right != right:
                continue
            matched.append(rule)
        if not matched:
            out.append(ch)
        else:
            out.append(_choose(matched, rng).succ)
    return "".join(out)


def _dot(a, b) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _norm(a):
    m = math.sqrt(_dot(a, a))
    if m < 1e-8:
        return (0.0, 1.0, 0.0)
    return (a[0] / m, a[1] / m, a[2] / m)


def _add(p, v, scale):
    return (p[0] + v[0] * scale, p[1] + v[1] * scale, p[2] + v[2] * scale)


def _rodrigues(v, axis, ang):
    c = math.cos(ang)
    s = math.sin(ang)
    k = 1.0 - c
    cr = _cross(axis, v)
    d = _dot(axis, v)
    return (
        v[0] * c + cr[0] * s + axis[0] * d * k,
        v[1] * c + cr[1] * s + axis[1] * d * k,
        v[2] * c + cr[2] * s + axis[2] * d * k,
    )


def _yaw(h, l, u, ang):
    """Tourner autour du haut. Angle positif : à gauche."""
    c, s = math.cos(ang), math.sin(ang)
    nh = (h[0] * c - l[0] * s, h[1] * c - l[1] * s, h[2] * c - l[2] * s)
    nl = (h[0] * s + l[0] * c, h[1] * s + l[1] * c, h[2] * s + l[2] * c)
    return nh, nl, u


def _pitch(h, l, u, ang):
    """Tourner autour de la gauche. Angle positif : cap vers le haut du repère."""
    c, s = math.cos(ang), math.sin(ang)
    nh = (h[0] * c + u[0] * s, h[1] * c + u[1] * s, h[2] * c + u[2] * s)
    nu = (-h[0] * s + u[0] * c, -h[1] * s + u[1] * c, -h[2] * s + u[2] * c)
    return nh, l, nu


def _roll(h, l, u, ang):
    c, s = math.cos(ang), math.sin(ang)
    nl = (l[0] * c - u[0] * s, l[1] * c - u[1] * s, l[2] * c - u[2] * s)
    nu = (l[0] * s + u[0] * c, l[1] * s + u[1] * c, l[2] * s + u[2] * c)
    return h, nl, nu


def _ortho(h, l, _u):
    h = _norm(h)
    d = _dot(l, h)
    l = _norm((l[0] - h[0] * d, l[1] - h[1] * d, l[2] - h[2] * d))
    u = _norm(_cross(l, h))
    return h, l, u


class Geom:
    """Segments, feuilles et lueurs, en mètres, plante à l'origine."""

    def __init__(self):
        self.a = np.zeros((0, 3), np.float32)
        self.b = np.zeros((0, 3), np.float32)
        self.rgb = np.zeros((0, 3), np.uint8)
        self.wide = np.zeros((0,), np.float32)
        self.leaves: list[tuple[np.ndarray, tuple[int, int, int]]] = []
        self.blooms = np.zeros((0, 3), np.float32)
        self.bloom_rgb = np.zeros((0, 3), np.uint8)
        self.bloom_r = np.zeros((0,), np.float32)

    @property
    def empty(self) -> bool:
        return len(self.a) == 0 and not self.leaves and len(self.blooms) == 0


def interpret(
    commands: str,
    angle: float = 25.0,
    step: float = 0.4,
    tropism: float = 0.0,
    sun=None,
    palette=None,
    rng: random.Random | None = None,
    wobble: float = 0.0,
) -> Geom:
    """Lit une chaîne. `angle` est en degrés. `tropism` est l'élasticité."""
    rng = rng or random.Random(0)
    colors = palette or (
        (24, 90, 80),
        (40, 220, 170),
        (170, 255, 190),
        (80, 255, 140),
        (255, 210, 120),
        (190, 255, 230),
    )
    pen = _Pen(math.radians(angle), step, tropism, sun, colors, rng, wobble)
    pen.draw(commands)
    return pen.geom()


class _Pen:
    def __init__(self, delta, step, tropism, sun, palette, rng, wobble):
        self.delta = delta
        self.step = step
        self.tropism = tropism
        self.sun = None if not sun or tropism <= 0 else _norm(sun)
        self.palette = palette
        self.rng = rng
        self.wobble = wobble
        self.pos = (0.0, 0.0, 0.0)
        self.H = (0.0, 1.0, 0.0)
        self.L = (1.0, 0.0, 0.0)
        self.U = (0.0, 0.0, 1.0)
        self.width = 1.9
        self.color = 1
        self.poly = None
        self.stack = []
        self._a = []
        self._b = []
        self._rgb = []
        self._wide = []
        self._leaves = []
        self._blooms = []
        self._bloom_rgb = []
        self._bloom_r = []
        # Bouts de rameaux où poser une masse de feuilles, après la tortue.
        self._marks = []

    def draw(self, commands: str):
        for ch in commands:
            if len(self._a) >= _MAX_SEG and ch in "Ff,":
                self._move(self.step if ch != "," else self.step * 0.42, False)
                continue
            if ch == "F":
                self._move(self.step, True)
                self._bend()
            elif ch == "f":
                self._move(self.step, False)
            elif ch == ",":
                self._move(self.step * 0.42, False)
            elif ch == "+":
                self._turn(_yaw, self.delta)
            elif ch == "-":
                self._turn(_yaw, -self.delta)
            elif ch == "&":
                self._turn(_pitch, self.delta)
            elif ch == "^":
                self._turn(_pitch, -self.delta)
            elif ch == "\\":
                self._turn(_roll, self.delta)
            elif ch == "/":
                self._turn(_roll, -self.delta)
            elif ch == "|":
                self.H, self.L, self.U = _yaw(self.H, self.L, self.U, math.pi)
            elif ch == "*":
                self.H, self.L, self.U = _yaw(self.H, self.L, self.U, _GOLDEN)
            elif ch == "[":
                poly = None if self.poly is None else list(self.poly)
                self.stack.append(
                    (self.pos, self.H, self.L, self.U, self.width, self.color, poly)
                )
            elif ch == "]":
                if self.stack:
                    self.pos, self.H, self.L, self.U, self.width, self.color, self.poly = (
                        self.stack.pop()
                    )
            elif ch == "!":
                self.width = max(0.35, self.width * 0.62)
            elif ch == "'":
                self.color = min(5, self.color + 1)
            elif ch == "{":
                self.poly = [self.pos]
            elif ch == "}":
                self._close_poly()
            elif ch == "@":
                self._flower()
            elif ch == "L":
                self._leaf()
            elif ch in _APEX:
                self._mark(0.4)
                self._glow(self.palette[5], self.step * 0.055)

    def _noise(self) -> float:
        if self.wobble <= 0:
            return 0.0
        return math.radians(self.rng.uniform(-self.wobble, self.wobble))

    def _turn(self, fn, ang):
        self.H, self.L, self.U = fn(self.H, self.L, self.U, ang + self._noise())

    def _move(self, dist, ink: bool):
        nxt = _add(self.pos, self.H, dist)
        if ink:
            self._seg(self.pos, nxt, self._stem_color(), self.width)
        if self.poly is not None and len(self._leaves) < _MAX_LEAF:
            self.poly.append(nxt)
        self.pos = nxt
        if ink and self.poly is None:
            self._mark(self.width)

    def _mark(self, width):
        self._marks.append((self.pos, self.H, self.L, width))

    def _stem_color(self):
        # Tronc sombre, rameau plus clair. Le fluo est dans les feuilles.
        if self.width >= 1.35:
            return self.palette[0]
        if self.width >= 0.8:
            return self.palette[1]
        return self.palette[2]

    def _seg(self, a, b, rgb, width):
        if len(self._a) >= _MAX_SEG:
            return
        self._a.append(a)
        self._b.append(b)
        self._rgb.append(rgb)
        self._wide.append(width)

    def _bend(self):
        sun = self.sun
        if sun is None:
            return
        axis = _cross(self.H, sun)
        mag = math.sqrt(_dot(axis, axis))
        if mag < 1e-5:
            return
        axis = (axis[0] / mag, axis[1] / mag, axis[2] / mag)
        ang = max(-0.45, min(0.45, self.tropism * mag))
        self.H = _rodrigues(self.H, axis, ang)
        self.L = _rodrigues(self.L, axis, ang)
        self.U = _rodrigues(self.U, axis, ang)
        self.H, self.L, self.U = _ortho(self.H, self.L, self.U)

    def _close_poly(self):
        pts = self.poly
        self.poly = None
        if not pts or len(pts) < 3 or len(self._leaves) >= _MAX_LEAF:
            return
        self._leaves.append(
            (np.asarray(pts, np.float32), self.palette[min(3, max(self.color, 3))])
        )

    def _leaf(self):
        self._frond(self.palette[3], 1.15, 0.0)
        self._frond(self.palette[5], 0.72, 1.15)

    def _frond(self, rgb, scale, ang):
        if len(self._leaves) >= _MAX_LEAF:
            return
        c, s = math.cos(ang), math.sin(ang)
        left = (
            self.L[0] * c + self.U[0] * s,
            self.L[1] * c + self.U[1] * s,
            self.L[2] * c + self.U[2] * s,
        )
        up = (
            -self.L[0] * s + self.U[0] * c,
            -self.L[1] * s + self.U[1] * c,
            -self.L[2] * s + self.U[2] * c,
        )
        reach = self.step * scale
        p = _add(self.pos, self.H, reach * 0.3)
        r = reach * 0.9
        pts = (
            _add(_add(p, left, r), up, r * 0.35),
            _add(_add(p, left, -r * 0.4), up, r),
            _add(_add(p, left, -r), up, -r * 0.3),
            _add(_add(p, left, r * 0.35), up, -r),
        )
        self._leaves.append((np.asarray(pts, np.float32), rgb))

    def _dab(self, mark, i):
        if len(self._leaves) >= _MAX_LEAF:
            return
        pos, H, L, _width = mark
        U = _cross(L, H)
        ang = i * 2.399963
        c, s = math.cos(ang), math.sin(ang)
        off = self.step * 0.3
        center = _add(_add(_add(pos, H, self.step * 0.22), L, c * off), U, s * off * 0.7)
        r = self.step * (0.5 + (i % 5) * 0.11)
        pts = (
            _add(_add(center, L, r), U, r * 0.3),
            _add(_add(center, L, -r * 0.35), U, r),
            _add(_add(center, L, -r), U, -r * 0.25),
            _add(_add(center, L, r * 0.28), U, -r * 0.9),
        )
        cols = (self.palette[2], self.palette[3], self.palette[3], self.palette[5])
        self._leaves.append((np.asarray(pts, np.float32), cols[i % 4]))

    def _emit_dabs(self):
        """Quelques grosses feuilles, réparties, plutôt vers le houppier."""
        room = _MAX_LEAF - len(self._leaves)
        if room <= 0 or not self._marks:
            return
        thin = [mark for mark in self._marks if mark[3] < 1.5]
        pool = thin if len(thin) >= 6 else self._marks
        n = min(_MAX_DAB, room, len(pool))
        if n <= 0:
            return
        if n == 1 or len(pool) == n:
            chosen = pool[:n] if len(pool) == n else [pool[-1]]
        else:
            step = (len(pool) - 1) / (n - 1)
            chosen = [pool[int(i * step + 0.5)] for i in range(n)]
        for i, mark in enumerate(chosen):
            self._dab(mark, i)

    def _flower(self):
        col = self.palette[4]
        reach = self.step * 0.42
        for k in range(5):
            ang = k * math.tau / 5.0
            c, s = math.cos(ang), math.sin(ang)
            d = (
                self.L[0] * c + self.U[0] * s,
                self.L[1] * c + self.U[1] * s,
                self.L[2] * c + self.U[2] * s,
            )
            self._seg(self.pos, _add(self.pos, d, reach), col, 0.55)
        self._glow(col, self.step * 0.15)

    def _glow(self, rgb, radius):
        if len(self._blooms) >= _MAX_BLOOM:
            return
        self._blooms.append(self.pos)
        self._bloom_rgb.append(rgb)
        self._bloom_r.append(radius)

    def geom(self) -> Geom:
        self._emit_dabs()
        g = Geom()
        if self._a:
            g.a = np.asarray(self._a, np.float32)
            g.b = np.asarray(self._b, np.float32)
            g.rgb = np.asarray(self._rgb, np.uint8)
            g.wide = np.asarray(self._wide, np.float32)
        g.leaves = self._leaves
        if self._blooms:
            g.blooms = np.asarray(self._blooms, np.float32)
            g.bloom_rgb = np.asarray(self._bloom_rgb, np.uint8)
            g.bloom_r = np.asarray(self._bloom_r, np.float32)
        return g
