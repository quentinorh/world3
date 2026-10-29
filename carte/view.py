"""Projection web mercator et tuiles visibles. Pur, sans pygame."""

from __future__ import annotations

import math

TILE = 256
MAX_DATA_ZOOM = 12
# Au-dela des donnees : les tuiles du niveau 12 sont agrandies (pixel-art).
MAX_VIEW_ZOOM = 15
MIN_VIEW_ZOOM = 0
HOME_LAT = 20.0
HOME_LON = 10.0
HOME_ZOOM = 2.0

# Limite de la projection, en degres.
_LAT_LIMIT = 85.05112878


def clamp_zoom(zoom):
    return min(MAX_VIEW_ZOOM, max(MIN_VIEW_ZOOM, zoom))


def data_zoom(zoom):
    return min(MAX_DATA_ZOOM, max(0, int(math.floor(zoom))))


# Crans sous la vue pour le pixel-art (2 => tuiles agrandies au moins x4).
PAINT_BELOW = 2


def paint_zoom(zoom):
    """Niveau des tuiles a l'ecran : PAINT_BELOW crans sous la vue, puis agrandi."""
    z = int(math.floor(clamp_zoom(zoom)))
    return min(MAX_DATA_ZOOM, max(0, z - PAINT_BELOW))


def tile_pixels(zoom):
    zoom = clamp_zoom(zoom)
    scale = 2 ** (zoom - paint_zoom(zoom))
    return max(1, int(round(TILE * scale)))


def world_size(zoom):
    return TILE * (2 ** zoom)


def lonlat_to_px(lon, lat, zoom):
    size = world_size(zoom)
    lat = min(_LAT_LIMIT, max(-_LAT_LIMIT, lat))
    x = (lon + 180.0) / 360.0 * size
    rad = math.radians(lat)
    y = (1.0 - math.log(math.tan(rad) + 1.0 / math.cos(rad)) / math.pi) / 2.0 * size
    return x, y


def px_to_lonlat(x, y, zoom):
    size = world_size(zoom)
    eps = 1e-6
    y = min(max(y, eps), size - eps)
    x = x % size
    lon = x / size * 360.0 - 180.0
    north = math.pi * (1.0 - 2.0 * y / size)
    lat = math.degrees(math.atan(math.sinh(north)))
    return lat, lon


def pan(lon, lat, zoom, dx, dy):
    """Le doigt emmene la carte : dx, dy sont le deplacement de l'ecran."""
    x, y = lonlat_to_px(lon, lat, zoom)
    return px_to_lonlat(x - dx, y - dy, zoom)


def tiles_in_view(lon, lat, zoom, width, height, pad=0, source_z=None):
    """Tuiles (z, x, y, sx, sy). x est ramene au monde, sx/sy a l'ecran.

    Par defaut source_z est paint_zoom (niveau precedent agrandi).
    pad ajoute des tuiles hors cadre (prechargement des bords).
    """
    zoom = clamp_zoom(zoom)
    tz = paint_zoom(zoom) if source_z is None else int(source_z)
    tz = min(MAX_DATA_ZOOM, max(0, tz))
    tile_px = TILE * (2 ** (zoom - tz))
    center_x, center_y = lonlat_to_px(lon, lat, zoom)
    left = center_x - width / 2.0
    top = center_y - height / 2.0
    count = 1 << tz
    pad = max(0, int(pad))
    x0 = math.floor(left / tile_px) - pad
    x1 = math.floor((left + width - 1e-6) / tile_px) + pad
    y0 = math.floor(top / tile_px) - pad
    y1 = math.floor((top + height - 1e-6) / tile_px) + pad
    found = []
    for ty in range(y0, y1 + 1):
        if ty < 0 or ty >= count:
            continue
        for tx in range(x0, x1 + 1):
            sx = tx * tile_px - left
            sy = ty * tile_px - top
            found.append((tz, tx % count, ty, sx, sy))
    return tile_px, found


def parent_tile(z, x, y):
    """Tuile du zoom precedent qui couvre (z, x, y), ou None."""
    if z <= 0:
        return None
    return (z - 1, x // 2, y // 2)


def approach_zoom(zoom, target):
    """Un pas vers le zoom vise. Plafonne pour ne pas sauter un niveau d'un coup."""
    zoom = clamp_zoom(zoom)
    target = clamp_zoom(target)
    gap = target - zoom
    if abs(gap) <= 0.01:
        return target
    delta = gap * 0.45
    if delta > 0.35:
        delta = 0.35
    elif delta < -0.35:
        delta = -0.35
    nxt = zoom + delta
    if (gap > 0 and nxt > target) or (gap < 0 and nxt < target):
        return target
    return nxt


def tile_screen_rects(lon, lat, zoom, z, x, y, width, height):
    """(sx, sy, cote) de la tuile a l'ecran, copie de l'autre cote de la coupure."""
    zoom = clamp_zoom(zoom)
    span = world_size(zoom) / (1 << z)
    center_x, center_y = lonlat_to_px(lon, lat, zoom)
    left = center_x - width / 2.0
    top = center_y - height / 2.0
    base_x = x * span - left
    base_y = y * span - top
    world = world_size(zoom)
    rects = []
    for shift in (0.0, world, -world):
        sx = base_x + shift
        if sx + span < 0 or sx > width or base_y + span < 0 or base_y > height:
            continue
        rects.append((sx, base_y, span))
    return rects


def screen_box(sx, sy, span):
    """Pixels entiers du rectangle, bords colles a la tuile voisine."""
    x0 = int(round(sx))
    y0 = int(round(sy))
    x1 = int(round(sx + span))
    y1 = int(round(sy + span))
    return x0, y0, max(1, x1 - x0), max(1, y1 - y0)
