"""Decodeur Mapbox Vector Tile, assez pour dessiner une tuile.

Pas de bibliotheque protobuf : le format des tuiles n'utilise qu'une
poignee de types, et le Pi n'a pas de dependance en plus.
"""

from __future__ import annotations

import struct

# Couches lourdes, illisibles sur la dalle. On saute leur contenu.
SKIP_LAYERS = frozenset({"buildings", "pois", "transit", "addresses"})


class Layer:
    def __init__(self, name, extent, features):
        self.name = name
        self.extent = extent or 4096
        self.features = features


class Feature:
    def __init__(self, geom_type, props, points, lines, rings):
        self.geom_type = geom_type
        self.props = props
        self.points = points
        self.lines = lines
        self.rings = rings


def decode_tile(data):
    layers = []
    index = 0
    while index < len(data):
        key, index = _varint(data, index)
        field, wire = key >> 3, key & 7
        if field == 3 and wire == 2:
            blob, index = _take(data, index)
            layer = _layer(blob)
            if layer.name not in SKIP_LAYERS:
                layers.append(layer)
            continue
        index = _skip(data, index, wire)
    return layers


def _layer(data):
    name = ""
    extent = 4096
    raw_features = []
    keys = []
    values = []
    index = 0
    while index < len(data):
        key, index = _varint(data, index)
        field, wire = key >> 3, key & 7
        if field == 1 and wire == 2:
            blob, index = _take(data, index)
            name = blob.decode("utf-8", "replace")
        elif field == 2 and wire == 2:
            if name in SKIP_LAYERS:
                index = _skip(data, index, 2)
            else:
                blob, index = _take(data, index)
                raw_features.append(blob)
        elif field == 3 and wire == 2:
            blob, index = _take(data, index)
            keys.append(blob.decode("utf-8", "replace"))
        elif field == 4 and wire == 2:
            blob, index = _take(data, index)
            values.append(_value(blob))
        elif field == 5 and wire == 0:
            extent, index = _varint(data, index)
        elif field == 15 and wire == 0:
            _version, index = _varint(data, index)
        else:
            index = _skip(data, index, wire)
    if name in SKIP_LAYERS:
        return Layer(name, extent, [])
    features = [_feature(blob, keys, values) for blob in raw_features]
    return Layer(name, extent, features)


def _feature(data, keys, values):
    geom_type = 0
    tags = []
    geometry = []
    index = 0
    while index < len(data):
        key, index = _varint(data, index)
        field, wire = key >> 3, key & 7
        if field == 2 and wire == 2:
            blob, index = _take(data, index)
            tags.extend(_packed(blob))
        elif field == 2 and wire == 0:
            tag, index = _varint(data, index)
            tags.append(tag)
        elif field == 3 and wire == 0:
            geom_type, index = _varint(data, index)
        elif field == 4 and wire == 2:
            blob, index = _take(data, index)
            geometry.extend(_packed(blob))
        elif field == 4 and wire == 0:
            word, index = _varint(data, index)
            geometry.append(word)
        else:
            index = _skip(data, index, wire)
    props = {}
    for cursor in range(0, len(tags) - 1, 2):
        key_index = tags[cursor]
        value_index = tags[cursor + 1]
        if key_index < len(keys) and value_index < len(values):
            props[keys[key_index]] = values[value_index]
    points, lines, rings = _geometry(geometry, geom_type)
    return Feature(geom_type, props, points, lines, rings)


def _geometry(words, geom_type):
    x = 0
    y = 0
    parts = []
    index = 0
    count_words = len(words)
    while index < count_words:
        command = words[index]
        index += 1
        op = command & 7
        count = command >> 3
        if op == 1:
            for _ in range(count):
                if index + 1 >= count_words:
                    break
                x += _zigzag(words[index])
                y += _zigzag(words[index + 1])
                index += 2
                parts.append([(x, y)])
        elif op == 2:
            if not parts:
                parts.append([])
            for _ in range(count):
                if index + 1 >= count_words:
                    break
                x += _zigzag(words[index])
                y += _zigzag(words[index + 1])
                index += 2
                parts[-1].append((x, y))
        elif op == 7:
            # ClosePath. Le numero n'est pas 3 : c'est 7 dans la spec.
            continue
        else:
            break
    if geom_type == 1:
        return [point for part in parts for point in part], [], []
    if geom_type == 2:
        return [], [part for part in parts if len(part) >= 2], []
    return [], [], [part for part in parts if len(part) >= 3]


def _value(data):
    found = None
    index = 0
    while index < len(data):
        key, index = _varint(data, index)
        field, wire = key >> 3, key & 7
        if field == 1 and wire == 2:
            blob, index = _take(data, index)
            found = blob.decode("utf-8", "replace")
        elif field == 2 and wire == 5:
            found = struct.unpack_from("<f", data, index)[0]
            index += 4
        elif field == 3 and wire == 1:
            found = struct.unpack_from("<d", data, index)[0]
            index += 8
        elif field == 4 and wire == 0:
            found, index = _varint(data, index)
            if found >= 2**63:
                found -= 2**64
        elif field == 5 and wire == 0:
            found, index = _varint(data, index)
        elif field == 6 and wire == 0:
            number, index = _varint(data, index)
            found = (number >> 1) ^ -(number & 1)
        elif field == 7 and wire == 0:
            number, index = _varint(data, index)
            found = bool(number)
        else:
            index = _skip(data, index, wire)
    return found


def _packed(data):
    values = []
    index = 0
    while index < len(data):
        number, index = _varint(data, index)
        values.append(number)
    return values


def _zigzag(number):
    return (number >> 1) ^ -(number & 1)


def _take(data, index):
    length, index = _varint(data, index)
    end = index + length
    if end > len(data):
        raise ValueError("champ tronque")
    return data[index:end], end


def _varint(data, index):
    number = 0
    shift = 0
    while True:
        if index >= len(data):
            raise ValueError("varint tronque")
        byte = data[index]
        index += 1
        number |= (byte & 0x7F) << shift
        if byte < 0x80:
            return number, index
        shift += 7
        if shift > 63:
            raise ValueError("varint trop long")


def _skip(data, index, wire):
    if wire == 0:
        _number, index = _varint(data, index)
        return index
    if wire == 1:
        return index + 8
    if wire == 2:
        length, index = _varint(data, index)
        end = index + length
        if end > len(data):
            raise ValueError("champ tronque")
        return end
    if wire == 5:
        return index + 4
    raise ValueError(f"type protobuf {wire}")
