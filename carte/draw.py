"""Dessin d'une tuile vectorielle sur une surface pygame."""

from __future__ import annotations

import pygame

from carte.mvt import decode_tile
from carte.style import (
    BORDER,
    BORDER_SOFT,
    HALO,
    INK,
    LAND,
    SEA,
    WATER,
    boundary_kept,
    cover_color,
    label_allowed,
    label_rank,
    label_size,
    place_name,
    road_kept,
    road_paint,
    use_color,
)

def render_tile(payload, size, view_zoom):
    """Surface carree et etiquettes en pixels de cette surface."""
    surf = pygame.Surface((size, size))
    surf.fill(SEA)
    labels = []
    if not payload:
        return surf, labels
    layers = decode_tile(payload)
    grouped = {}
    for layer in layers:
        grouped.setdefault(layer.name, []).append(layer)
    _fill(surf, grouped.get("earth"), LAND, SEA, size, kind=None)
    _fill(surf, grouped.get("landcover"), None, LAND, size, kind=cover_color)
    _fill(surf, grouped.get("landuse"), None, LAND, size, kind=use_color)
    _fill(surf, grouped.get("water"), WATER, LAND, size, kind=None)
    _lines(surf, grouped.get("water"), WATER, 1, size, keep=None)
    _roads(surf, grouped.get("roads"), size, view_zoom)
    _borders(surf, grouped.get("boundaries"), size, view_zoom)
    _places(grouped.get("places"), size, view_zoom, labels)
    return surf, labels


def _label_scale(size):
    return 3 if size >= 18 else 2


def blit_labels(surf, labels, font, width, height):
    ordered = sorted(labels, key=lambda item: item["rank"], reverse=True)
    taken = []
    shown = 0
    for item in ordered:
        if shown >= 48:
            break
        text = item["text"]
        scale = _label_scale(item["size"])
        text_w = font.width(text, scale)
        text_h = font.height(scale)
        x = int(item["x"] - text_w / 2)
        y = int(item["y"] - text_h / 2)
        rect = pygame.Rect(x, y, text_w, text_h)
        if rect.right < 0 or rect.bottom < 0 or rect.left > width or rect.top > height:
            continue
        padded = rect.inflate(8, 6)
        if any(padded.colliderect(other) for other in taken):
            continue
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            font.blit(surf, text, x + dx, y + dy, scale, HALO, align="left")
        font.blit(surf, text, x, y, scale, INK)
        taken.append(padded)
        shown += 1


def _fill(surf, layers, color, hole, size, kind):
    if not layers:
        return
    for layer in layers:
        for feature in layer.features:
            if feature.geom_type != 3 or not feature.rings:
                continue
            paint = color
            if kind is not None:
                paint = kind(_text(feature, "kind"))
                if paint is None:
                    continue
            exteriors = []
            holes = []
            for ring in feature.rings:
                if _area(ring) >= 0:
                    exteriors.append(ring)
                else:
                    holes.append(ring)
            if not exteriors:
                exteriors = holes
                holes = []
            for ring in exteriors:
                _polygon(surf, ring, layer.extent, size, paint)
            for ring in holes:
                _polygon(surf, ring, layer.extent, size, hole)


def _lines(surf, layers, color, width, size, keep):
    if not layers:
        return
    unit = max(1, int(round(width * size / 256)))
    for layer in layers:
        for feature in layer.features:
            if feature.geom_type != 2:
                continue
            if keep is not None and not keep(feature):
                continue
            for line in feature.lines:
                points = _points(line, layer.extent, size)
                if _stroke(points):
                    pygame.draw.lines(surf, color, False, points, unit)


def _roads(surf, layers, size, view_zoom):
    if not layers:
        return
    strokes = []
    for layer in layers:
        for feature in layer.features:
            if feature.geom_type != 2:
                continue
            kind = _text(feature, "kind")
            detail = _text(feature, "kind_detail")
            if not road_kept(kind, detail, view_zoom):
                continue
            color, width, rank = road_paint(kind, detail, view_zoom)
            px = max(1, int(round(width * size / 256)))
            for line in feature.lines:
                points = _points(line, layer.extent, size)
                if _stroke(points):
                    strokes.append((rank, px, color, points))
    strokes.sort(key=lambda item: item[0])
    for _rank, px, color, points in strokes:
        pygame.draw.lines(surf, color, False, points, px)


def _borders(surf, layers, size, view_zoom):
    if not layers:
        return
    for layer in layers:
        for feature in layer.features:
            if feature.geom_type != 2:
                continue
            kind = _text(feature, "kind")
            if not boundary_kept(kind, view_zoom):
                continue
            px = max(1, int(round(size / 256)))
            color = BORDER if kind == "country" else BORDER_SOFT
            for line in feature.lines:
                points = _points(line, layer.extent, size)
                if _stroke(points):
                    pygame.draw.lines(surf, color, False, points, px)


def _places(layers, size, view_zoom, labels):
    if not layers:
        return
    for layer in layers:
        extent = layer.extent or 4096
        factor = size / extent
        for feature in layer.features:
            if not feature.points:
                continue
            kind = _text(feature, "kind")
            detail = _text(feature, "kind_detail") or kind
            minimum = _number(feature.props.get("min_zoom"))
            if not label_allowed(kind, detail, minimum, view_zoom):
                continue
            text = place_name(feature.props)
            if not text:
                continue
            x, y = feature.points[0]
            labels.append({
                "text": text,
                "x": x * factor,
                "y": y * factor,
                "size": label_size(kind, detail),
                "rank": label_rank(kind, detail, feature.props.get("population_rank")),
            })


def _polygon(surf, ring, extent, size, color):
    points = _points(ring, extent, size)
    if len(points) >= 3:
        pygame.draw.polygon(surf, color, points)


def _points(ring, extent, size):
    factor = size / (extent or 4096)
    limit = size * 2
    points = []
    last = None
    for x, y in ring:
        px = int(x * factor)
        py = int(y * factor)
        if px < -size:
            px = -size
        elif px > limit:
            px = limit
        if py < -size:
            py = -size
        elif py > limit:
            py = limit
        point = (px, py)
        if point != last:
            points.append(point)
            last = point
    return points


def _stroke(points):
    return len(points) >= 2 and any(point != points[0] for point in points[1:])


def _area(ring):
    total = 0
    count = len(ring)
    for index in range(count):
        x1, y1 = ring[index]
        x2, y2 = ring[(index + 1) % count]
        total += x1 * y2 - x2 * y1
    return total


def _text(feature, key):
    value = feature.props.get(key)
    if isinstance(value, str):
        return value
    return ""


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)
