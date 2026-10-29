"""Réécriture, tortue 3D, et une image du jardin, sans capteur."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("WORLD3_ACCEL", "0")

import random

import numpy as np
import pygame

from jardin.draw import Camera, project_direction, render
from jardin.lsystem import Rule, interpret, left_module, rewrite, right_module
from jardin.scene import Garden, Params
from jardin.species import EPI, FLEUR, SPECIES, grow


def test_signal_du_blog():
    # B < a → B, et B → a : le marqueur avance vers la droite.
    rules = (
        Rule("a", "B", left="B"),
        Rule("B", "a"),
    )
    s = "Baaaaaaaa"
    rng = random.Random(0)
    for _ in range(4):
        s = rewrite(s, rules, 1, rng)
    assert s == "aaaaBaaaa", s
    for _ in range(4):
        s = rewrite(s, rules, 1, rng)
    assert s == "aaaaaaaaB", s


def test_contexte_ignore_les_branches():
    s = "F[B]A"
    assert left_module(s, s.index("A")) == "F"
    assert right_module(s, s.index("B")) == "A"
    assert right_module(s, 0) == "A"
    assert left_module(s, s.index("B")) == "F"
    # Le bourgeon contre l'apex reste, celui d'un entrenœud plus loin part.
    rules = (
        Rule("A", "F[&B]A"),
        Rule("B", "B", right="A"),
        Rule("B", "X"),
    )
    got = rewrite("A", rules, 3, random.Random(0))
    assert got == "F[&X]F[&B]F[&B]A", got


def test_carre_et_tangage():
    square = interpret("F-F-F-F", angle=90, step=1, wobble=0)
    end = square.b[-1]
    assert len(square.a) == 4
    assert abs(float(end[0])) < 1e-4
    assert abs(float(end[1])) < 1e-4
    assert abs(float(end[2])) < 1e-4
    pitched = interpret("F&F", angle=90, step=1, wobble=0)
    tip = pitched.b[-1]
    assert abs(float(tip[0])) < 1e-4
    assert abs(float(tip[1]) - 1) < 1e-4
    assert abs(float(tip[2]) - 1) < 1e-4


def test_crochet_revient():
    g = interpret("F[+F]F", angle=45, step=1, wobble=0)
    assert len(g.a) == 3
    # Le troisième trait reprend le bout du premier.
    assert np.allclose(g.a[2], g.b[0], atol=1e-4)


def test_angle_dor_et_tropisme():
    plain = interpret("F+F", angle=10, step=1, wobble=0)
    gold = interpret("F*F", angle=10, step=1, wobble=0)
    assert not np.allclose(plain.b[-1], gold.b[-1], atol=1e-2)
    bent = interpret(
        "FFFFFFF", angle=20, step=1, tropism=0.35, sun=(1.0, 0.3, 0.0), wobble=0,
    )
    assert float(bent.b[-1][0]) > 0.4
    assert float(bent.b[-1][1]) > 1.0


def test_feuille_et_fleur():
    leaf = interpret("{F+F+F}", angle=90, step=1, wobble=0)
    assert len(leaf.leaves) == 1
    assert len(leaf.leaves[0][0]) >= 3
    flower = interpret("@", angle=20, step=1, wobble=0)
    assert len(flower.blooms) == 1
    assert len(flower.a) == 5
    tip = interpret("X", wobble=0)
    assert len(tip.blooms) == 1
    assert len(tip.a) == 0


def test_epi_le_signal_monte():
    def at(steps):
        return rewrite(EPI.axiom, EPI.rules, steps, random.Random(1))

    assert at(1).index("S") > at(0).index("S")
    assert at(3).index("S") > at(1).index("S")
    low = grow(EPI, 1, EPI.angle, 0, 4, 1)
    high = grow(EPI, 4, EPI.angle, 0, 4, 1)
    assert len(high.blooms) > len(low.blooms)
    assert "@" not in at(0)
    assert "@" in at(4)


def test_chaque_espece_reste_legere():
    for species in SPECIES:
        geom = grow(species, 4, species.angle, 2, 4, 3)
        assert 4 <= len(geom.a) <= 160, (species.title, len(geom.a))
        assert len(geom.blooms) <= 80


def test_fleur_a_un_apex():
    # La règle de bourgeon dormant est bien dans la grammaire.
    assert any(rule.right == "A" and rule.pred == "B" for rule in FLEUR.rules)
    geom = grow(FLEUR, 4, FLEUR.angle, 1, 2, 5)
    assert len(geom.a) >= 4


def test_scene_et_regard():
    garden = Garden(Params())
    garden.update(0.0, Params())
    batch = garden.batch()
    assert len(batch.a) > 40
    assert len(batch.spores) == 36
    ahead = project_direction((0.0, 0.0, 1.0), 0.0)
    turned = project_direction((0.0, 0.0, 1.0), 0.4)
    assert ahead is not None and turned is not None
    assert turned[0] < ahead[0]


def test_dessin():
    pygame.init()
    try:
        pygame.display.set_mode((720, 720))
        garden = Garden(Params())
        garden.update(1.0, Params())
        surf = pygame.Surface((720, 720))
        render(surf, garden.batch(), Camera(1.0, 0.0), 4, 0.0)
        img = pygame.surfarray.array3d(surf)
        # array3d est (x, y, c). Le haut du ciel est plus sombre que l'horizon.
        top = int(img[:, 12, :].sum())
        band = int(img[:, 300, :].sum())
        assert top < band
        # Une teinte fluo : du cyan ou du magenta, pas seulement le soleil orange.
        fluo = (
            ((img[:, :, 1] > 150) & (img[:, :, 2] > 120) & (img[:, :, 0] < 180))
            | ((img[:, :, 0] > 160) & (img[:, :, 2] > 140) & (img[:, :, 1] < 120))
        )
        assert int(fluo.sum()) > 40, int(fluo.sum())
    finally:
        pygame.quit()


def main():
    test_signal_du_blog()
    test_contexte_ignore_les_branches()
    test_carre_et_tangage()
    test_crochet_revient()
    test_angle_dor_et_tropisme()
    test_feuille_et_fleur()
    test_epi_le_signal_monte()
    test_chaque_espece_reste_legere()
    test_fleur_a_un_apex()
    test_scene_et_regard()
    test_dessin()
    print("jardin ok")


if __name__ == "__main__":
    main()
