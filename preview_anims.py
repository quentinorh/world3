"""Passe en revue chaque animation de carte.

    python preview_anims.py

Fleches ou clic : une carte. Espace : rejouer. Echap : fermer.
"""

import argparse
from pathlib import Path

import pygame

from world3.anims import (
    CW,
    REVEAL_DUR,
    REVEAL_HOLD,
    SCALE,
    catalog,
    render_anim,
)
from world3.font import Font
from world3.theme import BG, DIM, INK, LINE, MUTED, OCHRE, W, H

WIN_W, WIN_H = 1180, 720
LIST_W = 430
CYCLE = REVEAL_DUR + REVEAL_HOLD


def anim_u(elapsed):
    if elapsed < REVEAL_DUR:
        return elapsed / REVEAL_DUR
    return 1.0


def build_rows(items):
    rows = []
    y = 12
    group = None
    for i, item in enumerate(items):
        if item["group"] != group:
            group = item["group"]
            rows.append({"type": "head", "text": group, "y": y})
            y += 28
        rows.append({"type": "item", "i": i, "y": y, "item": item})
        y += 34
    return rows, y + 12


def row_scroll(rows, sel, scroll):
    for row in rows:
        if row["type"] == "item" and row["i"] == sel:
            if row["y"] - scroll < 8:
                return max(0, row["y"] - 8)
            bottom = row["y"] + 32
            if bottom - scroll > WIN_H - 8:
                return bottom - (WIN_H - 8)
            return scroll
    return scroll


def draw_preview(surf, font, items, rows, sel, scroll, elapsed):
    surf.fill(BG)
    pygame.draw.rect(surf, LINE, (LIST_W, 0, 1, WIN_H))
    view = pygame.Rect(0, 0, LIST_W, WIN_H)
    surf.set_clip(view)
    for row in rows:
        y = row["y"] - scroll
        if y > WIN_H or y + 34 < 0:
            continue
        if row["type"] == "head":
            font.blit(surf, row["text"], 16, y, 2, OCHRE)
            continue
        item = row["item"]
        if row["i"] == sel:
            pygame.draw.rect(surf, LINE, (8, y - 4, LIST_W - 20, 30))
        color = INK if row["i"] == sel else MUTED
        font.blit(surf, item["meta"], 16, y, 2, OCHRE if row["i"] == sel else DIM)
        font.blit(surf, item["title"], 16 + font.width(item["meta"], 2) + 14, y, 2, color)
    surf.set_clip(None)

    item = items[sel]
    pane_x = LIST_W + (WIN_W - LIST_W) // 2
    render_anim(surf, item["key"], anim_u(elapsed), (pane_x, 250), SCALE)
    bar_w = CW * SCALE
    bar_x = pane_x - bar_w // 2
    bar_y = 250 + (36 * SCALE) // 2 + 16
    pygame.draw.rect(surf, LINE, (bar_x, bar_y, bar_w, 4))
    pygame.draw.rect(surf, OCHRE, (bar_x, bar_y, int(bar_w * anim_u(elapsed)), 4))

    tag = "ÉVÉNEMENT" if item["key"][0] == "shock" else "DILEMME"
    font.blit(surf, tag, pane_x, bar_y + 18, 2, OCHRE if tag == "ÉVÉNEMENT" else INK, align="center")
    font.blit(surf, item["title"], pane_x, bar_y + 46, 4, INK, align="center")
    for i, line in enumerate(item["lines"]):
        font.blit(surf, line, pane_x, bar_y + 92 + i * 28, 2, MUTED, align="center")
    if item["effect"]:
        font.blit(surf, item["effect"], pane_x, bar_y + 156, 2, OCHRE, align="center")
    code = f"{item['key'][0]}:{item['key'][1]}   {sel + 1}/{len(items)}"
    font.blit(surf, code, pane_x, WIN_H - 58, 2, DIM, align="center")
    font.blit(surf, "FLÈCHES  SUIVANT    ESPACE  REJOUER    ÉCHAP  FERMER", pane_x, WIN_H - 28, 2, DIM, align="center")


def hit_index(rows, scroll, pos):
    if pos[0] >= LIST_W:
        return None
    y = pos[1] + scroll
    for row in rows:
        if row["type"] == "item" and row["y"] - 4 <= y <= row["y"] + 28:
            return row["i"]
    return None


