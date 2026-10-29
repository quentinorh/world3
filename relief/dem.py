"""Altitude et seuil, nord en haut, une case au centre de chaque maille.

Cinq minutes d'arc : 2 160 lignes, 4 320 colonnes. La longitude se
referme. La ligne 0 touche le pôle Nord, sans le répéter.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

ASSETS = Path(__file__).resolve().parent / "assets" / "dem.npz"


def locate(lat, lon, height, width):
    """Case la plus proche. Latitude et longitude en degrés."""
    row, col = locate_grid(lat, lon, height, width)
    return int(row), int(col)


def locate_grid(lat, lon, height, width):
    """Même calcul, pour un tableau de points."""
    lat = np.asarray(lat, dtype=np.float32)
    lon = np.mod(np.asarray(lon, dtype=np.float32) + 180.0, 360.0) - 180.0
    cell_lat = np.float32(180.0 / height)
    cell_lon = np.float32(360.0 / width)
    row = np.rint((np.float32(90.0) - lat) / cell_lat - np.float32(0.5))
    col = np.rint((lon + np.float32(180.0)) / cell_lon - np.float32(0.5))
    row = np.clip(row, 0, height - 1).astype(np.int32)
    col = np.mod(col, width).astype(np.int32)
    return row, col


class Terrain:
    def __init__(self, elev, spill):
        self.elev = np.asarray(elev, dtype=np.int16)
        self.spill = np.asarray(spill, dtype=np.int16)
        if self.elev.shape != self.spill.shape or self.elev.ndim != 2:
            raise ValueError("altitude et seuil n'ont pas la même grille")

    @classmethod
    def load(cls, path=None):
        path = Path(path) if path is not None else ASSETS
        if not path.exists():
            raise FileNotFoundError(
                f"pas de {path.name}. Lancer : python -m relief.build_dem"
            )
        with np.load(path) as data:
            return cls(np.array(data["elev"]), np.array(data["spill"]))

    def at(self, lat, lon):
        row, col = locate(lat, lon, *self.elev.shape)
        return int(self.elev[row, col]), int(self.spill[row, col])

    def sample(self, lat, lon):
        row, col = locate_grid(lat, lon, *self.elev.shape)
        return self.elev[row, col], self.spill[row, col]
