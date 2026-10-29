"""Mise a jour du kiosque depuis le depot GitHub public."""

from __future__ import annotations

import os
import shutil
import subprocess
import tarfile
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from device.power import on_pi

# Depot public pousse depuis Windows. Surcharge possible : WORLD3_REPO=org/name
_DEFAULT_REPO = "quentinorh/world3"
_BRANCH = "main"
_UA = "WORLD3-kiosk/1.0"
_PROBE_EVERY = 45.0
_PROBE_TIMEOUT = 3.0

# Chemins locaux a ne jamais ecraser ni supprimer lors d'une maj.
_KEEP = frozenset({
    "save.json",
    "var",
    ".venv",
    ".git",
    "deploy/target.ps1",
})

# Etapes affichees sur le menu (id, libelle). Les bornes % sont inclusives a gauche.
# Telechargement puis une seule passe tar vers le dossier (pas d'extraction
# Python membre a membre + recopie, trop lente sur SD de Pi 3).
STEPS = (
    ("download", "TÉLÉCHARGEMENT", 0, 55),
    ("extract", "INSTALLATION", 55, 95),
    ("restart", "REDÉMARRAGE", 95, 100),
)

_lock = threading.Lock()
_state = {
    "online": False,
    "checked": 0.0,
    "busy": False,
    "result": None,  # None | "ok" | "fail"
    "detail": "",
    "step": "",
    "label": "",
    "percent": 0,
}
_probe_thread: threading.Thread | None = None


def repo_slug() -> str:
    return (os.environ.get("WORLD3_REPO") or _DEFAULT_REPO).strip() or _DEFAULT_REPO


def archive_url() -> str:
    return f"https://github.com/{repo_slug()}/archive/refs/heads/{_BRANCH}.tar.gz"


def online() -> bool:
    with _lock:
        return bool(_state["online"])


def busy() -> bool:
    with _lock:
        return bool(_state["busy"])


def progress():
    """Etat courant : step, label, percent, busy."""
    with _lock:
        return {
            "step": _state["step"],
            "label": _state["label"],
            "percent": int(_state["percent"]),
            "busy": bool(_state["busy"]),
        }


def set_step(step_id: str, fraction: float = 0.0):
    """fraction dans [0, 1] a l'interieur de l'etape."""
    fraction = max(0.0, min(1.0, float(fraction)))
    for sid, label, lo, hi in STEPS:
        if sid != step_id:
            continue
        percent = lo + (hi - lo) * fraction
        with _lock:
            _state["step"] = sid
            _state["label"] = label
            _state["percent"] = max(0, min(100, int(round(percent))))
        return
    with _lock:
        _state["step"] = step_id
        _state["label"] = step_id.upper()
        _state["percent"] = int(round(100 * fraction))


def take_result():
    """(result, detail) une fois, puis raz. result est 'ok', 'fail' ou None."""
    with _lock:
        result = _state["result"]
        detail = _state["detail"]
        _state["result"] = None
        _state["detail"] = ""
        return result, detail


def ensure_probe():
    """Lance le controle reseau periodique (une fois)."""
    global _probe_thread
    with _lock:
        if _probe_thread is not None and _probe_thread.is_alive():
            return
        _probe_thread = threading.Thread(
            target=_probe_loop, name="world3-online", daemon=True,
        )
        _probe_thread.start()


def _probe_loop():
    while True:
        flag = _ping()
        with _lock:
            _state["online"] = flag
            _state["checked"] = time.monotonic()
        time.sleep(_PROBE_EVERY)


def _ping() -> bool:
    url = f"https://github.com/{repo_slug()}"
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=_PROBE_TIMEOUT) as resp:
            return 200 <= getattr(resp, "status", 200) < 500
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError):
        try:
            req = urllib.request.Request(
                archive_url(), method="HEAD", headers={"User-Agent": _UA},
            )
            with urllib.request.urlopen(req, timeout=_PROBE_TIMEOUT) as resp:
                return 200 <= getattr(resp, "status", 200) < 500
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError):
            return False


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def start_update(root: Path | None = None):
    """Telecharge et applique en fond. Un seul essai a la fois."""
    with _lock:
        if _state["busy"]:
            return False
        _state["busy"] = True
        _state["result"] = None
        _state["detail"] = ""
        _state["step"] = "download"
        _state["label"] = "TÉLÉCHARGEMENT"
        _state["percent"] = 0
    target = Path(root) if root is not None else project_root()
    thread = threading.Thread(
        target=_run_update, args=(target,), name="world3-update", daemon=True,
    )
    thread.start()
    return True


