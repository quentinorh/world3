"""Galerie des couvertures, puis lecture, sans reseau."""

from __future__ import annotations

import argparse
import re

import pygame

from device.screen import H, W, open_screen
from device.widgets import BAR, HOME, draw_button, draw_home
from sp2050.library import catalog_mtime, load_stories
from sp2050.sync import maybe_start, running
from sp2050.theme import INK, LINE, MUTED, PAPER
from world3.font import Font

_HEADER = BAR
_NAV_X = 20
_NAV_BACK = 156
# L'ombre du bouton descend de 4 px. On la compte pour centrer le bloc.
_NAV_Y = (_HEADER - HOME - 4) // 2
_GAP = 12
_TEXT_X = 36
_TEXT_W = W - _TEXT_X * 2
# Les fichiers font 480×672. Le bloc divise 720 et la hauteur pleine largeur.
_BLOCK = 3
_COVER_W = 480
_COVER_H = 672
_FALLBACK_H = 220


def main(argv=None):
    parser = argparse.ArgumentParser(description="SP2050, lire les futurs hors ligne.")
    parser.add_argument("--fullscreen", action="store_true")
    parser.add_argument("--scale", type=int, default=1)
    args = parser.parse_args(argv)
    maybe_start(force=not load_stories())
    screen = open_screen(args.fullscreen, args.scale, "SP2050")
    try:
        run(screen)
    finally:
        screen.close()


def run(screen) -> str:
    """'menu' pour revenir au choix, 'quit' si la fenetre se ferme."""
    return Reader(screen).loop()


