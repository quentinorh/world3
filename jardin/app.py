"""Jardin : on avance, l'axe Y regarde sur le côté, les réglages changent la graine."""

from __future__ import annotations

import argparse
import math

import pygame

from device.accel import Accel
from device.screen import H, W, open_screen
from device.widgets import corner_hit, draw_button, draw_home, home_rect
from jardin.draw import EYE, Camera, render
from jardin.scene import Garden, Params, with_params
from jardin.species import HOURS, MIX, MIX_ANGLE, SPECIES
from world3.font import Font
from world3.theme import BG, INK, LINE, MUTED

# Même rappel que le globe : l'axe Y décale le regard, il ne s'intègre pas.
_TILT_GAIN = 1.4
_TILT_MAX = 0.95
_TILT_DEAD = 0.06
_TILT_SMOOTH = 5.0
_TILT_SMOOTH2 = 7.0
_LOOK_MAX = 1.2
_SPEED = 0.7

_PANEL = pygame.Rect(16, 152, 688, 556)
_ROW0 = 220
_ROW_H = 60
_ROWS = (
    ("species", "ESPÈCE"),
    ("seed", "GRAINE"),
    ("steps", "PASSES"),
    ("angle", "ANGLE"),
    ("density", "DENSITÉ"),
    ("tropism", "TROPISME"),
    ("hour", "HEURE"),
)


def _ease(rate, dt):
    return 1.0 - math.exp(-rate * dt)


def _default_angle(species: int) -> int:
    if species == MIX:
        return MIX_ANGLE
    return SPECIES[species].angle


def main(argv=None):
    parser = argparse.ArgumentParser(description="Jardin de plantes imaginaires.")
    parser.add_argument("--fullscreen", action="store_true")
    parser.add_argument("--scale", type=int, default=1)
    args = parser.parse_args(argv)
    screen = open_screen(args.fullscreen, args.scale, "JARDIN")
    try:
        run(screen)
    finally:
        screen.close()


def run(screen) -> str:
    """'menu' pour revenir au choix, 'quit' si la fenêtre se ferme."""
    return JardinApp(screen).loop()


