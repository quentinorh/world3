"""Construit relief/assets/dem.npz à partir d'ETOPO1.

La grille livrée fait 5 minutes d'arc. Le binaire NOAA, une minute,
reste dans var/etopo1/ et n'est pas versionné. Lancer depuis la racine :

    python -m relief.build_dem
"""

from __future__ import annotations

import sys
import urllib.request
import zipfile
from pathlib import Path

import numpy as np

from relief.dem import locate
from relief.spill import spill_map

# Surface des glaces, grille alignée sur les méridiens, entiers 16 bits.
_URL = (
    "https://www.ngdc.noaa.gov/mgg/global/relief/ETOPO1/data/"
    "ice_surface/grid_registered/binary/etopo1_ice_g_i2.zip"
)
_ROWS = 10801
_COLS = 21601
# Cinq échantillons d'une minute, puis la ligne du pôle Sud et la
# colonne +180°, qui répète le bord, sont laissées de côté.
_FACTOR = 5

# Mer fermée par un détroit plus étroit qu'une case, et le trait d'eau
# à abaisser pour la rouvrir. (latitude, longitude) en degrés.
_MERS = (
    ("Méditerranée", (38.0, 18.0), ((36.05, -5.80), (35.97, -5.45), (36.02, -5.00))),
    ("mer Rouge", (20.0, 38.5), ((12.70, 43.15), (12.58, 43.35), (12.45, 43.55))),
    ("Baltique", (58.5, 20.0), ((57.70, 10.70), (56.10, 11.30), (55.70, 12.70))),
    ("mer Noire", (43.5, 34.0), ((41.18, 29.12), (40.95, 28.90), (40.25, 26.45))),
)
_CASPIENNE = (41.0, 51.0)
_CREUX = -40


