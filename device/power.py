"""Extinction du Raspberry. Ailleurs, rien ne se passe."""

from __future__ import annotations

import os
import shutil
import subprocess


def on_pi():
    try:
        model = open("/proc/device-tree/model", "rb").read().lower()
    except OSError:
        return False
    return b"raspberry" in model


def halt_machine():
    """Eteint la carte. Faux ailleurs, ou si l'arret est refuse."""
    if not on_pi():
        return False
    exe = shutil.which("poweroff")
    sudo = shutil.which("sudo")
    if not exe or not sudo:
        return False
    if hasattr(os, "sync"):
        os.sync()
    try:
        done = subprocess.run(
            [sudo, "-n", exe],
            timeout=8,
            capture_output=True,
        )
    except subprocess.TimeoutExpired:
        return True
    except OSError:
        return False
    return done.returncode == 0
