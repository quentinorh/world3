"""Partie sauvee. Le temps n'avance que lorsque les annees sont lancees."""

import json
import random
from pathlib import Path

from .content import HORIZON_CAP, SHOCK_BY_ID
from .sim import START_YEAR, YEAR_MAX, YEAR_MIN, baseline_schedule, law_count, pad_notches

MAX_SEALS = 3


class GameState:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.year = float(START_YEAR)
        self.seals = 0
        self.schedule = list(baseline_schedule())
        self.seen_intro = False
        self.events_done = set()
        self.shocks = []
        self.rng_seed = random.randrange(1, 2**31 - 1)
        self.sound = True
        self.horizon = float(YEAR_MAX)
        self.council_granted = 0
        self.council_phase = ""
        self.pending = None

    @property
    def notches(self):
        return self.schedule[-1][1]

    def load(self):
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self.year = float(raw.get("year", START_YEAR))
        self.seals = int(raw.get("seals", 3))
        self.seen_intro = bool(raw.get("seen_intro", False))
        self.events_done = set(raw.get("events_done", []))
        self.sound = bool(raw.get("sound", True))
        try:
            self.horizon = float(raw.get("horizon", YEAR_MAX))
        except (TypeError, ValueError):
            self.horizon = float(YEAR_MAX)
        self.horizon = max(float(YEAR_MAX), min(float(HORIZON_CAP), self.horizon))
        try:
            self.council_granted = int(raw.get("council_granted") or 0)
        except (TypeError, ValueError):
            self.council_granted = 0
        phase = raw.get("council_phase") or ""
        self.council_phase = phase if phase in ("orient", "dilemma") else ""
        pending = raw.get("pending")
        self.pending = None
        if isinstance(pending, (list, tuple)) and len(pending) == 2:
            sid = str(pending[1])
            if sid in SHOCK_BY_ID:
                try:
                    self.pending = (float(pending[0]), sid)
                except (TypeError, ValueError):
                    self.pending = None
        seed = raw.get("rng_seed")
        if isinstance(seed, int) and seed > 0:
            self.rng_seed = seed
        shocks = []
        seen = set()
        for item in raw.get("shocks", []):
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                continue
            year, sid = item
            sid = str(sid)
            if sid not in SHOCK_BY_ID or sid in seen:
                continue
            try:
                year = float(year)
            except (TypeError, ValueError):
                continue
            year = min(YEAR_MAX, max(YEAR_MIN, year))
            shocks.append((year, sid))
            seen.add(sid)
        self.shocks = sorted(shocks)
        schedule = []
        for year, notches in raw.get("schedule", []):
            if notches is None:
                continue
            schedule.append((float(year), pad_notches(notches)))
        if not schedule or schedule[0][0] > YEAR_MIN + 1:
            schedule.insert(0, (float(YEAR_MIN), (0,) * law_count()))
        self.schedule = schedule
        self.year = min(self.horizon, max(START_YEAR, self.year))
        self.seals = max(0, min(MAX_SEALS, self.seals))

    def save(self):
        payload = {
            "version": 4,
            "year": self.year,
            "seals": self.seals,
            "schedule": [[y, list(n)] for y, n in self.schedule],
            "seen_intro": self.seen_intro,
            "events_done": sorted(self.events_done),
            "shocks": [[y, sid] for y, sid in self.shocks],
            "rng_seed": self.rng_seed,
            "sound": self.sound,
            "horizon": self.horizon,
            "council_granted": self.council_granted,
            "council_phase": self.council_phase,
            "pending": list(self.pending) if self.pending else None,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def grant_turn_seal(self):
        if self.seals >= MAX_SEALS:
            return 0
        self.seals += 1
        return 1

    def shock_ids(self):
        return {sid for _, sid in self.shocks}

    def reset_world(self):
        sound = self.sound
        self.__init__(self.path)
        self.sound = sound
        self.save()
