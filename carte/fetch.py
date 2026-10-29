"""Prepare la Terre entiere : zooms 0 a 12, environ 4 Go.

A lancer sur l'ordinateur, pas sur le Pi. Le Pi n'a ni la memoire ni
la place pour le fichier planete complet (environ 120 Go).

    python -m carte.fetch

Puis le deploiement copie var/carte/terre.pmtiles s'il est deja la.
"""

from __future__ import annotations

import argparse
import io
import json
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.error
import urllib.request
import zipfile
from datetime import date, timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_ARCHIVE = _ROOT / "var" / "carte" / "terre.pmtiles"
_BIN = _ROOT / "var" / "carte" / "bin"
_RELEASES = "https://api.github.com/repos/protomaps/go-pmtiles/releases/latest"
_USER_AGENT = "world3-carte"
_HEAVY = 6_000_000_000


def main(argv=None):
    parser = argparse.ArgumentParser(description="Telecharge la Terre OpenStreetMap, zooms 0 a 12.")
    parser.add_argument("--url", help="Archive PMTiles du jour. Sinon, le dernier build Protomaps.")
    parser.add_argument("--maxzoom", type=int, default=12)
    parser.add_argument("--dest", type=Path, default=_ARCHIVE)
    args = parser.parse_args(argv)
    if not 0 <= args.maxzoom <= 14:
        raise SystemExit("Le zoom doit etre entre 0 et 14.")
    dest = args.dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = args.url or latest_build_url()
    print(f"Carte : build {url}", flush=True)
    cli = ensure_cli()
    part = dest.with_name(dest.name + ".part")
    if part.exists():
        part.unlink()
    print(
        f"Carte : extraction des zooms 0 a {args.maxzoom}. Cela peut prendre longtemps.",
        flush=True,
    )
    try:
        subprocess.run(
            [str(cli), "extract", url, str(part), f"--maxzoom={args.maxzoom}"],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        if part.exists():
            part.unlink()
        raise SystemExit(f"pmtiles extract a echoue ({exc.returncode}).") from exc
    if not part.is_file() or part.stat().st_size == 0:
        raise SystemExit("pmtiles extract n'a rien ecrit.")
    part.replace(dest)
    size = dest.stat().st_size
    print(f"Carte : {size / 1e9:.1f} Go dans {dest}", flush=True)
    if size > _HEAVY:
        print(
            "Carte : fichier lourd. Relancer avec --maxzoom 11 le reduit environ de moitie.",
            flush=True,
        )


def recent_build_urls(day, count=21):
    return [
        f"https://build.protomaps.com/{(day - timedelta(days=i)).strftime('%Y%m%d')}.pmtiles"
        for i in range(count)
    ]


def latest_build_url(today=None, days=21):
    today = today or date.today()
    for url in recent_build_urls(today, days):
        if _url_exists(url):
            return url
    raise SystemExit("Aucun build Protomaps sur les trois dernieres semaines.")


def asset_token(system, machine):
    machine = machine.lower()
    if machine in ("armv7l", "armv6l", "armv7", "arm"):
        raise ValueError("Le Pi ne prepare pas la carte. Lancez python -m carte.fetch sur l'ordinateur.")
    arm64 = machine in ("arm64", "aarch64")
    if system == "Windows":
        return "Windows_arm64" if arm64 else "Windows_x86_64"
    if system == "Darwin":
        return "Darwin_arm64" if arm64 else "Darwin_x86_64"
    return "Linux_arm64" if arm64 else "Linux_x86_64"


def choose_asset(assets, token):
    for asset in assets:
        name = asset.get("name") or ""
        if token in name:
            return asset
    return None


def ensure_cli():
    binary = _BIN / ("pmtiles.exe" if platform.system() == "Windows" else "pmtiles")
    if binary.is_file():
        return binary
    token = asset_token(platform.system(), platform.machine())
    print("Carte : telechargement de l'outil pmtiles.", flush=True)
    release = _json(_RELEASES)
    asset = choose_asset(release.get("assets") or [], token)
    if asset is None:
        raise SystemExit(f"Pas de binaire pmtiles pour {token}.")
    _BIN.mkdir(parents=True, exist_ok=True)
    archive = _BIN / asset["name"]
    _download(asset["browser_download_url"], archive)
    _extract_binary(archive, binary)
    archive.unlink()
    return binary


def _extract_binary(archive, binary):
    want = binary.name
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as bundle:
            member = _member(bundle.namelist(), want)
            if member is None:
                raise SystemExit(f"{want} absent de {archive.name}.")
            binary.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(member) as source, binary.open("wb") as target:
                shutil.copyfileobj(source, target)
    else:
        with tarfile.open(archive, "r:*") as bundle:
            member = _member(bundle.getnames(), want)
            if member is None:
                raise SystemExit(f"{want} absent de {archive.name}.")
            extracted = bundle.extractfile(member)
            if extracted is None:
                raise SystemExit(f"Impossible de lire {want}.")
            with extracted, binary.open("wb") as target:
                shutil.copyfileobj(extracted, target)
    if platform.system() != "Windows":
        binary.chmod(0o755)


def _member(names, want):
    for name in names:
        parts = name.replace("\\", "/").split("/")
        if ".." in parts:
            continue
        if parts[-1] == want:
            return name
    return None


def _url_exists(url):
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return 200 <= response.status < 300
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 405):
            return _range_exists(url)
        return False
    except urllib.error.URLError:
        return False


def _range_exists(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": _USER_AGENT, "Range": "bytes=0-0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status in (200, 206)
    except urllib.error.HTTPError as exc:
        return exc.code in (200, 206)
    except urllib.error.URLError:
        return False


def _json(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": _USER_AGENT, "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(io.TextIOWrapper(response, encoding="utf-8"))


def _download(url, dest):
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=180) as response, dest.open("wb") as target:
        shutil.copyfileobj(response, target)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
