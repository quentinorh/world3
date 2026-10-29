"""Seuil où une case rejoint l'océan.

Une case basse n'est pas noyée pour autant : il faut un chemin jusqu'au
point le plus profond, dont chaque pas reste sous le niveau choisi. Le
seuil d'une case est le plus bas niveau qui ouvre un tel chemin. Une
cuvette derrière un col prend le niveau du col, pas le fond.
"""

from __future__ import annotations

import array

import numpy as np

# Valeur impossible pour une altitude ETOPO. Une case encore à ce
# nombre n'a pas été rattachée.
_VIDE = -32768


def spill_map(elev: np.ndarray, progress=None) -> np.ndarray:
    """Niveau de mer, en mètres, où chaque case rejoint le point le plus bas.

    `elev` est en mètres, entier, nord en haut. La longitude se referme.
    Huit voisins : un détroit en diagonale reste ouvert. Le point le
    plus bas amorce l'océan (la fosse, sur la grille mondiale).
    """
    if elev.ndim != 2:
        raise ValueError("la grille d'altitude doit être à deux dimensions")
    height, width = elev.shape
    values = np.ascontiguousarray(elev, dtype=np.int16).ravel()
    count = int(values.size)
    if count == 0:
        return values.reshape(elev.shape).copy()
    if array.array("i").itemsize != 4 or array.array("h").itemsize != 2:
        raise RuntimeError("entiers natifs inattendus")

    order = np.argsort(values, kind="mergesort").astype(np.int32, copy=False)
    # Tableaux C : l'indexation d'un scalaire numpy domine, et la carte
    # des voisins ne tient pas dans le cache.
    levels = array.array("h", values.tobytes())
    sequence = array.array("i", order.tobytes())
    parent = array.array("i", np.arange(count, dtype=np.int32).tobytes())
    nxt = array.array("i", np.full(count, -1, dtype=np.int32).tobytes())
    head = array.array("i", parent)
    tail = array.array("i", parent)
    ocean = bytearray(count)
    seen = bytearray(count)
    out = array.array("h", np.full(count, _VIDE, dtype=np.int16).tobytes())

    def find(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def pour(root: int, level: int) -> None:
        node = head[root]
        while node != -1:
            out[node] = level
            node = nxt[node]
        ocean[root] = 1

    step = max(count // 8, 1)
    for done in range(count):
        if progress is not None and done % step == 0:
            progress(done, count)
        idx = sequence[done]
        level = levels[idx]
        seen[idx] = 1
        y, x = divmod(idx, width)
        wet = [-1] * 8
        dry = [-1] * 8
        nw = nd = 0
        y0 = y - 1
        y1 = y + 1
        for yy, base_ok in ((y0, y0 >= 0), (y, True), (y1, y1 < height)):
            if not base_ok:
                continue
            base = yy * width
            x0 = (x - 1) % width
            x1 = (x + 1) % width
            candidates = (
                (base + x0, True),
                (base + x, yy != y),
                (base + x1, True),
            )
            for nb, keep in candidates:
                if not keep or not seen[nb]:
                    continue
                root = find(nb)
                if ocean[root]:
                    wet[nw] = root
                    nw += 1
                else:
                    dry[nd] = root
                    nd += 1
        if done == 0 or nw:
            out[idx] = level
            ocean[idx] = 1
            root = idx
            for slot in range(nw):
                other = find(wet[slot])
                if other != root:
                    parent[other] = root
            for slot in range(nd):
                other = find(dry[slot])
                if other == root or ocean[other]:
                    continue
                pour(other, level)
                parent[other] = root
            continue
        root = idx
        for slot in range(nd):
            other = find(dry[slot])
            if other == root:
                continue
            nxt[tail[root]] = head[other]
            tail[root] = tail[other]
            parent[other] = root

    if progress is not None:
        progress(count, count)
    result = np.frombuffer(out, dtype=np.int16).copy()
    if np.any(result == _VIDE):
        raise RuntimeError("une case n'a pas rejoint l'océan")
    return result.reshape(elev.shape)
