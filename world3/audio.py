"""Clics d'interface, calcules ici. Secs, courts, legers.

Un grain de bruit, parfois une sinus tres breve. La hauteur ne fait
qu'une teinte de quelques demi-tons : on sent le cran, pas une note.
"""

from __future__ import annotations

import numpy as np
import pygame

from .sim import law_count

SR = 44100

# Quelques demi-tons au plus. Assez pour sentir un cran, trop peu pour une gamme.
SCREEN_SEMI = {"monde": 0, "lois": 1, "courbes": 2, "temps": 3}


def law_semi(index):
    i = int(index)
    if i < 0:
        i = 0
    span = max(1, law_count() - 1)
    if i > span:
        i = span
    return int(round(i * 4 / span))


def year_semi(year):
    t = (min(2100.0, max(1900.0, float(year))) - 1900.0) / 200.0
    return int(round(t * 2))


def notch_semi(notch):
    return max(0, min(4, int(notch)))


def _pitches(name):
    if name == "seek":
        return (0, 1, 2)
    if name in ("snap", "swipe", "select"):
        return (0, 1, 2, 3, 4)
    return (0,)


# dur en secondes, peak entre 0 et 1.
# Les gains des couches sont des parts, pas un volume final.
_SOUNDS = {
    "seek": {
        "dur": 0.028,
        "peak": 0.128,
        "fade": 1.0,
        "cents": (-3, 0, 3),
        "layers": (
            {"op": "tick", "gain": 0.72, "att": 0.0003, "dec": 0.0028},
            {"op": "tone", "f": (2400, 1700), "gain": 0.28, "att": 0.0006, "dec": 0.008},
        ),
    },
    "snap": {
        "dur": 0.042,
        "peak": 0.32,
        "fade": 1.2,
        "cents": (-3, 0, 3),
        "layers": (
            {"op": "tick", "gain": 0.62, "att": 0.0003, "dec": 0.0032},
            {"op": "tone", "f": (1680, 1240), "gain": 0.38, "att": 0.0008, "dec": 0.012},
        ),
    },
    "swipe": {
        # Clic des cartes d'orientation : même esprit que select, plus aigu.
        "dur": 0.036,
        "peak": 0.28,
        "fade": 1.1,
        "layers": (
            {"op": "tick", "gain": 0.5, "att": 0.0003, "dec": 0.0028},
            {"op": "tone", "f": (2600, 2100), "gain": 0.42, "att": 0.0007, "dec": 0.01},
        ),
    },
    "select": {
        "dur": 0.036,
        "peak": 0.28,
        "fade": 1.1,
        "layers": (
            {"op": "tick", "gain": 0.55, "att": 0.0003, "dec": 0.003},
            {"op": "tone", "f": (1900, 1600), "gain": 0.4, "att": 0.0007, "dec": 0.01},
        ),
    },
    "toggle-on": {
        "dur": 0.05,
        "peak": 0.26,
        "fade": 1.2,
        "layers": (
            {"op": "tick", "gain": 0.5, "att": 0.0003, "dec": 0.0026},
            {"op": "tone", "f": (1500, 1280), "gain": 0.32, "att": 0.0006, "dec": 0.009},
            {"op": "tick", "gain": 0.28, "att": 0.0003, "dec": 0.0022, "delay": 0.016},
            {"op": "tone", "f": (1760, 1500), "gain": 0.22, "att": 0.0006, "dec": 0.008, "delay": 0.016},
        ),
    },
    "toggle-off": {
        "dur": 0.05,
        "peak": 0.24,
        "fade": 1.2,
        "layers": (
            {"op": "tick", "gain": 0.48, "att": 0.0003, "dec": 0.0026},
            {"op": "tone", "f": (1760, 1500), "gain": 0.3, "att": 0.0006, "dec": 0.008},
            {"op": "tick", "gain": 0.26, "att": 0.0003, "dec": 0.0022, "delay": 0.016},
            {"op": "tone", "f": (1400, 1180), "gain": 0.2, "att": 0.0006, "dec": 0.008, "delay": 0.016},
        ),
    },
    "check": {
        "dur": 0.046,
        "peak": 0.28,
        "fade": 1.2,
        "layers": (
            {"op": "tick", "gain": 0.58, "att": 0.0003, "dec": 0.0028},
            {"op": "tone", "f": (2100, 1650), "gain": 0.32, "att": 0.0006, "dec": 0.009},
            {"op": "tick", "gain": 0.34, "att": 0.0003, "dec": 0.0024, "delay": 0.014},
        ),
    },
    "uncheck": {
        "dur": 0.032,
        "peak": 0.2,
        "fade": 1.0,
        "layers": (
            {"op": "tick", "gain": 0.7, "att": 0.0003, "dec": 0.0026},
            {"op": "tone", "f": (1600, 1200), "gain": 0.28, "att": 0.0006, "dec": 0.008},
        ),
    },
    "open": {
        "dur": 0.07,
        "peak": 0.22,
        "fade": 1.8,
        "layers": (
            {"op": "whoosh", "f": (700, 1600), "q": 0.55, "gain": 0.78, "att": 0.006, "dec": 0.022},
            {"op": "tick", "gain": 0.22, "att": 0.0004, "dec": 0.003},
        ),
    },
    # Conseil / dilemme : même tic que warning, plus aigu.
    "council": {
        "dur": 0.048,
        "peak": 0.26,
        "fade": 1.2,
        "warm": 5,
        "layers": (
            {"op": "tick", "gain": 0.46, "att": 0.0004, "dec": 0.003},
            {"op": "tone", "f": (420, 340), "gain": 0.34, "att": 0.0008, "dec": 0.012},
            {"op": "tick", "gain": 0.28, "att": 0.0003, "dec": 0.0024, "delay": 0.018},
        ),
    },
    "close": {
        "dur": 0.06,
        "peak": 0.2,
        "fade": 1.6,
        "layers": (
            {"op": "whoosh", "f": (1600, 640), "q": 0.55, "gain": 0.78, "att": 0.004, "dec": 0.02},
            {"op": "tick", "gain": 0.2, "att": 0.0004, "dec": 0.0026},
        ),
    },
    "back": {
        "dur": 0.03,
        "peak": 0.22,
        "fade": 1.0,
        "layers": (
            {"op": "tick", "gain": 0.68, "att": 0.0003, "dec": 0.0026},
            {"op": "tone", "f": (1800, 1300), "gain": 0.28, "att": 0.0005, "dec": 0.008},
        ),
    },
    "forward": {
        "dur": 0.03,
        "peak": 0.22,
        "fade": 1.0,
        "layers": (
            {"op": "tick", "gain": 0.62, "att": 0.0003, "dec": 0.0026},
            {"op": "tone", "f": (1400, 1900), "gain": 0.3, "att": 0.0005, "dec": 0.008},
        ),
    },
    "cancel": {
        "dur": 0.034,
        "peak": 0.22,
        "fade": 1.0,
        "layers": (
            {"op": "tick", "gain": 0.66, "att": 0.0003, "dec": 0.0028},
            {"op": "tone", "f": (1500, 1180), "gain": 0.3, "att": 0.0006, "dec": 0.009},
        ),
    },
    "warning": {
        "dur": 0.048,
        "peak": 0.26,
        "fade": 1.2,
        "warm": 5,
        "layers": (
            {"op": "tick", "gain": 0.46, "att": 0.0004, "dec": 0.003},
            {"op": "tone", "f": (980, 820), "gain": 0.34, "att": 0.0008, "dec": 0.012},
            {"op": "tick", "gain": 0.28, "att": 0.0003, "dec": 0.0024, "delay": 0.018},
        ),
    },
    "delete": {
        "dur": 0.07,
        "peak": 0.28,
        "fade": 1.6,
        "warm": 7,
        "layers": (
            {"op": "thud", "gain": 0.42, "att": 0.001, "dec": 0.016},
            {"op": "tone", "f": (1100, 720), "gain": 0.4, "att": 0.001, "dec": 0.02},
            {"op": "tick", "gain": 0.22, "att": 0.0003, "dec": 0.003},
        ),
    },
    "blocked": {
        "dur": 0.04,
        "peak": 0.3,
        "fade": 1.1,
        "warm": 9,
        "layers": (
            {"op": "thud", "gain": 0.35, "att": 0.0005, "dec": 0.008},
            {"op": "tone", "f": (980, 760), "gain": 0.5, "att": 0.0006, "dec": 0.01},
            {"op": "tick", "gain": 0.22, "att": 0.0003, "dec": 0.0024},
        ),
    },
    "progress-step": {
        "dur": 0.05,
        "peak": 0.24,
        "fade": 1.2,
        "layers": (
            {"op": "tick", "gain": 0.55, "att": 0.0003, "dec": 0.0028},
            {"op": "tone", "f": (1500, 1180), "gain": 0.28, "att": 0.0006, "dec": 0.01},
        ),
    },
}


