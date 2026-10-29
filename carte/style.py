"""Ce qu'on garde d'une tuile, et les couleurs du fond de carte.

La dalle fait 4 pouces. Batiments, adresses, POI, sentiers et voies de
service ne s'y lisent pas : ils restent dans le fichier, on ne les dessine pas.
"""

from __future__ import annotations

SEA = (156, 196, 214)
LAND = (232, 224, 206)
WATER = (126, 176, 204)
WOOD = (178, 198, 160)
GRASS = (198, 214, 176)
CROP = (220, 214, 170)
URBAN = (214, 206, 196)
PARK = (186, 206, 168)
WET = (170, 198, 196)
SAND = (224, 214, 186)
ICE = (236, 240, 242)
INDUSTRIAL = (206, 202, 196)
PAPER = (244, 240, 230)
INK = (36, 32, 28)
MUTED = (96, 88, 76)
HALO = (248, 244, 236)

MOTORWAY = (214, 112, 64)
TRUNK = (222, 150, 72)
PRIMARY = (232, 196, 110)
SECONDARY = (248, 244, 230)
MINOR = (255, 252, 246)
RAIL = (120, 120, 128)
BORDER = (64, 58, 52)
BORDER_SOFT = (120, 112, 102)

_SKIP_ROADS = frozenset({
    "service", "track", "path", "footway", "cycleway", "steps", "bridleway",
    "corridor", "sidewalk", "crossing", "driveway", "parking_aisle", "alley",
    "drive-through", "emergency_access", "utility", "pedestrian", "raceway",
})
_LATE_ROADS = frozenset({"residential", "unclassified", "living_street", "road"})
_RAIL = frozenset({"rail", "light_rail", "narrow_gauge"})
_COVER = {
    "forest": WOOD, "wood": WOOD,
    "grass": GRASS, "meadow": GRASS, "grassland": GRASS,
    "farmland": CROP, "crop": CROP, "farm": CROP,
    "wetland": WET, "marsh": WET, "swamp": WET,
    "scrub": GRASS,
    "barren": SAND, "sand": SAND, "beach": SAND, "dune": SAND,
    "glacier": ICE, "ice": ICE, "snow": ICE,
    "urban": URBAN, "residential": URBAN,
}
_USE = {
    "residential": URBAN, "suburb": URBAN,
    "industrial": INDUSTRIAL, "commercial": INDUSTRIAL, "retail": INDUSTRIAL,
    "park": PARK, "garden": PARK, "forest": WOOD, "grass": GRASS,
    "cemetery": (190, 200, 186),
    "pitch": GRASS, "playground": GRASS, "recreation_ground": PARK,
    "farmland": CROP, "farmyard": CROP, "orchard": GRASS, "vineyard": CROP,
    "quarry": SAND, "military": URBAN,
}
# Couleur, epaisseur a 256 px au zoom 12, et rang : les grands axes passent dessus.
_ROAD_DRAW = {
    "motorway": (MOTORWAY, 3, 40),
    "trunk": (TRUNK, 3, 30),
    "primary": (PRIMARY, 2, 20),
    "secondary": (SECONDARY, 2, 10),
    "tertiary": (MINOR, 1, 0),
    "residential": (MINOR, 1, 0),
    "unclassified": (MINOR, 1, 0),
    "living_street": (MINOR, 1, 0),
    "road": (MINOR, 1, 0),
}
_LABEL_FLOOR = {
    "country": 1,
    "region": 3,
    "state": 4,
    "province": 4,
    "city": 5,
    "town": 8,
    "village": 11,
    "locality": 6,
}
_LABEL_CEILING = {
    "country": 6,
    "region": 8,
    "state": 8,
    "province": 8,
}
_LABEL_RANK = {
    "country": 500,
    "region": 400,
    "state": 400,
    "province": 380,
    "city": 300,
    "town": 200,
    "village": 100,
    "locality": 150,
}
_LABEL_SIZE = {
    "country": 26,
    "region": 18,
    "state": 18,
    "province": 18,
    "city": 20,
    "town": 16,
    "village": 14,
}
_HIDE = frozenset({
    "neighbourhood", "macrohood", "quarter", "hamlet", "farm",
    "isolated_dwelling", "allotments", "suburb",
})


def road_base(detail):
    detail = (detail or "").lower()
    if detail.endswith("_link"):
        return detail[:-5]
    return detail


def road_kept(kind, detail, view_zoom):
    kind = (kind or "").lower()
    if kind in ("path", "ferry", "aerialway"):
        return False
    base = road_base(detail)
    if base in _SKIP_ROADS:
        return False
    if base in _LATE_ROADS:
        return view_zoom >= 12
    if kind == "rail" or base in _RAIL:
        return view_zoom >= 8
    if base in ("tram", "subway", "monorail", "funicular", "miniature", "preserved"):
        return False
    if base:
        return True
    if kind in ("highway", "major_road"):
        return True
    if kind == "minor_road":
        return view_zoom >= 12
    return False


def road_paint(kind, detail, view_zoom):
    """Couleur, epaisseur a 256 px, et rang de dessin.

    L'epaisseur pleine est celle d'une ville, au zoom 12. En dessous le
    trait maigrit. Dezoome, tout axe tient sur un pixel, sans contour.
    """
    base = road_base(detail)
    if (kind or "").lower() == "rail" or base in _RAIL:
        color, width, rank = RAIL, 1, 5
    else:
        color, width, rank = _ROAD_DRAW.get(base, (SECONDARY, 1, 0))
        if (detail or "").lower().endswith("_link"):
            width = max(1, width - 1)
            rank = max(0, rank - 5)
    if view_zoom < 10:
        width = 1
    elif view_zoom < 12:
        width = max(1, width - 1)
    return color, width, rank


def cover_color(kind):
    return _COVER.get((kind or "").lower())


def use_color(kind):
    return _USE.get((kind or "").lower())


def boundary_kept(kind, view_zoom):
    kind = (kind or "").lower()
    if kind == "country":
        return True
    if kind == "region":
        return view_zoom >= 4
    if kind == "county":
        return view_zoom >= 8
    return False


def place_name(props):
    for key in ("name:fr", "name:en"):
        text = _clean(props.get(key))
        if text:
            return text
    text = _clean(props.get("name"))
    if text and is_latin(text):
        return text
    return ""


def label_allowed(kind, detail, min_zoom, view_zoom):
    kind = (kind or "").lower()
    detail = (detail or "").lower()
    if kind in _HIDE or detail in _HIDE:
        return False
    ceiling = _LABEL_CEILING.get(detail, _LABEL_CEILING.get(kind))
    if ceiling is not None and view_zoom > ceiling:
        return False
    if min_zoom is not None:
        return view_zoom + 0.01 >= min_zoom
    floor = _LABEL_FLOOR.get(detail, _LABEL_FLOOR.get(kind, 99))
    return view_zoom >= floor


def label_size(kind, detail):
    detail = (detail or "").lower()
    kind = (kind or "").lower()
    return _LABEL_SIZE.get(detail, _LABEL_SIZE.get(kind, 14))


def label_rank(kind, detail, population_rank):
    detail = (detail or "").lower()
    kind = (kind or "").lower()
    score = _LABEL_RANK.get(detail, _LABEL_RANK.get(kind, 0))
    if isinstance(population_rank, bool) or not isinstance(population_rank, (int, float)):
        return score
    return score + int(population_rank)


def is_latin(text):
    for char in text:
        code = ord(char)
        if code < 128:
            continue
        if 0x00C0 <= code <= 0x024F or char in "œŒæÆß":
            continue
        return False
    return True


def _clean(value):
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())
