"""Mise a jour du kiosque depuis le depot GitHub public."""

from __future__ import annotations

import json
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
# Taille typique de l'archive (dem.npz inclus) pour la barre sans Content-Length.
_ARCHIVE_HINT = 24 * 1024 * 1024
_REVISION = ".world3-revision"

# Chemins locaux a ne jamais ecraser ni supprimer lors d'une maj.
_KEEP = frozenset({
    "save.json",
    "var",
    ".venv",
    ".git",
    "deploy/target.ps1",
    _REVISION,
})

# Etapes affichees sur le menu (id, libelle). Les bornes % sont inclusives a gauche.
STEPS = (
    ("download", "TÉLÉCHARGEMENT", 0, 70),
    ("extract", "INSTALLATION", 70, 95),
    ("restart", "REDÉMARRAGE", 95, 100),
)

_lock = threading.Lock()
_state = {
    "online": False,
    "checked": 0.0,
    "busy": False,
    "result": None,  # None | "ok" | "same" | "fail"
    "detail": "",
    "step": "",
    "label": "",
    "percent": 0,
}
_probe_thread: threading.Thread | None = None


def repo_slug() -> str:
    return (os.environ.get("WORLD3_REPO") or _DEFAULT_REPO).strip() or _DEFAULT_REPO


def archive_url() -> str:
    # codeload : evite la redirection github.com et marche mieux avec curl.
    return f"https://codeload.github.com/{repo_slug()}/tar.gz/refs/heads/{_BRANCH}"


def commits_api_url() -> str:
    return f"https://api.github.com/repos/{repo_slug()}/commits/{_BRANCH}"


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
    """(result, detail) une fois, puis raz. result : 'ok', 'same', 'fail' ou None."""
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
    try:
        req = urllib.request.Request(
            commits_api_url(),
            headers={"User-Agent": _UA, "Accept": "application/vnd.github+json"},
        )
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


def revision_path(root: Path) -> Path:
    return Path(root) / _REVISION


def read_revision(root: Path) -> str:
    path = revision_path(root)
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def write_revision(root: Path, sha: str):
    try:
        revision_path(root).write_text(sha.strip() + "\n", encoding="utf-8")
    except OSError:
        pass


def remote_revision() -> str:
    """SHA du bout de main, ou chaine vide si indisponible."""
    req = urllib.request.Request(
        commits_api_url(),
        headers={"User-Agent": _UA, "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=12) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return str(data.get("sha") or "").strip()


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
        status = apply_update(root)
        set_step("restart", 0.0)
        with _lock:
            _state["result"] = status
            _state["detail"] = ""
    except Exception as exc:
        with _lock:
            _state["result"] = "fail"
            _state["detail"] = str(exc)[:120]
    finally:
        with _lock:
            _state["busy"] = False


def apply_update(root: Path) -> str:
    """Installe l'archive. Retourne 'ok' ou 'same' (deja a jour)."""
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    set_step("download", 0.0)
    try:
        remote = remote_revision()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        remote = ""
    if remote and remote == read_revision(root):
        set_step("download", 1.0)
        set_step("extract", 1.0)
        return "same"
    with tempfile.TemporaryDirectory(prefix="world3-upd-") as tmp:
        archive = Path(tmp) / "src.tgz"
        _download(archive_url(), archive)
        set_step("download", 1.0)
        set_step("extract", 0.0)
        _install_archive(archive, root)
        set_step("extract", 1.0)
    if remote:
        write_revision(root, remote)
    return "ok"


def _download(url: str, dest: Path):
    if _download_with_curl(url, dest):
        return
    _download_with_urllib(url, dest)


def _download_with_curl(url: str, dest: Path) -> bool:
    curl = shutil.which("curl")
    if not curl:
        return False
    cmd = [
        curl, "-L", "--fail", "--retry", "3", "--retry-delay", "2",
        "--connect-timeout", "20", "--max-time", "600",
        "-A", _UA, "-o", str(dest), url,
    ]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        return False
    last = -1
    while proc.poll() is None:
        size = dest.stat().st_size if dest.is_file() else 0
        frac = _download_fraction(size, 0)
        pct = int(frac * 100)
        if pct != last:
            last = pct
            set_step("download", frac)
        time.sleep(0.25)
    if proc.returncode != 0 or not dest.is_file() or dest.stat().st_size < 1024:
        try:
            dest.unlink()
        except OSError:
            pass
        return False
    set_step("download", 1.0)
    return True


def _download_with_urllib(url: str, dest: Path):
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as out:
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
            frac = _download_fraction(done, total_n)
            pct = int(frac * 100)
            if pct != last_report:
                last_report = pct
                set_step("download", frac)


def _download_fraction(done: int, total: int) -> float:
    """Progression honnete : ne plafonne plus a 50 % sans Content-Length."""
    if total > 0:
        return min(0.99, done / total)
    # Sans taille : asymptote vers 99 %, basee sur ~24 Mo typiques.
    return min(0.99, done / float(_ARCHIVE_HINT))


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
        return False
    if not (root / "main.py").is_file():
        return False
    set_step("extract", 1.0)
    return True


def _install_with_python(archive: Path, root: Path):
    """Repli : extractall une fois, puis copie."""
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