class JardinApp:
    def __init__(self, screen):
        self.screen = screen
        self.pixel = Font()
        self.params = Params()
        self.garden = Garden(self.params)
        self.z = 0.0
        self.drag_yaw = 0.0
        self.tilt_yaw = 0.0
        self._tilt_key = 0.0
        self._y1 = 0.0
        self._y2 = 0.0
        self.beat = 0.0
        self.panel = False
        self.pressed = None
        self.mode = None
        self.anchor = None
        self.last = None
        self.moved = False
        self.accel = None

    def loop(self) -> str:
        clock = pygame.time.Clock()
        self.accel = Accel.open()
        dt = 0.0
        try:
            while True:
                self.screen.poll()
                leaving = None
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        return "quit"
                    if event.type == pygame.KEYDOWN:
                        leaving = self._key(event.key)
                    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        self._down(self.screen.logical(event.pos))
                    elif event.type == pygame.MOUSEMOTION and self.mode is not None:
                        self._move(self.screen.logical(event.pos))
                    elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                        leaving = self._up(self.screen.logical(event.pos))
                if leaving:
                    return leaving
                self._held(dt)
                self._step(dt)
                self._draw()
                self.screen.present()
                dt = min(0.1, clock.tick(30) / 1000.0)
        finally:
            if self.accel is not None:
                self.accel.close()
                self.accel = None

    def _key(self, key):
        if key == pygame.K_ESCAPE:
            if self.panel:
                self.panel = False
                self.pressed = None
                return None
            return "menu"
        if key == pygame.K_SPACE:
            self.panel = not self.panel
        return None

    def _held(self, dt):
        if dt <= 0:
            return
        keys = pygame.key.get_pressed()
        if keys[pygame.K_UP]:
            self._tilt_key = max(-_TILT_MAX, self._tilt_key - 0.9 * dt)
        elif keys[pygame.K_DOWN]:
            self._tilt_key = min(_TILT_MAX, self._tilt_key + 0.9 * dt)

    def _step(self, dt):
        self._step_tilt(dt)
        self.beat += dt
        if not self.panel:
            self.z += _SPEED * dt
        self.garden.update(self.z, self.params)
        self.garden.step_spores(self.z, dt)

    def _step_tilt(self, dt):
        raw = self._tilt_key
        sensor = self.accel
        if sensor is not None:
            delta = sensor.read_y_delta()
            if delta is not None:
                if abs(delta) < _TILT_DEAD:
                    delta = 0.0
                raw += delta
        self._y1 += (raw - self._y1) * _ease(_TILT_SMOOTH, dt)
        self._y2 += (self._y1 - self._y2) * _ease(_TILT_SMOOTH2, dt)
        self.tilt_yaw = max(-_TILT_MAX, min(_TILT_MAX, self._y2 * _TILT_GAIN))

    def _view_yaw(self) -> float:
        return max(-_LOOK_MAX, min(_LOOK_MAX, self.drag_yaw + self.tilt_yaw))

    def _down(self, pos):
        self.anchor = pos
        self.last = pos
        self.moved = False
        self.pressed = self._hit(pos)
        self.mode = "look" if self.pressed is None and not self.panel else self.pressed

    def _move(self, pos):
        if self.anchor is not None:
            span = abs(pos[0] - self.anchor[0]) + abs(pos[1] - self.anchor[1])
            if span > 10:
                self.moved = True
        if self.mode == "look" and self.last is not None:
            dx = pos[0] - self.last[0]
            self.drag_yaw = max(-1.05, min(1.05, self.drag_yaw - dx * 0.0048))
            self.last = pos

    def _up(self, pos):
        pressed = self.pressed
        moved = self.moved
        self.mode = None
        self.pressed = None
        self.anchor = None
        if pressed is None or moved or pressed != self._hit(pos):
            return None
        if pressed == "home":
            return "menu"
        if pressed == "gear":
            self.panel = True
            return None
        if pressed == "close":
            self.panel = False
            return None
        if pressed.endswith("-"):
            self._bump(pressed[:-1], -1)
        elif pressed.endswith("+"):
            self._bump(pressed[:-1], 1)
        return None

    def _bump(self, key, delta):
        p = self.params
        if key == "species":
            species = (p.species + delta) % (MIX + 1)
            self.params = with_params(p, species=species, angle=_default_angle(species))
        elif key == "seed":
            self.params = with_params(p, seed=(p.seed + delta) % 100)
        elif key == "steps":
            self.params = with_params(p, steps=max(1, min(4, p.steps + delta)))
        elif key == "angle":
            self.params = with_params(p, angle=max(12, min(42, p.angle + 2 * delta)))
        elif key == "density":
            self.params = with_params(p, density=max(1, min(5, p.density + delta)))
        elif key == "tropism":
            self.params = with_params(p, tropism=max(0, min(4, p.tropism + delta)))
        elif key == "hour":
            self.params = with_params(p, hour=(p.hour + delta) % len(HOURS))

    def _hit(self, pos):
        if corner_hit(home_rect()).collidepoint(pos):
            return "home"
        if self.panel:
            if self._close_rect().collidepoint(pos):
                return "close"
            for key, _label, rect_m, rect_p in self._rows():
                if rect_m.collidepoint(pos) and self._enabled(key, -1):
                    return key + "-"
                if rect_p.collidepoint(pos) and self._enabled(key, 1):
                    return key + "+"
            return None
        if self._gear_rect().collidepoint(pos):
            return "gear"
        return None

    def _enabled(self, key, delta) -> bool:
        p = self.params
        if key == "steps":
            return (p.steps + delta) >= 1 and (p.steps + delta) <= 4
        if key == "angle":
            return 12 <= p.angle + 2 * delta <= 42
        if key == "density":
            return 1 <= p.density + delta <= 5
        if key == "tropism":
            return 0 <= p.tropism + delta <= 4
        return True

    def _gear_rect(self):
        return pygame.Rect(W // 2 - 116, H - 72, 232, 56)

    def _close_rect(self):
        return pygame.Rect(W // 2 - 110, 644, 220, 52)

    def _rows(self):
        out = []
        for i, (key, label) in enumerate(_ROWS):
            y = _ROW0 + i * _ROW_H
            out.append((
                key,
                label,
                pygame.Rect(468, y, 52, 52),
                pygame.Rect(636, y, 52, 52),
            ))
        return out

    def _value(self, key) -> str:
        p = self.params
        if key == "species":
            return p.title()
        if key == "hour":
            return HOURS[p.hour]
        return str(getattr(p, key))

    def _draw(self):
        eye = EYE + math.sin(self.beat * 0.8) * 0.012
        cam = Camera(self.z, self._view_yaw(), eye)
        render(self.screen.surf, self.garden.batch(), cam, self.params.hour, self.beat)
        draw_home(self.screen.surf, home_rect(), self.pressed == "home")
        if self.panel:
            self._draw_panel()
        else:
            draw_button(
                self.screen.surf, self.pixel, self._gear_rect(), "RÉGLAGES",
                self.pressed == "gear", 2,
            )

    def _draw_panel(self):
        surf = self.screen.surf
        pygame.draw.rect(surf, LINE, _PANEL.move(4, 4))
        pygame.draw.rect(surf, BG, _PANEL)
        pygame.draw.rect(surf, INK, _PANEL, 2)
        self.pixel.blit(surf, "RÉGLAGES", W // 2, 164, 3, INK, align="center")
        self.pixel.blit(
            surf, "L'AXE Y REGARDE SUR LE CÔTÉ", W // 2, 196, 2, MUTED, align="center",
        )
        for key, label, rect_m, rect_p in self._rows():
            self.pixel.blit(surf, label, 40, rect_m.y + 16, 2, INK)
            gap_x = rect_m.right
            gap_w = rect_p.left - rect_m.right
            self.pixel.blit(
                surf, self._value(key), gap_x + gap_w // 2, rect_m.y + 16,
                2, INK, align="center",
            )
            draw_button(
                surf, self.pixel, rect_m, "-",
                self.pressed == key + "-", 3, enabled=self._enabled(key, -1),
            )
            draw_button(
                surf, self.pixel, rect_p, "+",
                self.pressed == key + "+", 3, enabled=self._enabled(key, 1),
            )
        draw_button(
            surf, self.pixel, self._close_rect(), "FERMER",
            self.pressed == "close", 2,
        )
