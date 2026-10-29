"""Globe de relief, sans OpenGL.

Les rayons partent de la caméra, traversent la coque exagérée du
terrain, et s'arrêtent à la première surface : l'eau si la case est
reliée à l'océan, le sol sinon. L'exagération est forte de loin, où
l'Everest disparaîtrait, et se calme en approchant.
"""

from __future__ import annotations

import math

import numpy as np

from world3.theme import BG, ICE, MOSS, OCHRE, SAND, SEA, SEA_DEEP

EARTH_R = 6_371_000.0
ALT_FAR = 2.35
ALT_NEAR = 0.18
_FOV = math.radians(46.0)
_SUN = np.array([0.42, 0.38, 0.82], dtype=np.float32)
_SUN /= np.linalg.norm(_SUN)

# Terres couvertes : plus clair que le grand bleu, pour qu'on les voie.
_FLOOD = np.array([96.0, 184.0, 194.0], dtype=np.float32)
_LOW = np.array([42.0, 102.0, 58.0], dtype=np.float32)
_ROCK = np.array([142.0, 104.0, 74.0], dtype=np.float32)
_BASIN = np.array([118.0, 96.0, 72.0], dtype=np.float32)
_STOPS = np.array([0.0, 160.0, 650.0, 1500.0, 2800.0, 4600.0], dtype=np.float32)
_COLORS = np.array([_LOW, MOSS, SAND, OCHRE, _ROCK, ICE], dtype=np.float32)
_BG = np.array(BG, dtype=np.uint8)


def clamp_altitude(altitude: float) -> float:
    return min(ALT_FAR, max(ALT_NEAR, float(altitude)))


def pan_degrees(altitude: float, pixels: int) -> float:
    """Degrés de latitude pour un pixel, à la distance donnée."""
    altitude = clamp_altitude(altitude)
    ground = 2.0 * altitude * EARTH_R * math.tan(_FOV / 2.0)
    meters = ground / max(int(pixels), 1)
    return math.degrees(meters / EARTH_R)


def render(terrain, lat, lon, altitude, sea_m, width, height, steps=20) -> np.ndarray:
    """Image RGB, `height` lignes, `width` colonnes."""
    width = max(2, int(width))
    height = max(2, int(height))
    steps = max(4, int(steps))
    cam, right, up, forward, exag = _camera(lat, lon, altitude)
    dirs = _rays(width, height, right, up, forward)
    return _march(terrain, cam, dirs, exag, int(sea_m), steps)


def _camera(lat, lon, altitude):
    altitude = clamp_altitude(altitude)
    span = ALT_FAR - ALT_NEAR
    close = (ALT_FAR - altitude) / span
    close = float(min(1.0, max(0.0, close)))
    obliquity = math.radians(4.0 + 32.0 * close)
    exag = 40.0 - 22.0 * close
    lat_r = math.radians(lat)
    lon_r = math.radians(lon)
    cl, sl = math.cos(lat_r), math.sin(lat_r)
    co, so = math.cos(lon_r), math.sin(lon_r)
    target = np.array([cl * co, sl, cl * so], dtype=np.float64)
    north = np.array([-sl * co, cl, -sl * so], dtype=np.float64)
    north /= np.linalg.norm(north)
    back = -north
    cos_o, sin_o = math.cos(obliquity), math.sin(obliquity)
    cam = target * (1.0 + altitude * cos_o) + back * (altitude * sin_o)
    blend = (altitude - 0.55) / (ALT_FAR - 0.55)
    blend = float(min(1.0, max(0.0, blend)))
    # De près, le regard reste sous l'horizon : le ciel ne mange pas l'image.
    ahead = math.radians(-6.0) * (1.0 - blend)
    ground = target * math.cos(ahead) + north * math.sin(ahead)
    look = ground * (1.0 - blend)
    forward = look - cam
    forward /= np.linalg.norm(forward)
    right = np.cross(north, forward)
    scale = np.linalg.norm(right)
    if scale < 1e-8:
        east = np.cross(target, north)
        right = np.cross(east, forward)
        scale = np.linalg.norm(right)
    right /= scale
    up = np.cross(forward, right)
    up /= np.linalg.norm(up)
    return cam.astype(np.float32), right.astype(np.float32), up.astype(np.float32), forward.astype(np.float32), exag