def main(argv=None) -> None:
    root = Path(__file__).resolve().parent.parent
    cache = root / "var" / "etopo1"
    dest = root / "relief" / "assets" / "dem.npz"
    cache.mkdir(parents=True, exist_ok=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    archive = cache / "etopo1_ice_g_i2.zip"
    _download(archive)
    elev = _reduce(_extract(archive, cache))
    spill = _with_straits(elev)
    _check(elev, spill)
    np.savez_compressed(dest, elev=elev, spill=spill)
    print(f"écrit {dest} ({dest.stat().st_size // (1024 * 1024)} Mo)")


def _download(archive: Path) -> None:
    if archive.exists() and archive.stat().st_size > 1_000_000:
        print(f"archive déjà là : {archive}")
        return
    print(f"téléchargement {_URL}")
    request = urllib.request.Request(_URL, headers={"User-Agent": "world3-relief"})
    temporary = archive.with_suffix(".zip.part")
    with urllib.request.urlopen(request, timeout=120) as response:
        total = int(response.headers.get("Content-Length") or 0)
        got = 0
        with temporary.open("wb") as out:
            while True:
                chunk = response.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
                got += len(chunk)
                if total:
                    print(f"\r{got * 100 // total} %", end="", flush=True)
    print()
    temporary.replace(archive)


def _extract(archive: Path, cache: Path) -> Path:
    with zipfile.ZipFile(archive) as bundle:
        names = [info.filename for info in bundle.infolist() if not info.is_dir()]
        binary = max(names, key=lambda name: bundle.getinfo(name).file_size)
        target = cache / Path(binary).name
        if not target.exists() or target.stat().st_size != bundle.getinfo(binary).file_size:
            print(f"extraction {binary}")
            bundle.extract(binary, cache)
            extracted = cache / binary
            if extracted != target:
                extracted.replace(target)
        return target


def _reduce(binary: Path) -> np.ndarray:
    count = _ROWS * _COLS
    size = binary.stat().st_size
    if size != count * 2:
        raise RuntimeError(f"taille inattendue pour ETOPO1 : {size} octets")
    # NOAA range ces entiers en grand boutien. On les ramène en natif.
    raw = np.fromfile(binary, dtype=">i2").astype(np.int16)
    if not _sane(raw):
        raw = np.fromfile(binary, dtype="<i2").astype(np.int16)
        if not _sane(raw):
            raise RuntimeError("ETOPO1 illisible : ni grand boutien, ni petit")
    grid = raw.reshape(_ROWS, _COLS)
    out_h = (_ROWS - 1) // _FACTOR
    out_w = (_COLS - 1) // _FACTOR
    elev = np.empty((out_h, out_w), dtype=np.int16)
    for row in range(out_h):
        block = grid[row * _FACTOR:(row + 1) * _FACTOR, : out_w * _FACTOR]
        means = block.astype(np.int32).reshape(_FACTOR, out_w, _FACTOR).mean(axis=(0, 2))
        elev[row] = np.rint(means).astype(np.int16)
        if row % 400 == 0:
            print(f"réduction {row}/{out_h}")
    print(f"grille {elev.shape[0]}×{elev.shape[1]}, {int(elev.min())} à {int(elev.max())} m")
    return elev


def _sane(raw: np.ndarray) -> bool:
    sample = raw[::97]
    low = int(sample.min())
    high = int(sample.max())
    return -12000 <= low <= -2000 and 2000 <= high <= 10000


def _with_straits(elev: np.ndarray) -> np.ndarray:
    spill = _connect(elev)
    closed = [sea for sea in _MERS if not _open(spill, sea[1])]
    if not closed:
        print("détroits ouverts")
        return spill
    for name, _point, line in closed:
        print(f"détroit fermé, on l'ouvre : {name}")
        _carve(elev, line)
    return _connect(elev)


def _connect(elev: np.ndarray) -> np.ndarray:
    print("connexion à l'océan")

    def progress(done: int, count: int) -> None:
        print(f"\r{done * 100 // count} %", end="", flush=True)

    spill = spill_map(elev, progress=progress)
    print()
    return spill


def _open(spill: np.ndarray, point) -> bool:
    row, col = locate(point[0], point[1], spill.shape[0], spill.shape[1])
    return int(spill[row, col]) <= 0


def _carve(elev: np.ndarray, line) -> None:
    height, width = elev.shape
    cells = []
    for start, end in zip(line, line[1:]):
        cells.extend(_segment(start, end, height, width))
    if len(line) == 1:
        cells.append(locate(line[0][0], line[0][1], height, width))
    rows = []
    cols = []
    for row, col in cells:
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                yy = row + dy
                if yy < 0 or yy >= height:
                    continue
                rows.append(yy)
                cols.append((col + dx) % width)
    elev[rows, cols] = np.minimum(elev[rows, cols], _CREUX)


def _segment(start, end, height, width):
    r0, c0 = locate(start[0], start[1], height, width)
    r1, c1 = locate(end[0], end[1], height, width)
    steps = max(abs(r1 - r0), abs(c1 - c0), 1)
    rows = np.rint(np.linspace(r0, r1, steps + 1)).astype(np.int32)
    # La longitude peut passer par le méridien opposé : le segment reste court.
    cols = np.rint(np.linspace(c0, c1, steps + 1)).astype(np.int32) % width
    return list(zip(rows.tolist(), cols.tolist()))


def _check(elev: np.ndarray, spill: np.ndarray) -> None:
    wet = spill <= 0
    part = float(wet.mean())
    print(f"océan à 0 m : {part:.3f}")
    if not 0.65 <= part <= 0.75:
        raise RuntimeError(f"part d'océan inattendue : {part:.3f}")
    for name, point, _line in _MERS:
        row, col = locate(point[0], point[1], spill.shape[0], spill.shape[1])
        level = int(spill[row, col])
        ground = int(elev[row, col])
        print(f"{name} : sol {ground} m, seuil {level} m")
        if level > 0:
            raise RuntimeError(f"{name} encore fermée")
    row, col = locate(_CASPIENNE[0], _CASPIENNE[1], spill.shape[0], spill.shape[1])
    level = int(spill[row, col])
    ground = int(elev[row, col])
    print(f"Caspienne : sol {ground} m, seuil {level} m")
    if level <= 0 or ground >= 0:
        raise RuntimeError("la Caspienne devrait rester une cuvette sèche à 0 m")


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt:
        print("\ninterrompu")
        sys.exit(1)
