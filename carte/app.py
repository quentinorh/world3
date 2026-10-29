"""Carte OpenStreetMap hors ligne. Un doigt deplace, + et - zooment."""

from __future__ import annotations

import argparse
import math
from collections import OrderedDict
from pathlib import Path

import pygame

from carte.draw import blit_labels, render_tile
from carte.pmtiles import Archive
from carte.style import INK, PAPER, SEA
from carte.view import (
    HOME_LAT,
    HOME_LON,
    HOME_ZOOM,
    TILE,
    approach_zoom,
    clamp_zoom,
    data_zoom,
    paint_zoom,
    pan,
    parent_tile,
    screen_box,
    tile_screen_rects,
    tiles_in_view,
)
from device.screen import H, W, open_screen
from device.widgets import draw_button, draw_home, menu_rect, minus_rect, plus_rect
from world3.font import Font

_CACHE = 64
_EMPTY = object()
# Au-dela, on ne met pas toute la tuile en memoire : seul le morceau visible.
_SCALE_LIMIT = TILE * 2
# Tuiles hors cadre + parents du niveau precedent (bords deja en cache).
_PRELOAD_PAD = 1


def archive_path():
    return Path(__file__).resolve().parent.parent / "var" / "carte" / "terre.pmtiles"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Carte OpenStreetMap hors ligne.")
    parser.add_argument("--fullscreen", action="store_true")
    parser.add_argument("--scale", type=int, default=1)
    args = parser.parse_args(argv)
    screen = open_screen(args.fullscreen, args.scale, "CARTE")
    try:
        run(screen)
    finally:
        screen.close()


def run(screen, path=None) -> str:
    """'menu' pour revenir au choix, 'quit' si la fenetre se ferme."""
    return MapApp(screen, path).loop()