def _rays(width, height, right, up, forward):
    focal = (height * 0.5) / math.tan(_FOV / 2.0)
    xs = (np.arange(width, dtype=np.float32) - np.float32((width - 1) * 0.5)) / np.float32(focal)
    ys = (np.float32((height - 1) * 0.5) - np.arange(height, dtype=np.float32)) / np.float32(focal)
    dirs = xs[None, :, None] * right + ys[:, None, None] * up + forward
    dirs /= np.maximum(np.linalg.norm(dirs, axis=2, keepdims=True), np.float32(1e-8))
    return dirs


def _march(terrain, cam, dirs, exag, sea_m, steps):
    height, width = dirs.shape[:2]
    b = dirs @ cam
    cam2 = float(np.dot(cam, cam))
    exag_r = np.float32(exag / EARTH_R)
    r_outer = np.float32(1.0 + exag * 9000.0 / EARTH_R)
    r_inner = np.float32(1.0 + exag * (-11000.0) / EARTH_R)
    water_r = np.float32(1.0 + exag * float(sea_m) / EARTH_R)
    disc_outer = b * b - (cam2 - r_outer * r_outer)
    root_outer = np.sqrt(np.maximum(disc_outer, np.float32(0.0)))
    t0 = np.maximum(-b - root_outer, np.float32(0.0))
    t1 = -b + root_outer
    disc_inner = b * b - (cam2 - r_inner * r_inner)
    root_inner = np.sqrt(np.maximum(disc_inner, np.float32(0.0)))
    t_inner = -b - root_inner
    grazes = disc_inner < 0.0
    t_end = np.where(grazes, np.minimum(t1, np.maximum(-b, t0)), t_inner)
    t_end = np.maximum(t_end, t0)
    sky = disc_outer < 0.0

    hit = np.zeros((height, width), dtype=bool)
    hit_lat = np.zeros((height, width), dtype=np.float32)
    hit_lon = np.zeros((height, width), dtype=np.float32)
    hit_elev = np.zeros((height, width), dtype=np.int16)
    hit_spill = np.zeros((height, width), dtype=np.int16)
    for step in range(steps):
        pending = ~hit & ~sky
        if not pending.any():
            break
        t = t0 + (t_end - t0) * np.float32((step + 0.5) / steps)
        pos = cam + t[..., None] * dirs
        radius = np.linalg.norm(pos, axis=2)
        lat, lon = _latlon(pos)
        elev, spill = terrain.sample(lat, lon)
        flooded = spill <= sea_m
        surface = np.where(
            flooded,
            water_r,
            np.float32(1.0) + elev.astype(np.float32) * exag_r,
        )
        arrived = pending & (radius <= surface)
        if not arrived.any():
            continue
        hit[arrived] = True
        hit_lat[arrived] = lat[arrived]
        hit_lon[arrived] = lon[arrived]
        hit_elev[arrived] = elev[arrived]
        hit_spill[arrived] = spill[arrived]

    image = np.empty((height, width, 3), dtype=np.uint8)
    image[:] = _BG
    if hit.any():
        shade = _shade(terrain, hit_lat, hit_lon, exag, sea_m)
        color = _paint(hit_elev, hit_spill, sea_m, hit_lat)
        tinted = np.clip(color * shade[..., None], 0.0, 255.0).astype(np.uint8)
        image[hit] = tinted[hit]
    return image


def _latlon(pos):
    x = pos[..., 0]
    y = pos[..., 1]
    z = pos[..., 2]
    horiz = np.sqrt(x * x + z * z)
    lat = np.degrees(np.arctan2(y, horiz)).astype(np.float32)
    lon = np.degrees(np.arctan2(z, x)).astype(np.float32)
    return lat, lon


