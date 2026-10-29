"""Planete pixel. La sphere est un echantillonnage, pas un moteur 3D.

Les continents viennent d'une Blue Marble (NASA, domaine public),
reduite en aplats : foret, desert, glace, mer. La couleur suit
encore World3 : nourriture, pollution, population, ressources.
Les nuages sont une autre carte NASA, qui derive lentement.
Les calottes sont de la geographie, pas une temperature :
World3 ne calcule pas le climat.
"""

import math
from pathlib import Path

import numpy as np
import pygame

from .theme import CITY, ICE, MOSS, OCHRE, RUST, SAND, SEA, SEA_DEEP, mix

N = 80
_SCALE = 4
_GLOBE = Path(__file__).resolve().parent / "assets" / "globe.npz"
# Derive des nuages, en radians par seconde. Lent, pour qu'on les voie passer.
_CLOUD_SPEED = 0.035
# Quatre aplats de lumiere, du cote nuit vers le plein jour.
_GAINS = np.array([0.42, 0.62, 0.82, 1.0])
_CLOUD_TINT = np.array([236.0, 240.0, 242.0]) * _GAINS[:, None]
_CLOUD_U8 = np.clip(np.round(_CLOUD_TINT), 0, 255).astype(np.uint8)
# 0, 0.42 et 0.72, en huitièmes de 256. L'écart tient dans un niveau.
_CLOUD_W = np.array([0, 108, 184], dtype=np.uint16)
# Rayon du globe a l'ecran. Le pas est une fraction de pixel :
# coller le cran a un pixel de carte figeait le dessin, puis le faisait sauter.
_SCREEN_R = (N / 2 - 1.6) * _SCALE
_STEP = 1.0 / (_SCREEN_R * 16.0)


def _load():
    with np.load(_GLOBE) as data:
        kind = np.array(data["kind"])
        dry = np.array(data["dry"], dtype=np.float64)
        pale = np.array(data["pale"], dtype=np.float64)
        clouds = np.array(data["clouds"])
    return kind == 1, kind == 2, dry, pale, clouds


