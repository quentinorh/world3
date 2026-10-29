"""Releve du rythme, une ligne par tranche d'une demi-seconde.

Le fichier est du JSON, une ligne par tranche. `fps` est ce que l'ecran
montre. `work_ms` est le temps de calcul, sans l'attente qui cale les
30 images. Au-dela de 34 ms, une image depasse le budget et le jeu ralentit.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

_BUDGET_MS = 34.0
_SLOW_MS = 50.0
_SLICE_S = 0.5


class Pace:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.t0 = time.perf_counter()
        self.page = None
        self.act = None
        self.samples = []
        self.seg_t = self.t0
        self.fh = None
        try:
            self.fh = open(self.path, "a", encoding="utf-8", buffering=1)
        except OSError:
            return
        self._write({"kind": "session", "at": datetime.now().isoformat(timespec="seconds")})

    def boot(self, step, ms):
        self._write({"kind": "boot", "step": step, "ms": round(ms, 1)})

    def frame(self, page, act, year, work_ms, tick_ms, handle_ms, update_ms, draw_ms, present_ms):
        if self.fh is None:
            return
        changed = page != self.page or act != self.act
        aged = self.samples and (time.perf_counter() - self.seg_t) >= _SLICE_S
        if self.samples and (changed or aged):
            self._flush()
        if not self.samples:
            self.seg_t = time.perf_counter()
            self.page = page
            self.act = act
        self.samples.append((work_ms, tick_ms, handle_ms, update_ms, draw_ms, present_ms, year))
        if work_ms >= _SLOW_MS:
            self._write({
                "kind": "slow",
                "t": round(time.perf_counter() - self.t0, 2),
                "page": page,
                "act": act,
                "year": round(float(year), 1),
                "work_ms": round(work_ms, 1),
                "handle_ms": round(handle_ms, 1),
                "update_ms": round(update_ms, 1),
                "draw_ms": round(draw_ms, 1),
                "present_ms": round(present_ms, 1),
            })

    def close(self):
        if self.fh is None:
            return
        self._flush()
        self._write({"kind": "end", "t": round(time.perf_counter() - self.t0, 2)})
        self.fh.close()
        self.fh = None

    def _flush(self):
        rows = self.samples
        self.samples = []
        if not rows or self.fh is None:
            return
        works = sorted(row[0] for row in rows)
        ticks = sum(row[1] for row in rows)
        n = len(rows)
        fps = (n * 1000.0 / ticks) if ticks > 0 else 0.0
        p95 = works[min(n - 1, int(round(0.95 * (n - 1))))]

        def mean(index):
            return sum(row[index] for row in rows) / n

        self._write({
            "t": round(time.perf_counter() - self.t0, 2),
            "page": self.page,
            "act": self.act,
            "year": round(float(rows[-1][6]), 1),
            "n": n,
            "fps": round(fps, 1),
            "work_ms": round(mean(0), 1),
            "p95_ms": round(p95, 1),
            "max_ms": round(works[-1], 1),
            "handle_ms": round(mean(2), 1),
            "update_ms": round(mean(3), 1),
            "draw_ms": round(mean(4), 1),
            "present_ms": round(mean(5), 1),
            "slow": sum(1 for w in works if w >= _BUDGET_MS),
        })

    def _write(self, row):
        if self.fh is None:
            return
        self.fh.write(json.dumps(row, ensure_ascii=False) + "\n")
