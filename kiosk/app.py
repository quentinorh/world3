"""Quatre choix au demarrage : WORLD3, RELIEF, CARTE, SP2050."""

from __future__ import annotations

import argparse
import time

import pygame

from device.power import halt_machine
from device.screen import H, W, open_screen
from device.widgets import draw_button, plate
from kiosk.update import (
    busy as update_busy,
    ensure_probe,
    online,
    restart_kiosk,
    start_update,
    take_result,
)
from sp2050.sync import maybe_start, running
from sp2050.theme import INK as SP_INK
from sp2050.theme import MUTED as SP_MUTED
from sp2050.theme import PAPER, VIOLET
from world3.font import Font
from world3.theme import BG, GLASS, INK, LINE, MUTED, RUST

# Bande du relief. Assez sombre pour l'encre claire, assez bleue
# pour ne pas se confondre avec WORLD3.
_RELIEF = (16, 42, 50)
# Sable de la carte, distinct du papier de SP2050.
_CARTE = (214, 206, 188)
_CARTE_INK = (36, 32, 28)
_CARTE_MUTED = (110, 96, 78)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Choisir WORLD3, RELIEF, CARTE ou SP2050.")
    parser.add_argument("--fullscreen", action="store_true")
    parser.add_argument("--scale", type=int, default=1)
    args = parser.parse_args(argv)
    maybe_start()
    ensure_probe()
    screen = open_screen(args.fullscreen, args.scale, "WORLD3")
    root_save = _save_path()
    try:
        while True:
            choice = run_menu(screen)
            if choice == "world3":
                from world3.app import run_game

                run_game(screen, root_save)
                pygame.event.clear()
            elif choice == "relief":
                from relief.app import run

                if run(screen) == "quit":
                    break
                pygame.event.clear()
            elif choice == "carte":
                from carte.app import run

                if run(screen) == "quit":
                    break
                pygame.event.clear()
            elif choice == "sp2050":
                from sp2050.app import run

                if run(screen) == "quit":
                    break
                pygame.event.clear()
            else:
                break
    finally:
        screen.close()


def _save_path():
    from pathlib import Path

    return Path(__file__).resolve().parent.parent / "save.json"


def run_menu(screen) -> str:
    menu = Menu(screen)
    return menu.loop()


