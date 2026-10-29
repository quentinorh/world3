"""Palette, grille, et le peu de geometrie partage entre le dessin et le doigt."""

W = 720
H = 720

BG = (16, 14, 12)
INK = (236, 230, 216)
MUTED = (176, 168, 154)
DIM = (96, 90, 80)
LINE = (48, 44, 38)
SEA = (28, 92, 108)
SEA_DEEP = (12, 44, 54)
MOSS = (92, 168, 74)
OCHRE = (224, 164, 72)
RUST = (216, 104, 78)
GLASS = (130, 190, 198)
ICE = (214, 220, 216)
CITY = (236, 204, 128)
SAND = (168, 132, 86)

NAV_Y = 644
NAV_H = H - NAV_Y

# Milieu de l'écran. La barre escamotable ne le décale pas.
PLANET_C = (W // 2, H // 2)
PLANET_R = 160
RING_R = 192

# Intro événement : tours de phase par unité d'orbit. Plus haut = pulsations plus rapprochées.
EVENT_WAVE = 1.0

CONDITION = {
    "CROISSANCE": INK,
    "STABLE": MOSS,
    "RALENTISSEMENT": MOSS,
    "TENSION": OCHRE,
    "CRISE": RUST,
    "FAMINE": RUST,
}

# Vitesse de rotation au repos, en radians par seconde.
# Negatif : la surface va d'ouest en est. Une crise tourne plus vite.
MOOD_SPIN = {
    "CROISSANCE": -0.07,
    "STABLE": -0.015,
    "RALENTISSEMENT": -0.025,
    "TENSION": -0.055,
    "CRISE": -0.12,
    "FAMINE": -0.155,
}

TONE = {
    "ink": INK,
    "ok": MOSS,
    "warn": OCHRE,
    "bad": RUST,
}

SERIES_COLOR = {
    "pop": INK,
    "nrfr": OCHRE,
    "fpc": MOSS,
    "iopc": GLASS,
    "ppolx": RUST,
}


def mix(a, b, t):
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def tone_color(name):
    return TONE.get(name, INK)