class Kit:
    def __init__(self):
        self.ready = False
        self.bank = {}
        self.detent = None
        self._step = {}

    def load(self):
        if pygame.mixer.get_init():
            pygame.mixer.quit()
        pygame.mixer.init(SR, -16, 2, 512)
        pygame.mixer.set_num_channels(12)
        pygame.mixer.set_reserved(1)
        self.detent = pygame.mixer.Channel(0)
        self.bank = {}
        for name, spec in _SOUNDS.items():
            self.bank[name] = {}
            for semi in _pitches(name):
                cents = spec.get("cents", (0,))
                takes = []
                for var, cent in enumerate(cents):
                    arr = _render(name, spec, semi, cent, var)
                    snd = pygame.sndarray.make_sound(arr)
                    takes.append(snd)
                self.bank[name][int(semi)] = takes
        self.ready = True

    def play(self, name, semi=0, detent=False):
        takes = _resolve(self.bank, name, int(semi))
        if not takes:
            return
        i = self._step.get(name, 0)
        self._step[name] = i + 1
        snd = takes[i % len(takes)]
        if detent and self.detent is not None:
            self.detent.play(snd)
        else:
            snd.play()


def _resolve(bank, name, semi):
    bucket = bank.get(name)
    if not bucket:
        return None
    if semi in bucket:
        return bucket[semi]
    nearest = min(bucket, key=lambda s: abs(s - semi))
    return bucket[nearest]