class Planet:
    def __init__(self):
        self.land, self.ice, self.dry, self.pale, self.clouds = _load()
        r = N / 2 - 1.6
        xx = (np.arange(N) - (N - 1) / 2) / r
        yy = ((N - 1) / 2 - np.arange(N)) / r
        self._x = np.broadcast_to(xx[:, None], (N, N)).astype(np.float64).copy()
        self._y = np.broadcast_to(yy[None, :], (N, N)).astype(np.float64).copy()
        self.mask = self._x * self._x + self._y * self._y <= 1.0
        self._z = np.zeros((N, N), dtype=np.float64)
        self._z[self.mask] = np.sqrt(np.maximum(0.0, 1.0 - self._x[self.mask] ** 2 - self._y[self.mask] ** 2))
        self._shaded = None
        self._bake_key = None
        self._project(0.1)
        self.kind = None
        self.kind_key = None
        self.frame = None
        self.frame_key = None
        self._sheet = None
        self._lit = None
        self._prepare_terrain()

    def _project(self, pitch):
        cp, sp = math.cos(pitch), math.sin(pitch)
        y2 = self._y * cp - self._z * sp
        z2 = self._y * sp + self._z * cp
        self.lon0 = np.arctan2(self._x, np.where(self.mask, z2, 1.0))
        self.lat = np.arcsin(np.clip(y2, -1.0, 1.0))
        sun = np.array([0.42, 0.38, 0.82], dtype=np.float64)
        sun /= np.linalg.norm(sun)
        shade = self._x * sun[0] + y2 * sun[1] + z2 * sun[2]
        self.shade = np.clip(shade, 0.0, 1.0)
        self.shade[~self.mask] = 0.0
        self.band = np.digitize(self.shade, (0.22, 0.42, 0.62)).astype(np.uint8)
        self._pitch_bucket = int(round(math.degrees(pitch) / 3.0))
        base = np.mod(self.lon0 + math.pi, math.tau).astype(np.float32)
        th, tw = self.land.shape
        ch, cw = self.clouds.shape
        self._lon_land = base * np.float32(tw / math.tau)
        self._lon_cloud = base * np.float32(cw / math.tau)
        self._ty_land = np.clip(
            np.floor((math.pi / 2.0 - self.lat) / math.pi * th).astype(np.int32), 0, th - 1,
        )
        self._ty_cloud = np.clip(
            np.floor((math.pi / 2.0 - self.lat) / math.pi * ch).astype(np.int32), 0, ch - 1,
        )
        self._tw = tw
        self._cw = cw

    def _prepare_terrain(self):
        """Le mélange sec / pâle ne dépend pas du modèle. On ne le refait pas."""
        moss = np.array(MOSS, np.float32)
        sand = np.array(SAND, np.float32)
        ochre = np.array(OCHRE, np.float32)
        dry = self.dry.astype(np.float32)
        pale = self.pale.astype(np.float32)
        col = moss + (sand - moss) * dry[..., None]
        col = col + (ochre - col) * (pale * np.float32(0.8))[..., None]
        self._terrain = np.ascontiguousarray(col)
        self._ochre = ochre
        self._rust = np.array(RUST, np.float32)
        self._ice = np.array(ICE, np.float32)
        self._sea0 = np.array(SEA, np.float32)
        self._sea1 = np.array(SEA_DEEP, np.float32)
        self._dirt = np.array((28.0, 22.0, 18.0), np.float32)
        height, width = self.land.shape
        yy, xx = np.mgrid[0:height, 0:width]
        self._noise = ((xx * 73856093 ^ yy * 19349663) & 1023).astype(np.int16)

    def _kinds(self, sample):
        pop = sample["pop"]
        fpc = sample["fpc"]
        ppolx = sample["ppolx"]
        nrfr = sample["nrfr"]
        # Crans larges : pendant le défilement des années, la teinte ne
        # se recalcule pas à chaque image.
        key = (
            round(pop / 5e8),
            round(fpc / 100.0),
            round(float(ppolx) * 2.0) / 2.0,
            round(float(nrfr) * 8.0) / 8.0,
        )
        if key == self.kind_key:
            return self.kind
        kind = np.zeros(self.land.shape, dtype=np.uint8)  # 0 mer
        kind[self.land] = 1
        kind[self.ice] = 2
        # Villes : une grille stable, plus dense quand la population monte.
        density = int(np.clip((pop - 1.4e9) / 6.5e9, 0.0, 1.0) * 22)
        noise = self._noise
        city = self.land & (noise % 100 < density)
        kind[city] = 4
        if nrfr < 0.55:
            scars = int((0.55 - nrfr) * 28)
            scar = self.land & (noise % 100 < scars) & (noise % 3 == 0)
            kind[scar] = 5
        self.kind = kind
        self.kind_key = key
        self._food = float(np.clip((500 - fpc) / 340, 0.0, 1.0))
        self._poison = float(np.clip(ppolx / 16.0, 0.0, 1.0))
        return kind

    def _sample(self, lon, lat, height, width):
        tx = np.floor(lon / math.tau * width).astype(np.int32) % width
        ty = np.floor((math.pi / 2 - lat) / math.pi * height).astype(np.int32)
        return np.clip(ty, 0, height - 1), tx

    def _bake(self, kinds):
        """Couleurs de la carte, avant la lumiere. La lumiere reste en aplats."""
        if self._bake_key == self.kind_key:
            return
        food = np.float32(self._food)
        poison = np.float32(self._poison)
        sea = self._sea0 * (np.float32(1.0) - poison) + self._sea1 * poison
        col = self._terrain * (np.float32(1.0) - food) + self._ochre * food
        fade = poison * np.float32(0.55)
        col = col * (np.float32(1.0) - fade) + self._rust * fade
        base = np.empty(col.shape, np.float32)
        base[...] = sea
        land = (kinds == 1) | (kinds == 4)
        base[land] = col[land]
        base[kinds == 2] = self._ice
        scar = kinds == 5
        if np.any(scar):
            base[scar] = col[scar] * np.float32(0.35) + self._dirt * np.float32(0.65)
        shape = (4,) + base.shape
        if self._lit is None or self._lit.shape != shape:
            self._lit = np.empty(shape, np.uint8)
        lit = self._lit
        for index, gain in enumerate((np.float32(0.42), np.float32(0.62), np.float32(0.82), np.float32(1.0))):
            lit[index] = np.clip(base * gain, 0, 255)
        self._bake_key = self.kind_key

    def _surface(self, rgb):
        if rgb.dtype != np.uint8:
            rgb = np.clip(rgb, 0, 255).astype(np.uint8)
        else:
            rgb = rgb.copy()
        rgb[~self.mask] = 0
        # frombuffer lit les pixels ligne par ligne : (y, x), pas (x, y).
        image = np.ascontiguousarray(np.transpose(rgb, (1, 0, 2)))
        temp = pygame.image.frombuffer(image.tobytes(), (N, N), "RGB")
        # La petite carte seulement : convertir le globe deja agrandi coutait plus.
        if pygame.display.get_surface() is not None:
            temp = temp.convert()
        side = N * _SCALE
        sheet = self._sheet
        if sheet is None:
            sheet = pygame.Surface((side, side))
            if pygame.display.get_surface() is not None:
                sheet = sheet.convert()
            sheet.set_colorkey((0, 0, 0))
            self._sheet = sheet
        pygame.transform.scale(temp, (side, side), sheet)
        return sheet

    def render(self, yaw, pitch, sample, clock=0.0):
        kinds = self._kinds(sample)
        self._bake(kinds)
        yaw_i, yaw_q = _quant(yaw)
        # Les nuages devancent un peu la rotation, qui va d'ouest en est.
        cloud_i, phase_q = _quant(-clock * _CLOUD_SPEED)
        pitch_bucket = int(round(math.degrees(pitch) / 3.0))
        if pitch_bucket != self._pitch_bucket:
            self._project(math.radians(pitch_bucket * 3.0))
        key = (yaw_i, pitch_bucket, self.kind_key, cloud_i)
        if key == self.frame_key:
            return self.frame

        add = np.float32(yaw_q / math.tau * self._tw)
        tx = np.floor(self._lon_land + add).astype(np.int32) % self._tw
        ty = self._ty_land
        rgb = self._lit[self.band, ty, tx]
        kind = kinds[ty, tx]
        night = self.mask & (kind == 4) & (self.band <= 1)
        if np.any(night):
            rgb = rgb.copy()
            rgb[night] = CITY

        add_c = np.float32((yaw_q + phase_q) / math.tau * self._cw)
        txc = np.floor(self._lon_cloud + add_c).astype(np.int32) % self._cw
        level = self.clouds[self._ty_cloud, txc]
        weight = _CLOUD_W[level]
        if np.any(weight):
            weight = weight[..., None]
            cloud = _CLOUD_U8[self.band].astype(np.uint16)
            mixed = rgb.astype(np.uint16) * (np.uint16(256) - weight)
            mixed += cloud * weight
            rgb = (mixed >> 8).astype(np.uint8)

        self.frame = self._surface(rgb)
        self.frame_key = key
        return self.frame


def _quant(angle):
    tick = math.floor(angle / _STEP)
    return tick, tick * _STEP