def pixel_size(width, src_w, src_h, block=_BLOCK):
    """Largeur pleine, hauteur au rapport, les deux multiples du bloc."""
    if src_w <= 0 or src_h <= 0:
        src_w, src_h = _COVER_W, _COVER_H
    small_w = max(1, width // block)
    small_h = max(1, int(round(width * src_h / src_w / block)))
    return small_w * block, small_h * block


def pixel_cover(image, width, block=_BLOCK):
    """Gros pixels : moyenne en petit, puis agrandi au plus proche."""
    iw, ih = image.get_size()
    if iw <= 0 or ih <= 0:
        surf = pygame.Surface((width, _FALLBACK_H))
        surf.fill(PAPER)
        return surf
    out_w, out_h = pixel_size(width, iw, ih, block)
    small = pygame.transform.smoothscale(image, (out_w // block, out_h // block))
    return pygame.transform.scale(small, (out_w, out_h))


def _paragraphs(body: str):
    chunks = re.split(r"\n\s*\n", (body or "").strip())
    out = []
    for chunk in chunks:
        text = re.sub(r"\s+", " ", chunk).strip()
        if text:
            out.append(text)
    return out


class Reader:
    def __init__(self, screen):
        self.screen = screen
        self.pixel = Font()
        self.stories = []
        self.seen = -1.0
        self.images = {}
        self.story = None
        self.layout = None
        self.scroll = 0.0
        self.held = None
        self.drag = 0.0
        self.anchor = 0.0
        self.armed = None
        self.bar = pygame.Surface((W, _HEADER))
        self.bar.fill(PAPER)
        self.reload()

    def reload(self):
        self.stories = load_stories()
        self.seen = catalog_mtime()
        alive = {story.id for story in self.stories}
        for sid in list(self.images):
            if sid not in alive:
                self.images.pop(sid, None)

    def loop(self) -> str:
        clock = pygame.time.Clock()
        while True:
            if catalog_mtime() != self.seen:
                self.reload()
                if self.story is not None:
                    fresh = next((s for s in self.stories if s.id == self.story.id), None)
                    if fresh is None:
                        self.story = None
                        self.layout = None
                        self.scroll = 0.0
                    else:
                        self.images.pop(fresh.id, None)
                        self.story = fresh
                        self.layout = self._layout(fresh)
            self.screen.poll()
            leaving = None
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "quit"
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    leaving = self._back()
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self._down(self.screen.logical(event.pos))
                elif event.type == pygame.MOUSEMOTION and self.held is not None:
                    self._move(self.screen.logical(event.pos))
                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    leaving = self._up(self.screen.logical(event.pos))
                elif event.type == pygame.MOUSEWHEEL:
                    self.scroll -= event.y * 48
                    self._clamp()
            if leaving == "quit":
                return "quit"
            if leaving == "menu":
                return "menu"
            self._draw()
            self.screen.present()
            clock.tick(30)

    def _back(self):
        if self.story is not None:
            self.story = None
            self.layout = None
            self.scroll = 0.0
            self.held = None
            return None
        return "menu"

    def _back_rect(self):
        if self.story is None:
            return pygame.Rect(_NAV_X, _NAV_Y, HOME, HOME)
        return pygame.Rect(_NAV_X, _NAV_Y, _NAV_BACK, HOME)

    def _nav_label_y(self, scale):
        """Haut du texte, centré sur la face du bouton, pas sur la barre."""
        return _NAV_Y + (HOME - self.pixel.height(scale)) // 2

    def _down(self, pos):
        self.held = pos
        self.drag = 0.0
        self.anchor = self.scroll
        self.armed = "back" if self._back_rect().collidepoint(pos) else None

    def _move(self, pos):
        if self.held is None:
            return
        dy = pos[1] - self.held[1]
        self.drag = max(self.drag, abs(dy))
        if self.drag >= 12:
            self.armed = None
            self.scroll = self.anchor - dy
            self._clamp()

    def _up(self, pos):
        held = self.held
        drag = self.drag
        armed = self.armed
        self.held = None
        self.armed = None
        if held is None or drag >= 12:
            return None
        if armed == "back":
            if self._back_rect().collidepoint(pos):
                return self._back() if self.story is not None else "menu"
            return None
        if self.story is None:
            return self._tap_gallery(pos)
        return None

    def _tap_gallery(self, pos):
        if pos[1] < _HEADER:
            return None
        for index, story in enumerate(self.stories):
            rect = self._card_rect(index)
            if rect.collidepoint(pos):
                self.story = story
                self.layout = self._layout(story)
                self.scroll = 0.0
                return None
        return None

    def _cover_height(self, story):
        if story.id in self.images:
            image = self.images[story.id]
            return image.get_height() if image is not None else _FALLBACK_H
        if story.cover is None:
            return _FALLBACK_H
        return pixel_size(W, _COVER_W, _COVER_H)[1]

    def _card_rect(self, index):
        y = _HEADER
        for story in self.stories[:index]:
            y += self._cover_height(story) + _GAP
        return pygame.Rect(0, int(y - self.scroll), W, self._cover_height(self.stories[index]))

    def _max_scroll(self):
        if self.story is not None and self.layout is not None:
            return max(0, self.layout[0] - (H - _HEADER))
        if not self.stories:
            return 0
        content = _HEADER
        for story in self.stories:
            content += self._cover_height(story) + _GAP
        return max(0, content + 12 - H)

    def _clamp(self):
        self.scroll = max(0.0, min(float(self._max_scroll()), self.scroll))

    def _image(self, story):
        if story.cover is None:
            return None
        if story.id in self.images:
            return self.images[story.id]
        try:
            raw = pygame.image.load(story.cover).convert()
            image = pixel_cover(raw, W)
        except pygame.error:
            image = None
        self.images[story.id] = image
        return image

    def _layout(self, story):
        """(hauteur, pieces) sous la barre. Les y sont dans ce bloc."""
        pieces = []
        y = 0
        image = self._image(story)
        if image is not None:
            pieces.append(("image", y, 0, image))
            y += image.get_height() + 20
        else:
            y += 16
        left = []
        if story.when:
            left.append("Publié le")
            left.append(story.when)
        right = []
        if story.reading_time:
            right.append("Lecture")
            right.append(story.reading_time)
        if left or right:
            pieces.append(("meta", y, " ".join(left), " ".join(right), 2))
            y += self.pixel.step(2) + 10
            pieces.append(("rule", y))
            y += 18
        body = 3
        step = self.pixel.step(body)
        gap = 14
        for para in _paragraphs(story.body):
            for line in self.pixel.wrap(para, _TEXT_W, body):
                pieces.append(("text", y, body, line, INK))
                y += step
            y += gap
        if not story.body:
            pieces.append(("text", y, body, "Ce futur n'a pas de texte.", MUTED))
            y += step
        y += 12
        note = 2
        if story.author:
            license_line = (
                f"Texte publié par {story.author} "
                "sous licence Creative Commons BY-NC-SA 4.0."
            )
        else:
            license_line = "Texte publié sous licence Creative Commons BY-NC-SA 4.0."
        for line in self.pixel.wrap(license_line, _TEXT_W, note):
            pieces.append(("text", y, note, line, MUTED))
            y += self.pixel.step(note)
        y += 36
        return y, pieces

    def _draw(self):
        surf = self.screen.surf
        surf.fill(PAPER)
        if self.story is None:
            self._draw_gallery(surf)
        else:
            self._draw_story(surf)
        self._draw_header(surf)

    def _draw_header(self, surf):
        surf.blit(self.bar, (0, 0))
        pygame.draw.line(surf, LINE, (0, _HEADER - 1), (W, _HEADER - 1))
        if self.story is None:
            draw_home(surf, self._back_rect(), self.armed == "back", ground="light")
        else:
            draw_button(
                surf, self.pixel, self._back_rect(), "RETOUR",
                self.armed == "back", 2,
            )
        self.pixel.blit(
            surf, "SP2050", W // 2, self._nav_label_y(3),
            3, INK, align="center",
        )
        if self.story is None and running():
            self.pixel.blit(
                surf, "SYNCHRO", W - 24, self._nav_label_y(2),
                2, MUTED, align="right",
            )

    def _draw_gallery(self, surf):
        if not self.stories:
            self._draw_empty(surf)
            return
        for index, story in enumerate(self.stories):
            rect = self._card_rect(index)
            if rect.bottom < _HEADER or rect.top > H:
                continue
            card = self._image(story)
            if card is not None:
                surf.blit(card, rect.topleft)
            else:
                pygame.draw.rect(surf, (236, 234, 230), rect)
                self._draw_card_title(surf, rect, story.title or "Futur")

    def _draw_card_title(self, surf, rect, title):
        scale = 2
        lines = self.pixel.wrap(title, rect.w - 24, scale)
        if not lines:
            return
        step = self.pixel.step(scale)
        block = step * len(lines)
        y = rect.centery - block // 2
        for line in lines:
            self.pixel.blit(
                surf, line, rect.centerx, y, scale, INK,
                align="center", case="keep",
            )
            y += step

    def _draw_empty(self, surf):
        y = 260
        self.pixel.blit(surf, "SP2050", W // 2, y, 5, INK, align="center")
        y += self.pixel.height(5) + 28
        if running():
            lines = ["Récupération des futurs…"]
        else:
            lines = [
                "Les textes ne sont pas encore là.",
                "Ils arriveront à la prochaine connexion.",
            ]
        for line in lines:
            self.pixel.blit(surf, line, W // 2, y, 2, MUTED, align="center", case="keep")
            y += self.pixel.step(2)

    def _draw_story(self, surf):
        if self.layout is None:
            return
        _height, pieces = self.layout
        origin = _HEADER - self.scroll
        for piece in pieces:
            kind = piece[0]
            if kind == "image":
                _k, y, x, image = piece
                top = origin + y
                if top > H or top + image.get_height() < _HEADER:
                    continue
                surf.blit(image, (x, int(top)))
            elif kind == "text":
                _k, y, scale, line, color = piece
                top = origin + y
                if top > H or top + self.pixel.step(scale) < _HEADER:
                    continue
                self.pixel.blit(surf, line, _TEXT_X, top, scale, color, case="keep")
            elif kind == "meta":
                _k, y, left, right, scale = piece
                top = origin + y
                if _HEADER - 20 <= top <= H:
                    if left:
                        self.pixel.blit(surf, left, _TEXT_X, top, scale, MUTED, case="keep")
                    if right:
                        self.pixel.blit(
                            surf, right, W - _TEXT_X, top, scale, MUTED,
                            align="right", case="keep",
                        )
            elif kind == "rule":
                _k, y = piece
                top = origin + y
                if _HEADER <= top <= H:
                    pygame.draw.line(surf, LINE, (_TEXT_X, int(top)), (W - _TEXT_X, int(top)))