def _render(name, spec, semi, cents, var):
    rate = 2.0 ** ((float(semi) + float(cents) / 100.0) / 12.0)
    extra = float(spec.get("echo", 0.0)) / 1000.0
    n = int((float(spec["dur"]) + extra + 0.012) * SR)
    n = max(8, n)
    rng = np.random.default_rng(_seed(name, semi, var))
    tone = np.zeros(n, dtype=np.float64)
    air = np.zeros(n, dtype=np.float64)
    for layer in spec["layers"]:
        shaped = _layer(layer, n, rate, rng)
        if layer["op"] == "tone":
            tone += shaped
        else:
            air += shaped
    warm = int(spec.get("warm", 5))
    if warm > 3:
        tone = _blur(tone, warm)
    mix = tone + air
    mix -= np.mean(mix)
    _fade_inplace(mix, float(spec.get("fade", 3.0)))
    left, right = _image(mix, float(spec.get("echo", 0.0)), float(spec.get("echo_gain", 0.0)))
    peak = max(float(np.max(np.abs(left))), float(np.max(np.abs(right))), 1e-9)
    gain = float(spec["peak"]) / peak
    stereo = np.column_stack((left * gain, right * gain))
    _fade_inplace(stereo[:, 0], float(spec.get("fade", 3.0)) * 0.5)
    _fade_inplace(stereo[:, 1], float(spec.get("fade", 3.0)) * 0.5)
    out = np.clip(np.rint(stereo * 32767.0), -32767, 32767).astype(np.int16)
    return np.ascontiguousarray(out)


def _seed(name, semi, var):
    acc = 2166136261
    for ch in name:
        acc ^= ord(ch)
        acc = (acc * 16777619) & 0xFFFFFFFF
    acc = (acc + int(semi) * 131 + int(var) * 977) & 0x7FFFFFFF
    return acc


def _layer(layer, n, rate, rng):
    op = layer["op"]
    if op == "tone":
        raw = _tone(n, layer, rate)
    elif op == "tick":
        raw = _tick(n, rng)
    elif op == "whoosh":
        raw = _whoosh(n, layer, rate, rng)
    else:
        raw = _thud(n, rng)
    env = _env(n, float(layer.get("att", 0.002)), float(layer.get("dec", 0.04)), float(layer.get("delay", 0.0)))
    shaped = raw * env
    return _unit(shaped) * float(layer.get("gain", 1.0))


def _tone(n, layer, rate):
    f0, f1 = _ends(layer["f"], rate)
    phase = _phase(f0, f1, n)
    fm = layer.get("fm")
    if fm:
        ratio, depth = fm
        mod = np.sin(_phase(f0 * ratio, f1 * ratio, n))
        f_ref = max(1.0, (abs(f0) * abs(f1)) ** 0.5)
        index = float(depth) / (float(ratio) * f_ref)
        y = np.sin(phase + index * mod)
    else:
        y = np.sin(phase)
    detune = float(layer.get("detune", 0.0))
    if detune:
        y = y + 0.4 * np.sin(phase * (2.0 ** (detune / 1200.0)))
    for k, amp in enumerate(layer.get("partials", ()), start=2):
        y = y + float(amp) * np.sin(phase * k)
    sub = float(layer.get("sub", 0.0))
    if sub:
        y = y + sub * np.sin(phase * 0.5)
    return y