def _run_update(root: Path):
    try:
        apply_update(root)
        set_step("restart", 0.0)
        with _lock:
            _state["result"] = "ok"
            _state["detail"] = ""
    except Exception as exc:
        with _lock:
            _state["result"] = "fail"
            _state["detail"] = str(exc)[:120]
    finally:
        with _lock:
            _state["busy"] = False


def apply_update(root: Path):
    """Installe l'archive GitHub dans root sans toucher save.json, var/, .venv."""
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    url = archive_url()
    with tempfile.TemporaryDirectory(prefix="world3-upd-") as tmp:
        archive = Path(tmp) / "src.tgz"
        set_step("download", 0.0)
        _download(url, archive)
        set_step("download", 1.0)
        set_step("extract", 0.0)
        _install_archive(archive, root)
        set_step("extract", 1.0)


def _download(url: str, dest: Path):
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=180) as resp, open(dest, "wb") as out:
        total = resp.headers.get("Content-Length")
        try:
            total_n = int(total) if total else 0
        except ValueError:
            total_n = 0
        done = 0
        last_report = -1
        while True:
            chunk = resp.read(256 * 1024)
            if not chunk:
                break
            out.write(chunk)
            done += len(chunk)
            if total_n > 0:
                frac = min(1.0, done / total_n)
                pct = int(frac * 100)
                if pct != last_report:
                    last_report = pct
                    set_step("download", frac)
            elif done > 0:
                soft = min(0.9, done / (8 * 1024 * 1024))
                set_step("download", soft)


def _install_archive(archive: Path, root: Path):
    """Une passe vers root. Preferer le tar systeme (beaucoup plus rapide sur Pi)."""
    if _install_with_tar(archive, root):
        return
    _install_with_python(archive, root)


def _tar_excludes():
    flags = []
    for name in sorted(_KEEP):
        flags.extend(["--exclude", name])
    return flags


def _install_with_tar(archive: Path, root: Path) -> bool:
    tar_bin = shutil.which("tar")
    if not tar_bin:
        return False
    # GitHub : world3-main/...  -> strip 1 composant.
    cmd = [
        tar_bin, "-xzf", str(archive),
        "-C", str(root),
        "--strip-components=1",
        *_tar_excludes(),
    ]
    try:
        done = subprocess.run(
            cmd, capture_output=True, timeout=600, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if done.returncode != 0:
        # Certains tar Windows n'ont pas les memes options : repli Python.
        return False
    if not (root / "main.py").is_file():
        return False
    set_step("extract", 1.0)
    return True


def _install_with_python(archive: Path, root: Path):
    """Repli : extractall une fois, puis copie (evite extract() membre a membre)."""
    with tempfile.TemporaryDirectory(prefix="world3-py-") as tmp:
        extracted = Path(tmp)
        set_step("extract", 0.15)
        _safe_extract(archive, extracted)
        set_step("extract", 0.55)
        source = _archive_root(extracted)
        _overlay(source, root)
        set_step("extract", 1.0)


def _safe_extract(archive: Path, dest: Path):
    dest = dest.resolve()
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar.getmembers():
            name = member.name.replace("\\", "/")
            if name.startswith("/") or ".." in Path(name).parts:
                raise RuntimeError(f"archive refusee : {name}")
            target = (dest / name).resolve()
            if not str(target).startswith(str(dest) + os.sep) and target != dest:
                raise RuntimeError(f"archive refusee : {name}")
        try:
            tar.extractall(dest, filter="data")
        except TypeError:
            tar.extractall(dest)


def _archive_root(extracted: Path) -> Path:
    children = [path for path in extracted.iterdir() if path.is_dir()]
    if len(children) == 1:
        return children[0]
    if (extracted / "main.py").is_file():
        return extracted
    raise RuntimeError("archive GitHub sans racine lisible")


def kept(rel: Path) -> bool:
    """True si ce chemin relatif ne doit pas etre ecrase."""
    parts = rel.parts
    if not parts:
        return False
    if parts[0] in _KEEP:
        return True
    joined = "/".join(parts)
    return joined in _KEEP


def _overlay(source: Path, root: Path):
    for path in source.rglob("*"):
        rel = path.relative_to(source)
        if kept(rel):
            continue
        target = root / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def restart_kiosk() -> bool:
    """Relance world3.service sur le Pi. Ailleurs : succes sans rien faire."""
    set_step("restart", 1.0)
    if not on_pi():
        return True
    sudo = shutil.which("sudo")
    systemctl = shutil.which("systemctl")
    if not sudo or not systemctl:
        return False
    try:
        done = subprocess.run(
            [sudo, "-n", systemctl, "restart", "world3"],
            timeout=20,
            capture_output=True,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return done.returncode == 0
