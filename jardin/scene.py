"""Le jardin défile : des carrés devant la marche, oubliés derrière."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, replace

import numpy as np

from jardin.lsystem import Geom
from jardin.species import (
    BULBE,
    HERBE,
    MIX,
    SPECIES,
    Species,
    _palette,
    angle_for,
    grow,
)

CHUNK = 9.0
AHEAD = 26.0
BEHIND = 3.0
VARIANTS = 4
_PLANTS = (2, 3, 3, 4, 4)
_GRASS = (6, 8, 10, 12, 14)
_CAPS = (5, 6, 8, 9, 11)


@dataclass(frozen=True)
class Params:
    species: int = MIX
    seed: int = 7
    steps: int = 4
    angle: int = 24
    density: int = 3
    tropism: int = 2
    hour: int = 4

    def title(self) -> str:
        return ("LIANE", "CORAIL", "SPIRALE", "FOUGÈRE", "ÉPI", "FLEUR", "MÉLANGE")[
            self.species
        ]


@dataclass
class Batch:
    a: np.ndarray
    b: np.ndarray
    rgb: np.ndarray
    wide: np.ndarray
    leaves: list
    blooms: np.ndarray
    bloom_rgb: np.ndarray
    bloom_r: np.ndarray
    spores: np.ndarray
    spore_rgb: np.ndarray
    leaf_c: np.ndarray
    leaf_r: np.ndarray
    leaf_rgb: np.ndarray


def _mix(*parts: int) -> int:
    h = 2166136261
    for part in parts:
        h ^= int(part) & 0xFFFFFFFF
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def _empty_batch() -> Batch:
    z3 = np.zeros((0, 3), np.float32)
    zc = np.zeros((0, 3), np.uint8)
    return Batch(
        z3, z3.copy(), zc, np.zeros((0,), np.float32), [],
        z3.copy(), zc.copy(), np.zeros((0,), np.float32),
        z3.copy(), zc.copy(),
        z3.copy(), np.zeros((0,), np.float32), zc.copy(),
    )


def _gain(rng: random.Random) -> np.ndarray:
    return np.array(
        [rng.uniform(0.86, 1.08), rng.uniform(0.9, 1.14), rng.uniform(0.84, 1.16)],
        np.float32,
    )


def _paint(rgb: np.ndarray, gain: np.ndarray) -> np.ndarray:
    return np.clip(rgb.astype(np.float32) * gain, 0, 255).astype(np.uint8)


def _paint_one(rgb, gain: np.ndarray):
    return tuple(max(0, min(255, int(float(rgb[i]) * float(gain[i])))) for i in range(3))


def _spin(pts: np.ndarray, x: float, z: float, rot: float, scale: float) -> np.ndarray:
    if len(pts) == 0:
        return pts
    c, s = math.cos(rot), math.sin(rot)
    px = pts[:, 0] * scale
    py = pts[:, 1] * scale
    pz = pts[:, 2] * scale
    out = np.empty_like(pts)
    out[:, 0] = x + px * c - pz * s
    out[:, 1] = py
    out[:, 2] = z + px * s + pz * c
    return out


class Garden:
    def __init__(self, params: Params | None = None):
        self.params = params or Params()
        self._geoms: dict[tuple, Geom] = {}
        self._chunks: dict[int, Batch] = {}
        self._batch: Batch | None = None
        self._spore_rng = random.Random(self.params.seed)
        self.spores = np.zeros((0, 3), np.float32)
        self.spore_rgb = np.zeros((0, 3), np.uint8)
        self._init_spores()

    def update(self, cam_z: float, params: Params):
        if params != self.params:
            self.params = params
            self._geoms.clear()
            self._chunks.clear()
            self._batch = None
            self._spore_rng = random.Random(params.seed)
            self._init_spores(cam_z)
        lo = math.floor((cam_z - BEHIND) / CHUNK)
        hi = math.floor((cam_z + AHEAD) / CHUNK)
        wanted = range(lo, hi + 1)
        if any(i not in self._chunks for i in wanted) or any(
            i not in wanted for i in self._chunks
        ):
            for i in list(self._chunks):
                if i < lo or i > hi:
                    del self._chunks[i]
            for i in wanted:
                if i not in self._chunks:
                    self._chunks[i] = self._build(i)
            self._batch = self._join()

    def _join(self) -> Batch:
        chunks = [self._chunks[i] for i in sorted(self._chunks)]
        if not chunks:
            return _empty_batch()
        segs = [c for c in chunks if len(c.a)]
        if segs:
            a = np.concatenate([c.a for c in segs])
            b = np.concatenate([c.b for c in segs])
            rgb = np.concatenate([c.rgb for c in segs])
            wide = np.concatenate([c.wide for c in segs])
        else:
            a = np.zeros((0, 3), np.float32)
            b = a.copy()
            rgb = np.zeros((0, 3), np.uint8)
            wide = np.zeros((0,), np.float32)
        leaves = []
        for c in chunks:
            leaves.extend(c.leaves)
        lights = [c for c in chunks if len(c.blooms)]
        if lights:
            blooms = np.concatenate([c.blooms for c in lights])
            bloom_rgb = np.concatenate([c.bloom_rgb for c in lights])
            bloom_r = np.concatenate([c.bloom_r for c in lights])
        else:
            blooms = np.zeros((0, 3), np.float32)
            bloom_rgb = np.zeros((0, 3), np.uint8)
            bloom_r = np.zeros((0,), np.float32)
        lc, lr, lrgb = _cloud(leaves)
        return Batch(
            a, b, rgb, wide, leaves, blooms, bloom_rgb, bloom_r,
            self.spores, self.spore_rgb, lc, lr, lrgb,
        )

    def batch(self) -> Batch:
        base = self._batch or _empty_batch()
        base.spores = self.spores
        base.spore_rgb = self.spore_rgb
        return base

    def step_spores(self, cam_z: float, dt: float):
        if len(self.spores) == 0:
            return
        self.spores[:, 1] += dt * 0.12
        # Elles restent dans le volume devant l'œil : la marche ne les sème pas.
        behind = self.spores[:, 2] < cam_z - 1.5
        high = self.spores[:, 1] > 3.6
        lost = behind | high
        if not np.any(lost):
            return
        for i in np.flatnonzero(lost):
            self.spores[i] = self._spore_pos(cam_z, self._spore_rng)

    def _init_spores(self, cam_z: float = 0.0):
        cols = _palette(self.params.hour)
        rng = self._spore_rng
        pts = [self._spore_pos(cam_z, rng) for _ in range(36)]
        rgb = []
        for _ in range(36):
            src = cols[4] if rng.random() < 0.5 else cols[5]
            rgb.append(src)
        self.spores = np.asarray(pts, np.float32)
        self.spore_rgb = np.asarray(rgb, np.uint8)

    def _spore_pos(self, cam_z, rng: random.Random):
        return (
            rng.uniform(-3.2, 3.2),
            rng.uniform(0.4, 2.8),
            cam_z + rng.uniform(1.5, 22.0),
        )

    def _geom(self, species: Species, steps: int, angle: int, seed: int) -> Geom:
        p = self.params
        key = (species.name, steps, angle, p.tropism, p.hour, seed)
        hit = self._geoms.get(key)
        if hit is None:
            hit = grow(species, steps, angle, p.tropism, p.hour, seed)
            self._geoms[key] = hit
        return hit

    def _pick_species(self, rng: random.Random) -> Species:
        if self.params.species == MIX:
            return SPECIES[rng.randrange(len(SPECIES))]
        return SPECIES[self.params.species]

    def _build(self, index: int) -> Batch:
        rng = random.Random(_mix(self.params.seed, index, 17))
        parts_a = []
        parts_b = []
        parts_c = []
        parts_w = []
        leaves = []
        blooms = []
        bloom_c = []
        bloom_r = []
        n = _PLANTS[self.params.density - 1]
        for _ in range(n):
            self._plant(rng, index, False, parts_a, parts_b, parts_c, parts_w, leaves, blooms, bloom_c, bloom_r)
        for _ in range(_GRASS[self.params.density - 1]):
            self._under(rng, index, HERBE, 2, 0.55, 1.15, parts_a, parts_b, parts_c, parts_w, leaves, blooms, bloom_c, bloom_r)
        for _ in range(_CAPS[self.params.density - 1]):
            self._under(rng, index, BULBE, 0, 0.7, 1.3, parts_a, parts_b, parts_c, parts_w, leaves, blooms, bloom_c, bloom_r)
        return _pack(parts_a, parts_b, parts_c, parts_w, leaves, blooms, bloom_c, bloom_r)

    def _plant(self, rng, index, _under, parts_a, parts_b, parts_c, parts_w, leaves, blooms, bloom_c, bloom_r):
        species = self._pick_species(rng)
        side = -1.0 if rng.random() < 0.5 else 1.0
        spread = 2.15 + self.params.density * 0.55
        x = side * rng.uniform(1.2, spread)
        z = index * CHUNK + rng.uniform(0.5, CHUNK - 0.5)
        rot = rng.random() * math.tau
        scale = rng.uniform(0.78, 1.16)
        variant = rng.randrange(VARIANTS)
        seed = _mix(self.params.seed, _name_id(species.name), variant, self.params.hour)
        angle = angle_for(species, self.params.species, self.params.angle)
        geom = self._geom(species, self.params.steps, angle, seed)
        _stamp(geom, x, z, rot, scale, rng, parts_a, parts_b, parts_c, parts_w, leaves, blooms, bloom_c, bloom_r)

    def _under(self, rng, index, species, steps, scale_lo, scale_hi, parts_a, parts_b, parts_c, parts_w, leaves, blooms, bloom_c, bloom_r):
        x = rng.uniform(-5.4, 5.4)
        if abs(x) < 0.45:
            x = 0.7 if x >= 0 else -0.7
        z = index * CHUNK + rng.uniform(0.2, CHUNK - 0.2)
        rot = rng.random() * math.tau
        scale = rng.uniform(scale_lo, scale_hi)
        seed = _mix(self.params.seed, _name_id(species.name), index, int(z * 10), int(x * 10))
        angle = species.angle
        geom = self._geom(species, steps, angle, seed & 0xFFFF)
        # L'herbe basse et les bulbes ne gardent que fleurs et feuilles.
        # Le pré, lui, est dessiné à part.
        _stamp(
            geom, x, z, rot, scale, rng,
            parts_a, parts_b, parts_c, parts_w, leaves, blooms, bloom_c, bloom_r,
            stems=False,
        )


def _name_id(name: str) -> int:
    n = 0
    for ch in name:
        n = (n * 33 + ord(ch)) & 0xFFFFFFFF
    return n


def _stamp(geom, x, z, rot, scale, rng, parts_a, parts_b, parts_c, parts_w, leaves, blooms, bloom_c, bloom_r, stems=True):
    gain = _gain(rng)
    if stems and len(geom.a):
        parts_a.append(_spin(geom.a, x, z, rot, scale))
        parts_b.append(_spin(geom.b, x, z, rot, scale))
        parts_c.append(_paint(geom.rgb, gain))
        parts_w.append(geom.wide * np.float32(scale))
    for pts, col in geom.leaves:
        leaves.append((_spin(pts, x, z, rot, scale), _paint_one(col, gain)))
    if len(geom.blooms):
        blooms.append(_spin(geom.blooms, x, z, rot, scale))
        bloom_c.append(_paint(geom.bloom_rgb, gain))
        bloom_r.append(geom.bloom_r * scale)


def _pack(parts_a, parts_b, parts_c, parts_w, leaves, blooms, bloom_c, bloom_r) -> Batch:
    if parts_a:
        a = np.concatenate(parts_a)
        b = np.concatenate(parts_b)
        rgb = np.concatenate(parts_c)
        wide = np.concatenate(parts_w)
    else:
        a = np.zeros((0, 3), np.float32)
        b = a.copy()
        rgb = np.zeros((0, 3), np.uint8)
        wide = np.zeros((0,), np.float32)
    if blooms:
        bp = np.concatenate(blooms)
        bc = np.concatenate(bloom_c)
        br = np.concatenate(bloom_r)
    else:
        bp = np.zeros((0, 3), np.float32)
        bc = np.zeros((0, 3), np.uint8)
        br = np.zeros((0,), np.float32)
    lc, lr, lrgb = _cloud(leaves)
    return Batch(a, b, rgb, wide, leaves, bp, bc, br, bp[:0], bc[:0], lc, lr, lrgb)


def _cloud(leaves):
    """Centre, rayon et couleur de chaque feuille, une fois par carré."""
    n = len(leaves)
    c = np.zeros((n, 3), np.float32)
    r = np.zeros((n,), np.float32)
    rgb = np.zeros((n, 3), np.uint8)
    for i, (pts, col) in enumerate(leaves):
        m = pts.mean(axis=0)
        c[i] = m
        r[i] = np.abs(pts - m).mean() * np.float32(1.4)
        rgb[i, 0], rgb[i, 1], rgb[i, 2] = int(col[0]), int(col[1]), int(col[2])
    return c, r, rgb


def horizon_color(hour: int):
    """Teinte du soleil, partagée par le ciel et la brume."""
    t = max(0, min(4, hour)) / 4.0
    a = (232, 128, 72)
    b = (220, 42, 112)
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# replace est utilisé par l'écran des réglages.
def with_params(params: Params, **kwargs) -> Params:
    return replace(params, **kwargs)