def _ends(freq, rate):
    if isinstance(freq, tuple):
        return float(freq[0]) * rate, float(freq[1]) * rate
    f = float(freq) * rate
    return f, f


def _phase(f0, f1, n):
    if n <= 1 or (f0 <= 0 and f1 <= 0):
        return np.zeros(n, dtype=np.float64)
    if abs(f1 - f0) < 1e-3:
        return (2.0 * np.pi * f0 / SR) * np.arange(n, dtype=np.float64)
    t = np.arange(n, dtype=np.float64) / float(n - 1)
    freq = f0 * (f1 / f0) ** t
    return 2.0 * np.pi * np.cumsum(freq) / SR


def _tick(n, rng):
    white = rng.standard_normal(n)
    hp = np.diff(white, prepend=white[0])
    return hp * 0.82 + white * 0.18


def _thud(n, rng):
    white = rng.standard_normal(n)
    brown = np.cumsum(white)
    brown -= np.linspace(brown[0], brown[-1], n)
    body = _blur(brown, 41)
    # Le tres grave ne sort pas du petit haut-parleur : on garde le poids, pas le grondement.
    slow = max(31, min(len(body) // 3, int(SR / 180.0)))
    return body - _blur(body, slow)


def _whoosh(n, layer, rate, rng):
    f0, f1 = _ends(layer["f"], rate)
    f0 = min(max(f0, 80.0), SR * 0.45)
    f1 = min(max(f1, 80.0), SR * 0.45)
    q = float(layer.get("q", 0.8))
    src = _blur(rng.standard_normal(n), 3)
    return _band_sweep(src, f0, f1, q)


def _band_sweep(x, f0, f1, q):
    y = np.empty(len(x), dtype=np.float64)
    z1 = 0.0
    z2 = 0.0
    last = max(1, len(x) - 1)
    for i, sample in enumerate(x):
        t = i / last
        freq = f0 * (f1 / f0) ** t
        w = 2.0 * np.pi * freq / SR
        cw = np.cos(w)
        sw = np.sin(w)
        alpha = sw / (2.0 * q)
        a0 = 1.0 + alpha
        b0 = alpha / a0
        b2 = -alpha / a0
        a1 = (-2.0 * cw) / a0
        a2 = (1.0 - alpha) / a0
        out = b0 * sample + z1
        z1 = -a1 * out + z2
        z2 = b2 * sample - a2 * out
        y[i] = out
    return y


def _env(n, attack, decay, delay):
    t = np.arange(n, dtype=np.float64) / SR
    local = t - delay
    alive = local >= 0.0
    att = np.clip(local / max(attack, 1e-4), 0.0, 1.0)
    att = 0.5 - 0.5 * np.cos(np.pi * att)
    dec = np.exp(-np.maximum(0.0, local - attack) / max(decay, 1e-4))
    return np.where(alive, att * dec, 0.0)


def _unit(x):
    peak = float(np.max(np.abs(x)))
    if peak < 1e-8:
        return x
    return x / peak


def _blur(x, width):
    width = int(width)
    if width < 3 or len(x) < width:
        return x
    if width % 2 == 0:
        width += 1
    kernel = np.hanning(width)
    kernel /= np.sum(kernel)
    return np.convolve(x, kernel, mode="same")


def _fade_inplace(x, ms):
    n = min(len(x) // 2, int(ms * SR / 1000.0))
    if n < 2:
        return
    w = 0.5 - 0.5 * np.cos(np.linspace(0.0, np.pi, n))
    x[:n] *= w
    x[-n:] *= w[::-1]


def _image(mono, echo_ms, echo_gain):
    # Les deux canaux restent le meme son : un petit haut-parleur ne doit pas en perdre la moitie.
    left = mono
    right = mono
    echo_n = max(0, int(echo_ms * SR / 1000.0))
    if echo_n > 0 and echo_gain > 0.0 and echo_n < len(mono):
        echo = np.zeros(len(mono), dtype=np.float64)
        echo[echo_n:] = mono[:-echo_n] * echo_gain
        echo = _blur(echo, 31)
        left = mono + echo
        right = left
    return left, right
