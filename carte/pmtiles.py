"""Lecture d'une archive PMTiles v3, sans charger tout le repertoire.

Le fichier de la Terre fait plusieurs gigaoctets. On ne garde en memoire
que l'en-tete et quelques repertoires (la racine, puis une feuille).
"""

from __future__ import annotations

import gzip
import struct
from collections import OrderedDict
from pathlib import Path

NONE = 1
GZIP = 2
MVT = 1

_HEADER = struct.Struct("<7sB11Q6B4iB2i")
_DIR_CACHE = 12


def zxy_to_tileid(z, x, y):
    """Identifiant de Hilbert utilise par PMTiles."""
    if z == 0:
        return 0
    if z > 26:
        raise ValueError("zoom trop haut")
    if x < 0 or y < 0 or x >= (1 << z) or y >= (1 << z):
        raise ValueError("tuile hors du zoom")
    acc = ((1 << (2 * z)) - 1) // 3
    a = z - 1
    tx, ty = x, y
    s = 1 << a
    while s > 0:
        rx = tx & s
        ry = ty & s
        acc += ((3 * rx) ^ ry) << a
        tx, ty = _rotate(s, tx, ty, rx, ry)
        a -= 1
        s >>= 1
    return acc


def tileid_to_zxy(tile_id):
    z = ((3 * tile_id + 1).bit_length() - 1) >> 1
    acc = ((1 << (2 * z)) - 1) // 3
    t = tile_id - acc
    x = 0
    y = 0
    n = 1 << z
    s = 1
    while s < n:
        rx = s & (t // 2)
        ry = s & (t ^ rx)
        x, y = _rotate(s, x, y, rx, ry)
        t //= 2
        x += rx
        y += ry
        s <<= 1
    return z, x, y


def _rotate(n, x, y, rx, ry):
    if ry == 0:
        if rx != 0:
            return n - 1 - y, n - 1 - x
        return y, x
    return x, y


def find_entry(entries, tile_id):
    """Plus grande entree dont l'identifiant est <= tile_id, si elle le couvre."""
    lo = 0
    hi = len(entries) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        current = entries[mid][0]
        if tile_id > current:
            lo = mid + 1
        elif tile_id < current:
            hi = mid - 1
        else:
            return entries[mid]
    if hi < 0:
        return None
    tid, _offset, _length, run = entries[hi]
    if run == 0 or tile_id - tid < run:
        return entries[hi]
    return None


def parse_directory(data, compression):
    """Entrees (tile_id, offset, length, run_length), deja triees."""
    if compression == GZIP:
        data = gzip.decompress(data)
    elif compression not in (NONE, 0):
        raise ValueError(f"compression interne {compression} non prise en charge")
    reader = _Reader(data)
    count = reader.varint()
    ids = []
    last = 0
    for _ in range(count):
        last += reader.varint()
        ids.append(last)
    runs = [reader.varint() for _ in range(count)]
    lengths = [reader.varint() for _ in range(count)]
    entries = []
    for i in range(count):
        raw = reader.varint()
        if i > 0 and raw == 0:
            prev = entries[-1]
            offset = prev[1] + prev[2]
        else:
            offset = raw - 1
        entries.append((ids[i], offset, lengths[i], runs[i]))
    return entries


def serialize_directory(entries, compression=GZIP):
    raw = bytearray()
    _write_varint(raw, len(entries))
    last = 0
    for tile_id, _offset, _length, _run in entries:
        _write_varint(raw, tile_id - last)
        last = tile_id
    for _tile_id, _offset, _length, run in entries:
        _write_varint(raw, run)
    for _tile_id, _offset, length, _run in entries:
        _write_varint(raw, length)
    previous = None
    for tile_id, offset, length, _run in entries:
        if previous is not None and offset == previous[0] + previous[1]:
            _write_varint(raw, 0)
        else:
            _write_varint(raw, offset + 1)
        previous = (offset, length)
    blob = bytes(raw)
    if compression == GZIP:
        return gzip.compress(blob)
    if compression in (NONE, 0):
        return blob
    raise ValueError(f"compression interne {compression} non prise en charge")


class Header:
    def __init__(self, fields):
        self.root_offset = fields[0]
        self.root_length = fields[1]
        self.metadata_offset = fields[2]
        self.metadata_length = fields[3]
        self.leaf_offset = fields[4]
        self.leaf_length = fields[5]
        self.tile_offset = fields[6]
        self.tile_length = fields[7]
        self.addressed = fields[8]
        self.entries = fields[9]
        self.contents = fields[10]
        self.clustered = fields[11] == 1
        self.internal_compression = fields[12]
        self.tile_compression = fields[13]
        self.tile_type = fields[14]
        self.min_zoom = fields[15]
        self.max_zoom = fields[16]


def read_header(data):
    if len(data) < 127 or data[:7] != b"PMTiles":
        raise ValueError("pas une archive PMTiles")
    unpacked = _HEADER.unpack_from(data)
    if unpacked[1] != 3:
        raise ValueError(f"version {unpacked[1]} non prise en charge")
    return Header(unpacked[2:])


class Archive:
    def __init__(self, path):
        self.path = Path(path)
        self._fh = self.path.open("rb")
        try:
            self.header = read_header(self._fh.read(127))
        except Exception:
            self._fh.close()
            raise
        self._dirs = OrderedDict()

    def close(self):
        self._fh.close()

    def tile(self, z, x, y):
        """Octets de la tuile, deja decompresses, ou None."""
        entry = self._lookup(zxy_to_tileid(z, x, y), self.header.root_offset, self.header.root_length, 0)
        if entry is None or entry[3] == 0:
            return None
        _tid, offset, length, _run = entry
        if length <= 0:
            return None
        self._fh.seek(self.header.tile_offset + offset)
        blob = self._fh.read(length)
        if len(blob) != length:
            raise ValueError("tuile tronquee")
        return _decompress(blob, self.header.tile_compression)

    def _lookup(self, tile_id, offset, length, depth):
        if depth > 4:
            return None
        entry = find_entry(self._directory(offset, length), tile_id)
        if entry is None:
            return None
        if entry[3] > 0:
            return entry
        return self._lookup(tile_id, self.header.leaf_offset + entry[1], entry[2], depth + 1)

    def _directory(self, offset, length):
        key = (offset, length)
        cached = self._dirs.get(key)
        if cached is not None:
            self._dirs.move_to_end(key)
            return cached
        self._fh.seek(offset)
        raw = self._fh.read(length)
        if len(raw) != length:
            raise ValueError("repertoire tronque")
        entries = parse_directory(raw, self.header.internal_compression)
        self._dirs[key] = entries
        if len(self._dirs) > _DIR_CACHE:
            self._dirs.popitem(last=False)
        return entries


def write_archive(path, tiles, leaf_size=0):
    """Ecrit une petite archive gzippee. Sert aux essais.

    tiles : (z, x, y, octets MVT bruts). leaf_size > 0 force des feuilles,
    pour verifier qu'on ne charge pas tout le repertoire d'un coup.
    """
    ordered = sorted(tiles, key=lambda item: zxy_to_tileid(item[0], item[1], item[2]))
    blobs = []
    entries = []
    cursor = 0
    min_zoom = 0
    max_zoom = 0
    for index, (z, x, y, payload) in enumerate(ordered):
        blob = gzip.compress(payload)
        if index == 0:
            min_zoom = max_zoom = z
        else:
            min_zoom = min(min_zoom, z)
            max_zoom = max(max_zoom, z)
        entries.append((zxy_to_tileid(z, x, y), cursor, len(blob), 1))
        blobs.append(blob)
        cursor += len(blob)
    if leaf_size and entries:
        leaves = bytearray()
        root_entries = []
        for start in range(0, len(entries), leaf_size):
            chunk = entries[start:start + leaf_size]
            raw = serialize_directory(chunk, GZIP)
            root_entries.append((chunk[0][0], len(leaves), len(raw), 0))
            leaves.extend(raw)
        root = serialize_directory(root_entries, GZIP)
        leaf_bytes = bytes(leaves)
    else:
        root = serialize_directory(entries, GZIP)
        leaf_bytes = b""
    meta = gzip.compress(b"{}")
    root_offset = 127
    meta_offset = root_offset + len(root)
    leaf_offset = meta_offset + len(meta)
    tile_offset = leaf_offset + len(leaf_bytes)
    header = _HEADER.pack(
        b"PMTiles",
        3,
        root_offset,
        len(root),
        meta_offset,
        len(meta),
        leaf_offset,
        len(leaf_bytes),
        tile_offset,
        cursor,
        len(entries),
        len(entries),
        len(entries),
        1,
        GZIP,
        GZIP,
        MVT,
        min_zoom,
        max_zoom,
        -1800000000,
        -850511287,
        1800000000,
        850511287,
        2,
        0,
        0,
    )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(header)
        handle.write(root)
        handle.write(meta)
        handle.write(leaf_bytes)
        for blob in blobs:
            handle.write(blob)


class _Reader:
    def __init__(self, data):
        self.data = data
        self.i = 0

    def varint(self):
        number, self.i = _read_varint(self.data, self.i)
        return number


def _read_varint(data, index):
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


def _write_varint(raw, number):
    if number < 0:
        raise ValueError("varint negatif")
    while number >= 0x80:
        raw.append((number & 0x7F) | 0x80)
        number >>= 7
    raw.append(number)


def _decompress(data, compression):
    if compression == GZIP:
        return gzip.decompress(data)
    if compression in (NONE, 0):
        return data
    raise ValueError(f"compression de tuile {compression} non prise en charge")