def _shade(terrain, lat, lon, exag, sea_m):
    rows, cols = terrain.elev.shape
    cell_lat = np.float32(180.0 / rows)
    cell_lon = np.float32(360.0 / cols)
    north_m = EARTH_R * math.pi / rows
    east, _spill_e = terrain.sample(lat, lon + cell_lon)
    west, _spill_w = terrain.sample(lat, lon - cell_lon)
    north, _spill_n = terrain.sample(lat + cell_lat, lon)
    south, _spill_s = terrain.sample(lat - cell_lat, lon)
    cos_lat = np.maximum(np.cos(np.radians(lat)), np.float32(0.25))
    east_m = north_m * cos_lat
    dz_de = (east.astype(np.float32) - west.astype(np.float32)) / np.float32(2.0 * east_m) * np.float32(exag)
    dz_dn = (north.astype(np.float32) - south.astype(np.float32)) / np.float32(2.0 * north_m) * np.float32(exag)
    # L'eau reste un globe. Le fond marin n'en garde qu'une ombre légère.
    flooded = terrain.sample(lat, lon)[1] <= sea_m
    dz_de = np.where(flooded, dz_de * np.float32(0.35), dz_de)
    dz_dn = np.where(flooded, dz_dn * np.float32(0.35), dz_dn)
    radial, east_axis, north_axis = _basis(lat, lon)
    normal = radial - dz_de[..., None] * east_axis - dz_dn[..., None] * north_axis
    normal /= np.maximum(np.linalg.norm(normal, axis=2, keepdims=True), np.float32(1e-8))
    light = np.clip(normal @ _SUN, 0.0, 1.0)
    return np.float32(0.40) + np.float32(0.60) * light.astype(np.float32)


def _basis(lat, lon):
    lat_r = np.radians(lat).astype(np.float32)
    lon_r = np.radians(lon).astype(np.float32)
    cl, sl = np.cos(lat_r), np.sin(lat_r)
    co, so = np.cos(lon_r), np.sin(lon_r)
    radial = np.stack((cl * co, sl, cl * so), axis=-1)
    north = np.stack((-sl * co, cl, -sl * so), axis=-1)
    east = np.cross(radial, north)
    return radial, east, north


def _paint(elev, spill, sea_m, lat):
    elev_f = elev.astype(np.float32)
    above_sea = elev_f - np.float32(sea_m)
    flooded = spill <= sea_m
    was_land = elev > 0
    basin = (~flooded) & (above_sea < 0.0)
    land = ~flooded & ~basin
    depth = np.clip((np.float32(sea_m) - elev_f) / np.float32(4500.0), 0.0, 1.0)
    ocean = _lerp(np.array(SEA, dtype=np.float32), np.array(SEA_DEEP, dtype=np.float32), depth ** 0.55)
    # Même sous plusieurs dizaines de mètres, la terre noyée reste
    # plus claire que le large : c'est le changement qu'on vient voir.
    shallow = np.clip((np.float32(sea_m) - elev_f) / np.float32(250.0), 0.0, 1.0)
    flood = _lerp(_FLOOD, np.array(SEA, dtype=np.float32), shallow * np.float32(0.55))
    color = ocean
    if np.any(flooded & was_land):
        color = np.where((flooded & was_land)[..., None], flood, color)
    if np.any(land):
        color = np.where(land[..., None], _hypso(above_sea), color)
    if np.any(basin):
        color = np.where(basin[..., None], _BASIN, color)
    polar = (~flooded) & (np.abs(lat) >= np.float32(72.0)) & (elev_f > np.float32(200.0))
    if np.any(polar):
        icy = color * np.float32(0.35) + np.array(ICE, dtype=np.float32) * np.float32(0.65)
        color = np.where(polar[..., None], icy, color)
    return color


def _hypso(height_above):
    flat = np.clip(height_above, 0.0, _STOPS[-1]).ravel()
    painted = np.empty((flat.size, 3), dtype=np.float32)
    for channel in range(3):
        painted[:, channel] = np.interp(flat, _STOPS, _COLORS[:, channel])
    return painted.reshape(height_above.shape + (3,))


def _lerp(a, b, t):
    return a + (b - a) * t[..., None]
