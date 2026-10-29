"""Relief : tourner la Terre, zoomer, faire varier la mer."""

from __future__ import annotations

import argparse
import math

import numpy as np
import pygame

from device.screen import H, W, open_screen
from device.widgets import BAR, draw_button, draw_home, menu_rect, minus_rect, plus_rect
from relief.dem import Terrain
from relief.view import ALT_FAR, clamp_altitude, pan_degrees, render
from world3.font import Font
from world3.theme import BG, INK, LINE, MUTED, SEA

SEA_MIN = -140
SEA_MAX = 80
_TOP = BAR
_SLIDER = 600


def main(argv=None):
    parser = argparse.ArgumentParser(description="Relief et niveau des mers.")
    parser.add_argument("--fullscreen", action="store_true")
    parser.add_argument("--scale", type=int, default=1)
    args = parser.parse_args(argv)
    screen = open_screen(args.fullscreen, args.scale, "RELIEF")
    try:
        run(screen)
    finally:
        screen.close()


def run(screen) -> str:
    """'menu' pour revenir au choix, 'quit' si la fenetre se ferme."""
    return GlobeApp(screen).loop()


class GlobeApp:
    def __init__(self, screen):
        self.screen = screen
        self.pixel = Font()
        self.terrain = Terrain.load()
        self.lat = 18.0
        self.lon = 12.0
        self.altitude = ALT_FAR
        self.sea = 0
        self.mode = None
        self.anchor = None
        self.last = None
        self.moved = False
        self.dirty = True
        self.refine = True
        self.globe = None
        self.scaled = None

    def loop(self) -> str:
        clock = pygame.time.Clock()
        self._draw()
        self.screen.present()
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
                elif event.type == pygame.MOUSEWHEEL:
                    self._zoom(1.15 if event.y > 0 else 1.0 / 1.15)
            if leaving:
                return leaving
            if self.dirty:
                self._render(False)
                self.dirty = False
            elif self.refine and self.mode is None:
                self._render(True)
                self.refine = False
            self._draw()
            self.screen.present()
            clock.tick(30)

    def _key(self, key):
        if key == pygame.K_ESCAPE:
            return "menu"
        if key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
            self._zoom(1.35)
        elif key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self._zoom(1.0 / 1.35)
        return None

    def _down(self, pos):
        self.anchor = pos
        self.last = pos
        self.moved = False
        if self._menu_rect().collidepoint(pos):
            self.mode = "menu"
        elif self._plus_rect().collidepoint(pos):
            self.mode = "plus"
        elif self._minus_rect().collidepoint(pos):
            self.mode = "minus"
        elif pos[1] >= _SLIDER:
            self.mode = "sea"
            self._set_sea(pos[0])
        else:
            self.mode = "globe"

    def _move(self, pos):
        if self.anchor is not None:
            span = abs(pos[0] - self.anchor[0]) + abs(pos[1] - self.anchor[1])
            if span > 8:
                self.moved = True
        if self.mode == "globe":
            self._pan(pos[0] - self.last[0], pos[1] - self.last[1])
            self.last = pos
        elif self.mode == "sea":
            self._set_sea(pos[0])

    def _up(self, pos):
        mode = self.mode
        moved = self.moved
        self.mode = None
        self.anchor = None
        if mode == "menu" and not moved and self._menu_rect().collidepoint(pos):
            return "menu"
        if mode == "plus" and not moved and self._plus_rect().collidepoint(pos):
            self._zoom(1.35)
        elif mode == "minus" and not moved and self._minus_rect().collidepoint(pos):
            self._zoom(1.0 / 1.35)
        elif mode in ("globe", "sea"):
            self.refine = True
        return None

    def _pan(self, dx, dy):
        if dx == 0 and dy == 0:
            return
        scale = pan_degrees(self.altitude, self._view_rect().h)
        cos_lat = max(0.25, math.cos(math.radians(self.lat)))
        self.lon = _wrap(self.lon - dx * scale / cos_lat)
        self.lat = min(78.0, max(-78.0, self.lat + dy * scale))
        self.dirty = True
        self.refine = False

    def _zoom(self, factor):
        self.altitude = clamp_altitude(self.altitude / factor)
        self.dirty = True
        self.refine = True

    def _set_sea(self, x):
        track = self._track_rect()
        span = max(track.w, 1)
        t = min(1.0, max(0.0, (x - track.x) / span))
        sea = int(round(SEA_MIN + t * (SEA_MAX - SEA_MIN)))
        if sea == self.sea:
            return
        self.sea = sea
        self.dirty = True
        self.refine = False

    def _render(self, fine):
        width, height = self._buffer(fine)
        image = render(
            self.terrain, self.lat, self.lon, self.altitude, self.sea,
            width, height, 14 if fine else 8,
        )
        self.globe = pygame.surfarray.make_surface(np.transpose(image, (1, 0, 2)))
        self.scaled = None

    def _buffer(self, fine):
        view = self._view_rect()
        longest = 420 if fine else 240
        scale = min(1.0, longest / max(view.w, view.h))
        return max(2, int(view.w * scale)), max(2, int(view.h * scale))

    def _view_rect(self):
        return pygame.Rect(0, _TOP, W, _SLIDER - _TOP)

    def _menu_rect(self):
        return menu_rect()

    def _plus_rect(self):
        return plus_rect(self._view_rect())

    def _minus_rect(self):
        return minus_rect(self._view_rect())

    def _track_rect(self):
        return pygame.Rect(48, 662, W - 96, 8)

    def _draw(self):
        surf = self.screen.surf
        surf.fill(BG)
        self._draw_globe(surf)
        pygame.draw.rect(surf, BG, (0, 0, W, _TOP))
        pygame.draw.line(surf, LINE, (0, _TOP - 1), (W, _TOP - 1))
        draw_home(surf, self._menu_rect(), self.mode == "menu", ground="dark")
        title_h = self.pixel.height(3)
        self.pixel.blit(surf, "RELIEF", W // 2, (_TOP - title_h) // 2, 3, MUTED, align="center")
        draw_button(surf, self.pixel, self._plus_rect(), "+", self.mode == "plus", 3)
        draw_button(surf, self.pixel, self._minus_rect(), "-", self.mode == "minus", 3)
        self._draw_slider(surf)

    def _draw_globe(self, surf):
        if self.globe is None:
            return
        view = self._view_rect()
        if self.scaled is None or self.scaled.get_size() != view.size:
            if self.globe.get_size() == view.size:
                self.scaled = self.globe
            else:
                self.scaled = pygame.transform.scale(self.globe, view.size)
        surf.blit(self.scaled, view.topleft)

    def _draw_slider(self, surf):
        self.pixel.blit(surf, "NIVEAU", 48, 618, 2, MUTED)
        self.pixel.blit(surf, self._level(), W // 2, 612, 4, INK, align="center")
        track = self._track_rect()
        pygame.draw.rect(surf, LINE, track)
        zero = self._x_of(0)
        pygame.draw.line(surf, MUTED, (zero, track.y - 6), (zero, track.bottom + 6), 2)
        t = (self.sea - SEA_MIN) / (SEA_MAX - SEA_MIN)
        filled = pygame.Rect(track.x, track.y, max(1, int(track.w * t)), track.h)
        pygame.draw.rect(surf, SEA, filled)
        thumb = pygame.Rect(0, 0, 22, 28)
        thumb.center = (self._x_of(self.sea), track.centery)
        face = thumb.move(2, 2) if self.mode == "sea" else thumb
        pygame.draw.rect(surf, INK, face)
        self.pixel.blit(surf, "-140", track.x, 684, 2, MUTED)
        self.pixel.blit(surf, "+80", track.right, 684, 2, MUTED, align="right")

    def _x_of(self, sea):
        track = self._track_rect()
        t = (sea - SEA_MIN) / (SEA_MAX - SEA_MIN)
        return track.x + int(t * track.w)

    def _level(self):
        if self.sea > 0:
            return f"+{self.sea} M"
        return f"{self.sea} M"


def _wrap(lon):
    return (lon + 180.0) % 360.0 - 180.0
