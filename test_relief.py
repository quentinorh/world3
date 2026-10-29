"""Seuil de connexion, puis le dessin du globe, sans reseau."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np

from relief.dem import ASSETS, Terrain, locate
from relief.spill import spill_map
from relief.view import render
from world3.theme import BG

# Mers qui doivent communiquer avec l'océan à 0 m.
_OUVERTES = (
    ("Méditerranée", 38.0, 18.0),
    ("mer Rouge", 20.0, 38.5),
    ("Baltique", 58.5, 20.0),
    ("mer Noire", 43.5, 34.0),
)
_CASPIENNE = (41.0, 51.0)


def test_cuvette_et_plateau():
    # La longitude se referme : les murs de 500 m empêchent le tour du monde
    # d'être un chemin plus bas que le col.
    elev = np.full((6, 10), 500, dtype=np.int16)
    elev[:, 1] = -4000
    elev[:, 2] = -100
    elev[:, 3] = -50
    elev[:, 4] = 30
    elev[:, 5] = -20
    elev[:, 6] = -20
    spill = spill_map(elev)
    assert spill[3, 1] == -4000
    assert spill[3, 3] == -50
    assert spill[3, 5] == 30
    assert not (spill[3, 5] <= 0)
    assert spill[3, 5] <= 30
    assert spill[3, 3] > -120
    assert spill[3, 3] <= 0
    # Un col en diagonale suffit.
    thin = np.full((5, 5), 80, dtype=np.int16)
    thin[2, 0] = -300
    thin[1, 1] = 10
    thin[0, 2] = -15
    spill = spill_map(thin)
    assert spill[0, 2] == 10


def test_locate_nord_et_date():
    row, col = locate(89.97, -179.97, 2160, 4320)
    assert row == 0
    assert col == 0
    row, col = locate(0.0, 0.0, 2160, 4320)
    assert row == 1080
    assert col == 2160


def test_ocean_et_mers():
    if not ASSETS.exists():
        raise AssertionError("dem.npz absent : python -m relief.build_dem")
    terrain = Terrain.load()
    part = float((terrain.spill <= 0).mean())
    assert 0.65 <= part <= 0.75, part
    for _name, lat, lon in _OUVERTES:
        elev, spill = terrain.at(lat, lon)
        assert spill <= 0, (_name, elev, spill)
        assert elev < 0, (_name, elev, spill)
    elev, spill = terrain.at(*_CASPIENNE)
    assert elev < 0, (elev, spill)
    assert spill > 0, (elev, spill)
    # Plateau de la Sonde : une case basse, déjà dans l'océan, émerge à -120 m.
    height, width = terrain.elev.shape
    lat = np.linspace(-4.0, 2.0, 13)
    lon = np.linspace(104.0, 110.0, 13)
    lat, lon = np.meshgrid(lat, lon)
    ground, level = terrain.sample(lat, lon)
    shelf = (ground <= -20) & (ground >= -80) & (level <= 0) & (level > -120)
    assert shelf.any()
    assert not (level[shelf][0] <= -120)


def test_dessin():
    if not ASSETS.exists():
        raise AssertionError("dem.npz absent : python -m relief.build_dem")
    import pygame

    terrain = Terrain.load()
    dry = render(terrain, 23.5, 90.2, 0.22, 0, 96, 80, steps=12)
    wet = render(terrain, 23.5, 90.2, 0.22, 70, 96, 80, steps=12)
    assert dry.shape == (80, 96, 3)
    assert not np.array_equal(dry, wet)
    assert not np.array_equal(dry[40, 48], np.array(BG))
    pygame.init()
    try:
        window = pygame.display.set_mode((96, 80))
        frame = pygame.surfarray.make_surface(np.transpose(dry, (1, 0, 2)))
        window.blit(frame, (0, 0))
        pygame.display.flip()
    finally:
        pygame.quit()


def main():
    test_cuvette_et_plateau()
    test_locate_nord_et_date()
    test_ocean_et_mers()
    test_dessin()
    print("relief ok")


if __name__ == "__main__":
    main()
