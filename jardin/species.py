"""Espèces du jardin. Chaque grammaire pousse un mécanisme plus loin.

Liane : réécriture de nœuds, en trois dimensions.
Corail : plusieurs successeurs, tirés au poids.
Spirale : l'angle d'or, pas le pas de la tortue.
Fougère : feuilles pleines.
Épi : un signal qui monte l'axe, puis une fleur au bout.
Fleur : un bourgeon reste dormant tant que l'apex est son voisin.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from jardin.lsystem import Geom, Rule, interpret, rewrite

MIX = 6
MIX_ANGLE = 24


@dataclass(frozen=True)
class Species:
    name: str
    title: str
    axiom: str
    angle: int
    step: float
    rules: tuple[Rule, ...]
    wobble: float = 2.5


def _palette(hour: int):
    """Six teintes : tronc, tige, jeune, feuille, fleur, lueur. Aube → couchant."""
    t = max(0, min(4, hour)) / 4.0

    def mix(a, b):
        return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))

    return (
        mix((18, 42, 28), (36, 16, 30)),
        mix((32, 96, 70), (120, 40, 78)),
        mix((28, 118, 64), (132, 40, 86)),
        mix((64, 186, 96), (214, 58, 164)),
        mix((255, 220, 80), (150, 255, 236)),
        mix((168, 214, 64), (255, 148, 72)),
    )


def sun_vector(hour: int):
    """Soleil bas, de l'aube (à gauche) au couchant (à droite)."""
    t = max(0, min(4, hour)) / 4.0
    yaw = -0.28 + t * 0.56
    x = math.sin(yaw)
    y = 0.055
    z = math.cos(yaw)
    m = math.sqrt(x * x + y * y + z * z)
    return (x / m, y / m, z / m)


def sun_target(hour: int, tropism: int):
    """Direction de croissance, et élasticité. Zéro : pas de tropisme."""
    if tropism <= 0:
        return None, 0.0
    sx, _sy, sz = sun_vector(hour)
    k = max(0, min(4, tropism)) / 4.0
    x, y, z = sx * k, 1.0, sz * k * 0.45
    m = math.sqrt(x * x + y * y + z * z)
    return (x / m, y / m, z / m), 0.04 + 0.2 * k


LIANE = Species(
    "liane", "LIANE", "X", 25, 0.42,
    (Rule("X", "FF[&!+X][^!-X]X"),),
    wobble=2.0,
)

CORAIL = Species(
    "corail", "CORAIL", "F", 22, 0.34,
    (
        Rule("F", "F[&+F][^-F]", weight=1),
        Rule("F", "F[/+F][\\-F]", weight=1),
        Rule("F", "F[+F][-F]F", weight=1),
    ),
    wobble=3.5,
)

SPIRALE = Species(
    "spirale", "SPIRALE", "A", 30, 0.46,
    (Rule("A", "FF*[&+A][^-A]A"),),
    wobble=1.2,
)

FOUGERE = Species(
    "fougere", "FOUGÈRE", "X", 28, 0.4,
    (Rule("X", "F[&+X]/[^-X]L"),),
    wobble=1.5,
)

# Le S avance d'un entrenœud à chaque passe, et ne fleurit qu'au bout.
EPI = Species(
    "epi", "ÉPI", "SFFF", 22, 0.7,
    (
        Rule("F", "S", left="S"),
        Rule("S", "F*[@][&@][^@]", right=""),
        Rule("S", "F*[&+,@]"),
    ),
    wobble=1.0,
)

FLEUR = Species(
    "fleur", "FLEUR", "A", 26, 0.4,
    (
        Rule("A", "FF[&!B][^!B]A", weight=3),
        Rule("A", "FF[@]", weight=1),
        Rule("B", "B", right="A"),
        Rule("B", "F[@]", weight=2),
        Rule("B", "F[&!+A]L", weight=1),
    ),
    wobble=2.0,
)

HERBE = Species(
    "herbe", "HERBE", "X", 34, 0.26,
    (Rule("X", "F[+X][-X][+F]F"),),
    wobble=7.0,
)

BULBE = Species("bulbe", "BULBE", "F@", 16, 0.36, (), wobble=0.0)

SPECIES: tuple[Species, ...] = (LIANE, CORAIL, SPIRALE, FOUGERE, EPI, FLEUR)
TITLES = tuple(item.title for item in SPECIES) + ("MÉLANGE",)
HOURS = ("AUBE", "ROSE", "BRAISE", "SOIR", "COUCHANT")


def angle_for(species: Species, chosen: int, angle: int) -> int:
    """Sur une espèce, l'angle est absolu. En mélange, il décale chaque défaut."""
    if chosen == MIX:
        return max(10, min(48, species.angle + (angle - MIX_ANGLE)))
    return angle


def grow(species: Species, steps: int, angle: int, tropism: int, hour: int, seed: int) -> Geom:
    rng = random.Random(seed & 0xFFFFFFFF)
    commands = rewrite(species.axiom, species.rules, steps, rng)
    sun, elast = sun_target(hour, tropism)
    return interpret(
        commands,
        angle=angle,
        step=species.step,
        tropism=elast,
        sun=sun,
        palette=_palette(hour),
        rng=rng,
        wobble=species.wobble,
    )
