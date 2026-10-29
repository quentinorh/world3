"""Mise a jour GitHub : chemins conserves, extraction sure. Sans reseau."""

from __future__ import annotations

import io
import os
import tarfile
import tempfile
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from kiosk.update import (
    STEPS,
    _download_fraction,
    apply_update,
    archive_url,
    kept,
    progress,
    project_root,
    repo_slug,
    set_step,
)


def _tarball(files: dict[str, bytes], root_name="world3-main") -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(f"{root_name}/{name}")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        info = tarfile.TarInfo(f"{root_name}/dossier")
        info.type = tarfile.DIRTYPE
        tar.addfile(info)
    return buf.getvalue()


def test_repo_et_garde():
    assert "/" in repo_slug()
    assert "codeload.github.com" in archive_url()
    assert archive_url().endswith("/main")
    assert kept(Path("save.json"))
    assert kept(Path("var/carte/terre.pmtiles"))
    assert kept(Path(".venv/bin/python"))
    assert kept(Path("deploy/target.ps1"))
    assert not kept(Path("kiosk/app.py"))
    assert not kept(Path("contenu.json"))
    assert len(STEPS) == 3
    set_step("download", 0.5)
    info = progress()
    assert info["step"] == "download"
    assert info["label"] == "TÉLÉCHARGEMENT"
    assert 30 <= info["percent"] <= 40
    set_step("extract", 1.0)
    assert progress()["percent"] == 95
    # Sans Content-Length, ne plus plafonner a ~50 % des 8 premiers Mo.
    assert _download_fraction(8 * 1024 * 1024, 0) < 0.45
    assert _download_fraction(24 * 1024 * 1024, 0) >= 0.99


def test_overlay_conserve_locaux(monkeypatch=None):
    payload = _tarball({
        "main.py": b"NEW\n",
        "kiosk/app.py": b"# maj\n",
        "save.json": b"NE_PAS_PRENDRE\n",
    })
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "world3"
        root.mkdir()
        (root / "save.json").write_text("PARTIE\n", encoding="utf-8")
        (root / "var").mkdir()
        (root / "var" / "keep.txt").write_text("ok\n", encoding="utf-8")
        (root / "main.py").write_text("OLD\n", encoding="utf-8")
        archive = Path(tmp) / "src.tgz"
        archive.write_bytes(payload)

        import kiosk.update as upd

        def fake_download(url, dest):
            dest.write_bytes(archive.read_bytes())

        old_dl = upd._download
        old_tar = upd._install_with_tar
        old_remote = upd.remote_revision
        upd._download = fake_download
        # Forcer le repli Python pour un comportement identique partout.
        upd._install_with_tar = lambda *_args, **_kw: False
        upd.remote_revision = lambda: "abc123"
        try:
            assert apply_update(root) == "ok"
            assert apply_update(root) == "same"
        finally:
            upd._download = old_dl
            upd._install_with_tar = old_tar
            upd.remote_revision = old_remote

        assert (root / "main.py").read_text(encoding="utf-8") == "NEW\n"
        assert (root / "kiosk" / "app.py").read_text(encoding="utf-8") == "# maj\n"
        assert (root / "save.json").read_text(encoding="utf-8") == "PARTIE\n"
        assert (root / "var" / "keep.txt").read_text(encoding="utf-8") == "ok\n"
        assert (root / ".world3-revision").read_text(encoding="utf-8").strip() == "abc123"


def test_archive_refuse_traversal():
    import kiosk.update as upd

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        info = tarfile.TarInfo("../evil.py")
        data = b"x"
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "bad.tgz"
        archive.write_bytes(buf.getvalue())
        dest = Path(tmp) / "out"
        dest.mkdir()
        try:
            upd._safe_extract(archive, dest)
        except RuntimeError:
            pass
        else:
            raise AssertionError("traversal accepte")


def test_bouton_menu():
    import pygame

    from kiosk.app import Menu
    import kiosk.update as upd

    pygame.init()
    try:
        pygame.display.set_mode((720, 720))
        screen = _Screen()
        menu = Menu(screen)
        with upd._lock:
            upd._state["online"] = True
            upd._state["busy"] = False
        assert menu._update_visible()
        assert menu._update_rect().right == 720 - 20
        assert menu._hit((menu._update_rect().centerx, menu._update_rect().centery)) == "update"
        with upd._lock:
            upd._state["online"] = False
        assert not menu._update_visible()
        assert project_root().name == "world3"
    finally:
        pygame.quit()


class _Screen:
    def __init__(self):
        import pygame

        self.surf = pygame.Surface((720, 720))

    def poll(self):
        return None

    def present(self):
        return None

    def logical(self, pos):
        return pos


def main():
    test_repo_et_garde()
    test_overlay_conserve_locaux()
    test_archive_refuse_traversal()
    test_bouton_menu()
    print("update ok")


if __name__ == "__main__":
    main()