def loop():
    pygame.init()
    pygame.display.set_caption("WORLD3  animations")
    pygame.key.set_repeat(280, 45)
    window = pygame.display.set_mode((WIN_W, WIN_H))
    font = Font()
    items = catalog()
    rows, content_h = build_rows(items)
    sel = 0
    scroll = 0
    elapsed = 0.0
    clock = pygame.time.Clock()
    alive = True
    while alive:
        dt = clock.tick(30) / 1000
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                alive = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    alive = False
                elif event.key in (pygame.K_DOWN, pygame.K_RIGHT):
                    sel = (sel + 1) % len(items)
                    elapsed = 0.0
                elif event.key in (pygame.K_UP, pygame.K_LEFT):
                    sel = (sel - 1) % len(items)
                    elapsed = 0.0
                elif event.key == pygame.K_PAGEUP:
                    sel = max(0, sel - 8)
                    elapsed = 0.0
                elif event.key == pygame.K_PAGEDOWN:
                    sel = min(len(items) - 1, sel + 8)
                    elapsed = 0.0
                elif event.key == pygame.K_HOME:
                    sel = 0
                    elapsed = 0.0
                elif event.key == pygame.K_END:
                    sel = len(items) - 1
                    elapsed = 0.0
                elif event.key in (pygame.K_SPACE, pygame.K_RETURN):
                    elapsed = 0.0
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                picked = hit_index(rows, scroll, event.pos)
                if picked is None:
                    elapsed = 0.0
                else:
                    sel = picked
                    elapsed = 0.0
            elif event.type == pygame.MOUSEWHEEL:
                scroll -= event.y * 48
        elapsed += dt
        if elapsed >= CYCLE:
            elapsed = 0.0
        scroll = row_scroll(rows, sel, scroll)
        scroll = max(0, min(scroll, max(0, content_h - WIN_H)))
        draw_preview(window, font, items, rows, sel, scroll, elapsed)
        pygame.display.flip()
    pygame.quit()


def save_sheets(folder):
    pygame.init()
    font = pygame.font.SysFont("consolas", 16)
    items = catalog()
    scale = 3
    fw, fh = CW * scale, 36 * scale
    label_w = 230
    frames = (0.08, 0.5, 1.0)
    groups = []
    bucket = []
    current = None
    for item in items:
        if item["group"] != current:
            if bucket:
                groups.append((current, bucket))
            current = item["group"]
            bucket = []
        bucket.append(item)
    if bucket:
        groups.append((current, bucket))

    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    chunk = []

    def flush(name, rows):
        if not rows:
            return
        height = 28 + len(rows) * (fh + 12)
        width = label_w + len(frames) * (fw + 10) + 16
        sheet = pygame.Surface((width, height))
        sheet.fill(BG)
        title = pygame.font.SysFont("consolas", 20)
        sheet.blit(title.render(name, True, OCHRE), (12, 4))
        for i, item in enumerate(rows):
            y = 28 + i * (fh + 12)
            sheet.blit(font.render(item["meta"], True, OCHRE), (12, y + 8))
            sheet.blit(font.render(item["title"], True, INK), (12, y + 30))
            code = f"{item['key'][0]}:{item['key'][1]}"
            sheet.blit(font.render(code, True, DIM), (12, y + 52))
            for n, t in enumerate(frames):
                buf = pygame.Surface((720, 720))
                buf.fill((0, 0, 0))
                render_anim(buf, item["key"], t, (360, 360), scale)
                # L'animation est centree : on en coupe le sprite.
                side = fw
                tall = fh
                cut = pygame.Surface((side, tall))
                cut.blit(buf, (0, 0), (360 - side // 2, 360 - tall // 2, side, tall))
                sheet.blit(cut, (label_w + n * (fw + 10), y))
        path = folder / f"{name.lower().replace(' ', '_')}.png"
        pygame.image.save(sheet, str(path))
        paths.append(path)

    for name, rows in groups:
        if len(rows) <= 12:
            flush(name, rows)
            continue
        flush(name + " A", rows[:12])
        flush(name + " B", rows[12:])

    # Le label des cartes, en haut a gauche.
    from world3.content import EVENTS, SHOCKS
    from world3.render import Hits, draw_event, draw_shock
    from world3.font import Font as Pixel

    pixel = Pixel()
    card = pygame.Surface((W, H))
    card.fill(BG)

    class App:
        pressed = None
        event = EVENTS[0]
        shock = None
        state = type("S", (), {"year": 2031, "horizon": 2100})()

        def choose(self, _key):
            return None

        def dismiss_shock(self):
            return None

        def shock_traj(self):
            return None

        def traj(self):
            return None

    app = App()
    draw_event(card, pixel, app, Hits())
    pygame.image.save(card, str(folder / "carte_dilemme.png"))
    card.fill(BG)
    app.shock = {
        "id": SHOCKS[0]["id"],
        "year": 2031,
        "title": SHOCKS[0]["title"],
        "lines": SHOCKS[0]["lines"],
        "effect": SHOCKS[0]["effect"],
    }
    draw_shock(card, pixel, app, Hits())
    pygame.image.save(card, str(folder / "carte_evenement.png"))
    paths.append(folder / "carte_dilemme.png")
    paths.append(folder / "carte_evenement.png")
    pygame.quit()
    return paths


def main():
    parser = argparse.ArgumentParser(description="Revoir les animations des cartes.")
    parser.add_argument("--sheet", metavar="DOSSIER", help="ecrit des planches et quitte")
    args = parser.parse_args()
    if args.sheet:
        for path in save_sheets(args.sheet):
            print(path)
        return
    loop()


if __name__ == "__main__":
    main()