def paint_missing(surf, broken, font=None):
    surf.fill(PAPER)
    if font is None:
        font = Font()
    lines = (
        ("La carte est illisible." if broken else "La carte n'est pas sur cet appareil.", 3),
        ("Sur l'ordinateur :", 2),
        ("python -m carte.fetch", 2),
    )
    gap = 16
    block = sum(font.step(scale) for _text, scale in lines) + gap * (len(lines) - 1)
    y = (H - block) // 2 - 24
    for index, (text, scale) in enumerate(lines):
        font.blit(surf, text, W // 2, y, scale, INK, align="center", case="keep")
        y += font.step(scale)
        if index + 1 < len(lines):
            y += gap


class MapApp:
    def __init__(self, screen, path=None):
        self.screen = screen
        self.pixel = Font()
        self.path = Path(path) if path is not None else archive_path()
        self.archive = None
        self.broken = False
        if self.path.is_file():
            try:
                self.archive = Archive(self.path)
            except Exception:
                self.broken = True
        self.lat = HOME_LAT
        self.lon = HOME_LON
        self.zoom = HOME_ZOOM
        self.zoom_target = HOME_ZOOM
        self.drag = False
        self.mode = None
        self.anchor = None
        self.last = None
        self.moved = False
        self.cache = OrderedDict()
        self.ready = {}

    def loop(self) -> str:
        clock = pygame.time.Clock()
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
                    elif event.type == pygame.MOUSEMOTION and self.drag:
                        self._move(self.screen.logical(event.pos))
                    elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                        leaving = self._up(self.screen.logical(event.pos))
                    elif event.type == pygame.MOUSEWHEEL and self.archive is not None:
                        self._set_zoom(self.zoom + (0.5 if event.y > 0 else -0.5))
                if leaving:
                    return leaving
                self._paint()
                self.screen.present()
                clock.tick(30)
        finally:
            if self.archive is not None:
                self.archive.close()
                self.archive = None

    def _key(self, key):
        if key == pygame.K_ESCAPE:
            return "menu"
        if self.archive is None:
            return None
        if key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
            self._set_zoom(self.zoom + 1)
        elif key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self._set_zoom(self.zoom - 1)
        return None

    def _down(self, pos):
        self.anchor = pos
        self.last = pos
        self.moved = False
        if self._menu_rect().collidepoint(pos):
            self.mode = "menu"
        elif self.archive is not None and self._plus_rect().collidepoint(pos):
            self.mode = "plus"
        elif self.archive is not None and self._minus_rect().collidepoint(pos):
            self.mode = "minus"
        elif self.archive is not None:
            self.mode = "map"
            self.drag = True
        else:
            self.mode = None

    def _move(self, pos):
        if self.anchor is not None:
            span = abs(pos[0] - self.anchor[0]) + abs(pos[1] - self.anchor[1])
            if span > 8:
                self.moved = True
        if self.mode != "map":
            return
        self.lat, self.lon = pan(
            self.lon, self.lat, self.zoom,
            pos[0] - self.last[0], pos[1] - self.last[1],
        )
        self.last = pos

    def _up(self, pos):
        mode = self.mode
        moved = self.moved
        self.mode = None
        self.drag = False
        self.anchor = None
        if mode == "menu" and not moved and self._menu_rect().collidepoint(pos):
            return "menu"
        if self.archive is None:
            return None
        if mode == "plus" and not moved and self._plus_rect().collidepoint(pos):
            self._set_zoom(self.zoom + 1)
        elif mode == "minus" and not moved and self._minus_rect().collidepoint(pos):
            self._set_zoom(self.zoom - 1)
        return None

    def _set_zoom(self, zoom):
        self.zoom_target = clamp_zoom(zoom)

    def _paint(self):
        surf = self.screen.surf
        if self.archive is None:
            paint_missing(surf, self.broken, self.pixel)
            draw_home(surf, self._menu_rect(), self.mode == "menu", ground="light")
            return
        self.zoom = approach_zoom(self.zoom, self.zoom_target)
        surf.fill(SEA)
        span, tiles = tiles_in_view(self.lon, self.lat, self.zoom, W, H)
        moving = self.drag or self.zoom != self.zoom_target
        budget = 0 if moving else self._budget()
        decoded = self._fill_visible(tiles, budget)
        if any((z, x, y) not in self.cache for z, x, y, _sx, _sy in tiles):
            self._draw_backdrop(surf)
        labels = []
        for z, x, y, sx, sy in tiles:
            key = (z, x, y)
            cached = self.cache.get(key)
            if cached is None or cached is _EMPTY:
                continue
            self.cache.move_to_end(key)
            image, tile_labels = cached
            self._blit_tile(key, image, sx, sy, span)
            factor = span / image.get_width()
            for label in tile_labels:
                labels.append({
                    "text": label["text"],
                    "x": sx + label["x"] * factor,
                    "y": sy + label["y"] * factor,
                    "size": label["size"],
                    "rank": label["rank"],
                })
        if not moving and decoded < budget:
            self._prefetch(tiles, budget - decoded)
        blit_labels(surf, labels, self.pixel, W, H)
        draw_home(surf, self._menu_rect(), self.mode == "menu", ground="light")
        draw_button(surf, self.pixel, self._plus_rect(), "+", self.mode == "plus", 3)
        draw_button(surf, self.pixel, self._minus_rect(), "-", self.mode == "minus", 3)
        self._credit(surf)

    def _budget(self):
        if self.drag:
            return 0
        if paint_zoom(self.zoom) >= 8:
            return 1
        return 4

    def _fill_visible(self, tiles, budget):
        """Charge les tuiles a l'ecran. Dessinees a TILE, puis agrandies x2+."""
        decoded = 0
        for z, x, y, _sx, _sy in tiles:
            if decoded >= budget:
                break
            key = (z, x, y)
            cached = self.cache.get(key)
            if cached is not None:
                continue
            fresh = self._load(z, x, y)
            if fresh is None:
                self._store(key, _EMPTY)
            else:
                decoded += 1
                self._store(key, fresh)
        return decoded

    def _prefetch(self, visible, budget):
        """Bords affiches, parent (fond), et niveau vue pour le prochain zoom."""
        if budget <= 0:
            return
        decoded = 0
        _, rim = tiles_in_view(
            self.lon, self.lat, self.zoom, W, H, pad=_PRELOAD_PAD,
        )
        seen = {(z, x, y) for z, x, y, _sx, _sy in visible}
        queue = []
        for z, x, y, _sx, _sy in rim:
            key = (z, x, y)
            if key not in seen:
                queue.append(key)
        for z, x, y, _sx, _sy in visible:
            parent = parent_tile(z, x, y)
            if parent is not None:
                queue.append(parent)
        # Niveau de la vue (souvent paint+1) : deja la pour zoomer d'un cran.
        nxt = data_zoom(self.zoom)
        if nxt != paint_zoom(self.zoom):
            _, sharper = tiles_in_view(
                self.lon, self.lat, self.zoom, W, H, source_z=nxt,
            )
            for z, x, y, _sx, _sy in sharper:
                queue.append((z, x, y))
        for key in queue:
            if decoded >= budget:
                return
            if key in self.cache:
                continue
            z, x, y = key
            fresh = self._load(z, x, y)
            if fresh is None:
                self._store(key, _EMPTY)
            else:
                decoded += 1
                self._store(key, fresh)

    def _draw_backdrop(self, surf):
        """Encore un cran en dessous, agrandi, si le niveau affiche manque."""
        tz = paint_zoom(self.zoom)
        levels = {
            key[0]
            for key, value in self.cache.items()
            if value is not _EMPTY and key[0] != tz
        }
        if not levels:
            return
        source = min(levels, key=lambda level: (abs(level - (tz - 1)), abs(level - tz), -level))
        for key, value in list(self.cache.items()):
            z, x, y = key
            if z != source or value is _EMPTY:
                continue
            image = value[0]
            for sx, sy, tile_span in tile_screen_rects(
                self.lon, self.lat, self.zoom, z, x, y, W, H,
            ):
                self._blit_tile(key, image, sx, sy, tile_span)
            self.cache.move_to_end(key)

    def _blit_tile(self, key, image, sx, sy, span):
        x0, y0, w, h = screen_box(sx, sy, span)
        if w <= _SCALE_LIMIT and h <= _SCALE_LIMIT:
            if w == image.get_width() and h == image.get_height():
                self.screen.surf.blit(image, (x0, y0))
                return
            self.screen.surf.blit(self._scaled(key, image, w, h), (x0, y0))
            return
        self._blit_cropped(image, sx, sy, span)

    def _scaled(self, key, image, w, h):
        slot = (key, w, h)
        found = self.ready.get(slot)
        if found is not None:
            return found
        scaled = pygame.transform.scale(image, (w, h))
        if self.zoom == self.zoom_target and key[0] == paint_zoom(self.zoom):
            if len(self.ready) > _CACHE:
                self.ready.clear()
            self.ready[slot] = scaled
        return scaled

    def _blit_cropped(self, image, sx, sy, span):
        cx0 = max(sx, 0.0)
        cy0 = max(sy, 0.0)
        cx1 = min(sx + span, float(W))
        cy1 = min(sy + span, float(H))
        if cx1 - cx0 < 1 or cy1 - cy0 < 1:
            return
        iw, ih = image.get_size()
        iu0 = max(0, min(iw - 1, int(math.floor((cx0 - sx) / span * iw))))
        iv0 = max(0, min(ih - 1, int(math.floor((cy0 - sy) / span * ih))))
        iu1 = max(iu0 + 1, min(iw, int(math.ceil((cx1 - sx) / span * iw))))
        iv1 = max(iv0 + 1, min(ih, int(math.ceil((cy1 - sy) / span * ih))))
        dw = max(1, int(round(cx1 - cx0)))
        dh = max(1, int(round(cy1 - cy0)))
        src = image.subsurface((iu0, iv0, iu1 - iu0, iv1 - iv0))
        self.screen.surf.blit(pygame.transform.scale(src, (dw, dh)), (int(round(cx0)), int(round(cy0))))

    def _store(self, key, value):
        self.cache[key] = value
        self.cache.move_to_end(key)
        self._forget_ready(key)
        while len(self.cache) > _CACHE:
            victim = None
            for old, item in self.cache.items():
                if item is _EMPTY:
                    victim = old
                    break
            if victim is None:
                victim = next(iter(self.cache))
            del self.cache[victim]
            self._forget_ready(victim)

    def _forget_ready(self, key):
        if not self.ready:
            return
        self.ready = {slot: image for slot, image in self.ready.items() if slot[0] != key}

    def _load(self, z, x, y):
        """Dessine la tuile a TILE px. L'ecran l'agrandit (effet pixel-art)."""
        try:
            payload = self.archive.tile(z, x, y)
        except Exception:
            payload = b""
        if not payload:
            return None
        # Le style suit le zoom des donnees : au-dela, c'est l'agrandissement
        # qui grossit les traits, pas un nouveau dessin vectoriel.
        style_zoom = float(z)
        try:
            return render_tile(payload, TILE, style_zoom)
        except Exception:
            blank = pygame.Surface((TILE, TILE))
            blank.fill(SEA)
            return blank, ()

    def _menu_rect(self):
        return menu_rect()

    def _plus_rect(self):
        return plus_rect(pygame.Rect(0, 0, W, H))

    def _minus_rect(self):
        return minus_rect(pygame.Rect(0, 0, W, H))

    def _credit(self, surf):
        label = "© OPENSTREETMAP"
        scale = 2
        width = self.pixel.width(label, scale)
        height = self.pixel.height(scale)
        x = 16
        y = H - 16 - height
        box = pygame.Rect(x - 8, y - 6, width + 16, height + 12)
        pygame.draw.rect(surf, PAPER, box)
        self.pixel.blit(surf, label, x, y, scale, INK)
