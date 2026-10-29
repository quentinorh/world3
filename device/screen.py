"""Fenetre 720x720, et la dalle Waveshare quand elle est la."""

from __future__ import annotations

import os

import pygame

from device.panel import Panel

# Meme carre que world3.theme. La dalle fait 720x720.
W = 720
H = 720


def logical_pos(window, surf, pos):
    lw, lh = surf.get_size()
    win_w, win_h = window.get_size()
    scale = min(win_w / lw, win_h / lh)
    sw, sh = lw * scale, lh * scale
    ox = (win_w - sw) / 2
    oy = (win_h - sh) / 2
    return (pos[0] - ox) / scale, (pos[1] - oy) / scale


def present_frame(window, surf, panel):
    if panel is not None:
        panel.blit(surf)
        return
    win_w, win_h = window.get_size()
    # Dalle Waveshare 720x720 : une copie suffit. Le scale et le fond
    # noir sont deux passages de plus, visibles sur un Pi 3.
    width, height = surf.get_size()
    if win_w == width and win_h == height:
        window.blit(surf, (0, 0))
        pygame.display.flip()
        return
    scale = min(win_w / width, win_h / height)
    sw, sh = max(1, int(width * scale)), max(1, int(height * scale))
    frame = pygame.transform.scale(surf, (sw, sh))
    window.fill((0, 0, 0))
    window.blit(frame, ((win_w - sw) // 2, (win_h - sh) // 2))
    pygame.display.flip()


class Screen:
    def __init__(self, window, surf, panel):
        self.window = window
        self.surf = surf
        self.panel = panel

    def present(self):
        present_frame(self.window, self.surf, self.panel)

    def logical(self, pos):
        return logical_pos(self.window, self.surf, pos)

    def poll(self):
        if self.panel is not None:
            self.panel.poll()

    def close(self):
        panel = self.panel
        self.panel = None
        if panel is not None:
            panel.close()
        pygame.quit()


def open_screen(fullscreen=False, scale=1, caption=""):
    """Ouvre l'ecran. Une seule fois : le menu le garde pour les apps."""
    use_panel = bool(fullscreen) and Panel.available()
    if use_panel:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
    pygame.init()
    pygame.display.set_caption(caption or "WORLD3")
    panel = None
    try:
        if use_panel:
            window = pygame.display.set_mode((W, H))
            pygame.mouse.set_visible(False)
            panel = Panel.open(W, H)
        elif fullscreen:
            window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            pygame.mouse.set_visible(False)
        else:
            factor = max(1, int(scale))
            window = pygame.display.set_mode((W * factor, H * factor))
        surf = pygame.Surface((W, H)).convert()
    except Exception:
        if panel is not None:
            panel.close()
        pygame.quit()
        raise
    return Screen(window, surf, panel)