class Menu:
    def __init__(self, screen):
        self.screen = screen
        self.pixel = Font()
        self.confirm = False
        self.update_ask = False
        self.pressed = None
        self.down = None
        self.toast_until = 0.0
        self.toast_text = "IMPOSSIBLE"
        self.toast_color = RUST
        self.shade = pygame.Surface((W, H), pygame.SRCALPHA)
        self.shade.fill((0, 0, 0, 150))
        self.band = H // 4
        ensure_probe()

    def loop(self) -> str:
        clock = pygame.time.Clock()
        while True:
            self.screen.poll()
            self._poll_update()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "quit"
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    if self.confirm or self.update_ask:
                        self.confirm = False
                        self.update_ask = False
                        self.pressed = None
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self._down(self.screen.logical(event.pos))
                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    choice = self._up(self.screen.logical(event.pos))
                    if choice:
                        return choice
            self._draw()
            self.screen.present()
            clock.tick(30)

    def _poll_update(self):
        result, _detail = take_result()
        if result is None:
            return
        self.update_ask = False
        if result == "ok":
            self._toast("REDÉMARRAGE", INK)
            if not restart_kiosk():
                self._toast("À JOUR", INK)
            return
        self._toast("ÉCHEC", RUST)

    def _toast(self, text, color=RUST, seconds=1.8):
        self.toast_text = text
        self.toast_color = color
        self.toast_until = time.monotonic() + seconds

    def _power_rect(self):
        return pygame.Rect(20, 16, 48, 48)

    def _update_rect(self):
        return pygame.Rect(W - 20 - 48, 16, 48, 48)

    def _update_visible(self):
        return online() and not update_busy()

    def _world_rect(self):
        return pygame.Rect(0, 0, W, self.band)

    def _relief_rect(self):
        return pygame.Rect(0, self.band, W, self.band)

    def _carte_rect(self):
        return pygame.Rect(0, 2 * self.band, W, self.band)

    def _sp_rect(self):
        return pygame.Rect(0, 3 * self.band, W, H - 3 * self.band)

    def _down(self, pos):
        self.down = pos
        self.pressed = self._hit(pos)

    def _up(self, pos):
        pressed = self.pressed
        self.pressed = None
        self.down = None
        if pressed is None or pressed != self._hit(pos):
            return None
        if pressed == "off":
            self.confirm = True
            self.update_ask = False
            return None
        if pressed == "update":
            self.update_ask = True
            self.confirm = False
            return None
        if pressed == "cancel":
            self.confirm = False
            self.update_ask = False
            return None
        if pressed == "do-off":
            self.confirm = False
            if halt_machine():
                return "quit"
            self._toast("IMPOSSIBLE", RUST)
            return None
        if pressed == "do-update":
            self.update_ask = False
            if start_update():
                self._toast("TÉLÉCHARGEMENT", INK, seconds=30.0)
            else:
                self._toast("OCCUPÉ", RUST)
            return None
        if self.confirm or self.update_ask or update_busy():
            return None
        if pressed == "world3":
            return "world3"
        if pressed == "relief":
            return "relief"
        if pressed == "carte":
            return "carte"
        if pressed == "sp2050":
            maybe_start(force=not _has_stories())
            return "sp2050"
        return None

    def _hit(self, pos):
        if self.confirm:
            if self._cancel_rect().collidepoint(pos):
                return "cancel"
            if self._off_rect().collidepoint(pos):
                return "do-off"
            return None
        if self.update_ask:
            if self._cancel_rect().collidepoint(pos):
                return "cancel"
            if self._off_rect().collidepoint(pos):
                return "do-update"
            return None
        if update_busy():
            return None
        if self._power_rect().collidepoint(pos):
            return "off"
        if self._update_visible() and self._update_rect().collidepoint(pos):
            return "update"
        if self._world_rect().collidepoint(pos):
            return "world3"
        if self._relief_rect().collidepoint(pos):
            return "relief"
        if self._carte_rect().collidepoint(pos):
            return "carte"
        if self._sp_rect().collidepoint(pos):
            return "sp2050"
        return None

    def _cancel_rect(self):
        return pygame.Rect(W // 2 - 210, H // 2 + 20, 190, 72)

    def _off_rect(self):
        return pygame.Rect(W // 2 + 20, H // 2 + 20, 190, 72)

    def _draw(self):
        surf = self.screen.surf
        surf.fill(BG)
        pygame.draw.rect(surf, _RELIEF, self._relief_rect())
        pygame.draw.rect(surf, _CARTE, self._carte_rect())
        pygame.draw.rect(surf, PAPER, self._sp_rect())
        self._draw_world(surf)
        self._draw_relief(surf)
        self._draw_carte(surf)
        self._draw_sp(surf)
        self._draw_power(surf)
        if self._update_visible() or update_busy():
            self._draw_update(surf)
        if self.confirm:
            self._draw_confirm(surf)
        elif self.update_ask:
            self._draw_update_confirm(surf)
        elif time.monotonic() < self.toast_until:
            self._draw_toast(surf)

    def _shift(self, name):
        return (3, 3) if self.pressed == name else (0, 0)

    def _band_title(self, surf, band, name, title, sub, title_color, sub_color):
        title_scale = 8
        sub_scale = 2
        title_h = self.pixel.height(title_scale)
        sub_h = self.pixel.height(sub_scale)
        gap = 14
        block = title_h + gap + sub_h
        dx, dy = self._shift(name)
        y = band.y + (band.h - block) // 2 + dy
        x = W // 2 + dx
        self.pixel.blit(surf, title, x, y, title_scale, title_color, align="center")
        self.pixel.blit(surf, sub, x, y + title_h + gap, sub_scale, sub_color, align="center")

    def _draw_world(self, surf):
        self._band_title(
            surf, self._world_rect(), "world3",
            "WORLD3", "DE 1900 À 2100", INK, MUTED,
        )

    def _draw_relief(self, surf):
        self._band_title(
            surf, self._relief_rect(), "relief",
            "RELIEF", "MERS ET RELIEFS", INK, GLASS,
        )

    def _draw_carte(self, surf):
        self._band_title(
            surf, self._carte_rect(), "carte",
            "CARTE", "OPENSTREETMAP", _CARTE_INK, _CARTE_MUTED,
        )

    def _draw_sp(self, surf):
        band = self._sp_rect()
        dx, dy = self._shift("sp2050")
        title_scale = 8
        sub_scale = 2
        title_h = self.pixel.height(title_scale)
        sub_h = self.pixel.height(sub_scale)
        gap = 14
        block = title_h + gap + sub_h
        hint = running()
        if hint:
            block += 18 + self.pixel.height(2)
        y = band.y + (band.h - block) // 2 + dy
        x = W // 2 + dx
        self.pixel.blit(surf, "SP2050", x, y, title_scale, SP_INK, align="center")
        self.pixel.blit(
            surf, "LIRE LE FUTUR", x, y + title_h + gap,
            sub_scale, VIOLET, align="center",
        )
        if hint:
            self.pixel.blit(
                surf, "SYNCHRO", x, y + title_h + gap + sub_h + 18,
                2, SP_MUTED, align="center",
            )

    def _draw_power(self, surf):
        pressed = self.pressed == "off" and not self.confirm and not self.update_ask
        face, _color = plate(surf, self._power_rect(), pressed)
        _power_mark(surf, face)

    def _draw_update(self, surf):
        pressed = self.pressed == "update" and not self.update_ask and not self.confirm
        face, _color = plate(surf, self._update_rect(), pressed or update_busy())
        _update_mark(surf, face)

    def _draw_confirm(self, surf):
        surf.blit(self.shade, (0, 0))
        panel = pygame.Rect(W // 2 - 250, H // 2 - 120, 500, 250)
        pygame.draw.rect(surf, LINE, panel.move(4, 4))
        pygame.draw.rect(surf, BG, panel)
        pygame.draw.rect(surf, INK, panel, 2)
        self.pixel.blit(
            surf, "ÉTEINDRE LE PI ?", W // 2, panel.y + 48,
            3, INK, align="center",
        )
        draw_button(
            surf, self.pixel, self._cancel_rect(), "ANNULER",
            self.pressed == "cancel", 2,
        )
        draw_button(
            surf, self.pixel, self._off_rect(), "ÉTEINDRE",
            self.pressed == "do-off", 2, kind="rust",
        )

    def _draw_update_confirm(self, surf):
        surf.blit(self.shade, (0, 0))
        panel = pygame.Rect(W // 2 - 250, H // 2 - 120, 500, 250)
        pygame.draw.rect(surf, LINE, panel.move(4, 4))
        pygame.draw.rect(surf, BG, panel)
        pygame.draw.rect(surf, INK, panel, 2)
        self.pixel.blit(
            surf, "METTRE À JOUR ?", W // 2, panel.y + 48,
            3, INK, align="center",
        )
        self.pixel.blit(
            surf, "CODE DEPUIS GITHUB", W // 2, panel.y + 96,
            2, MUTED, align="center",
        )
        draw_button(
            surf, self.pixel, self._cancel_rect(), "ANNULER",
            self.pressed == "cancel", 2,
        )
        draw_button(
            surf, self.pixel, self._off_rect(), "OUI",
            self.pressed == "do-update", 2, kind="on",
        )

    def _draw_toast(self, surf):
        self.pixel.blit(
            surf, self.toast_text, W // 2, H - 72, 2, self.toast_color, align="center",
        )


def _has_stories():
    from sp2050.library import load_stories

    return bool(load_stories())


# Cercle et trait, aussi larges que hauts. Le trait ne depasse qu'un cran.
_POWER = (
    "...#...",
    ".#.#.#.",
    "#.....#",
    "#.....#",
    "#.....#",
    ".#...#.",
    "..###..",
)


def _power_mark(surf, face):
    _pixel_mark(surf, face, _POWER, INK)


# Fleche vers le bas : telecharger / mettre a jour.
_UPDATE = (
    "...#...",
    "...#...",
    "...#...",
    ".#.#.#.",
    "..###..",
    "...#...",
    ".#####.",
)


def _update_mark(surf, face):
    _pixel_mark(surf, face, _UPDATE, INK)


def _pixel_mark(surf, face, rows, color):
    scale = 4
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
