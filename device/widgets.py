"""Boutons du menu, du relief, de la carte et de SP2050.

Meme dessin que ceux du jeu : ombre decalee, cadre de deux pixels,
face qui s'enfonce. La police est world3.font.
"""

import pygame

from world3.theme import BG, DIM, INK, LINE, OCHRE, RUST

BAR = 72
BUTTON = 56
HOME = 48
# L'encre du jeu est beige. Sur fond clair, la face reste un gris neutre.
HOME_LIGHT = (242, 242, 242)

# Toit en escalier, debord, porte centree. Le trou est le seuil.
_HOUSE = (
    "....#....",
    "...###...",
    "..#####..",
    ".#######.",
    "#########",
    ".###.###.",
    ".###.###.",
    ".###.###.",
)


def home_rect():
    return pygame.Rect(20, 16, HOME, HOME)


def menu_rect():
    return home_rect()


def plus_rect(view):
    view = pygame.Rect(view)
    return pygame.Rect(view.right - 72, view.centery - 70, BUTTON, BUTTON)


def minus_rect(view):
    view = pygame.Rect(view)
    return pygame.Rect(view.right - 72, view.centery + 16, BUTTON, BUTTON)


def plate(surf, rect, pressed=False, kind="plain", enabled=True, fill=None, edge=None):
    """Dessine la face et retourne (face, couleur du texte)."""
    rect = pygame.Rect(rect)
    face = rect.move(3, 3) if pressed and enabled else pygame.Rect(rect)
    if kind == "invert":
        pygame.draw.rect(surf, INK, face)
        return face, BG
    if enabled and not pressed:
        pygame.draw.rect(surf, LINE, rect.move(4, 4))
    pygame.draw.rect(surf, BG if fill is None else fill, face)
    if edge is not None:
        color = edge
    elif not enabled:
        color = DIM
    elif kind == "rust":
        color = RUST
    elif kind == "on":
        color = OCHRE
    else:
        color = INK
    pygame.draw.rect(surf, color, face, 2)
    return face, color


def _mark(surf, face, rows, color, scale):
    width = len(rows[0]) * scale
    height = len(rows) * scale
    x0 = face.centerx - width // 2
    y0 = face.centery - height // 2
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == "#":
                pygame.draw.rect(
                    surf, color, (x0 + x * scale, y0 + y * scale, scale, scale),
                )


def draw_home(surf, rect, pressed=False, ground="dark"):
    """Maison. Fond sombre : encre claire. Fond clair : maison sombre sur gris."""
    if ground == "light":
        face, color = plate(surf, rect, pressed, fill=HOME_LIGHT, edge=BG)
    else:
        face, color = plate(surf, rect, pressed)
    _mark(surf, face, _HOUSE, color, 4)
    return face


def draw_button(surf, font, rect, label, pressed=False, scale=2, kind="plain", enabled=True):
    face, color = plate(surf, rect, pressed, kind, enabled)
    font.blit_center(surf, label, face, scale, color)
    return face
