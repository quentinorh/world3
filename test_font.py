"""Police bitmap : capitales du jeu, minuscules, bouton partage."""

import pygame

from device.widgets import CORNER_PAD, HOME_LIGHT, corner_hit, draw_button, draw_home, home_rect
from world3.font import GLYPHS, Font
from world3.theme import BG, INK, LINE


def test_capitales():
    font = Font()
    assert font._normalize("ab é") == font._normalize("AB É")
    assert font._normalize("(«") == font._normalize("  ")
    assert GLYPHS["A"][0] == (False, True, True, True, False)
    assert GLYPHS["A"][3] == (True, True, True, True, True)
    for rows in GLYPHS.values():
        for row in rows:
            assert len(row) == 5


def test_minuscules():
    font = Font()
    assert font._normalize("été", case="keep") != font._normalize("été")
    assert GLYPHS["a"] != GLYPHS["A"]
    assert GLYPHS["é"] != GLYPHS["e"]
    assert len(GLYPHS["g"]) == 9
    assert font._normalize("(«bonjour»)", case="keep") == font._normalize('("bonjour")', case="keep")
    assert font.width("cœur", 2, case="keep") == font.width("coeur", 2, case="keep")
    assert font.width("l’été", 2, case="keep") == font.width("l'été", 2, case="keep")
    lines = font.wrap("Le cœur dit : « bonjour » l'été, déjà.", 90, 2)
    assert len(lines) > 1
    assert all(font.width(line, 2, case="keep") <= 90 for line in lines)
    assert font.step(2) > font.height(2) + font.descent(2)


def test_dessin():
    pygame.init()
    try:
        pygame.display.set_mode((80, 80))
        font = Font()
        upper = pygame.Surface((80, 40))
        lower = pygame.Surface((80, 40))
        same = pygame.Surface((80, 40))
        upper.fill((0, 0, 0))
        lower.fill((0, 0, 0))
        same.fill((0, 0, 0))
        font.blit(upper, "A", 4, 8, 3, (255, 255, 255))
        font.blit(same, "a", 4, 8, 3, (255, 255, 255))
        font.blit(lower, "a", 4, 8, 3, (255, 255, 255), case="keep")
        assert pygame.image.tostring(upper, "RGB") == pygame.image.tostring(same, "RGB")
        assert pygame.image.tostring(upper, "RGB") != pygame.image.tostring(lower, "RGB")

        plate = pygame.Surface((80, 80))
        plate.fill((200, 0, 0))
        draw_button(plate, font, pygame.Rect(10, 10, 56, 56), "+", False, 3)
        assert plate.get_at((67, 67))[:3] == LINE
        assert plate.get_at((30, 30))[:3] == BG
        assert plate.get_at((10, 10))[:3] == INK

        dark = pygame.Surface((80, 80))
        light = pygame.Surface((80, 80))
        dark.fill((0, 80, 0))
        light.fill((0, 80, 0))
        draw_home(dark, pygame.Rect(10, 10, 48, 48), ground="dark")
        draw_home(light, pygame.Rect(10, 10, 48, 48), ground="light")
        assert dark.get_at((16, 16))[:3] == BG
        assert dark.get_at((10, 10))[:3] == INK
        assert light.get_at((16, 16))[:3] == HOME_LIGHT
        assert light.get_at((10, 10))[:3] == BG
        assert dark.get_at((33, 22))[:3] != light.get_at((33, 22))[:3]

        pressed = pygame.Surface((80, 80))
        pressed.fill((200, 0, 0))
        draw_button(pressed, font, pygame.Rect(10, 10, 56, 56), "+", True, 3)
        assert pressed.get_at((10, 10))[:3] == (200, 0, 0)
        assert pressed.get_at((13, 13))[:3] == INK
    finally:
        pygame.quit()


def test_zone_coin():
    visual = home_rect()
    zone = corner_hit(visual)
    assert zone.size == (visual.w + 2 * CORNER_PAD, visual.h + 2 * CORNER_PAD)
    assert zone.center == visual.center
    assert zone.collidepoint(visual.x - (CORNER_PAD - 1), visual.centery)
    assert not zone.collidepoint(visual.x - (CORNER_PAD + 1), visual.centery)


def main():
    test_capitales()
    test_minuscules()
    test_dessin()
    test_zone_coin()
    print("font ok")


if __name__ == "__main__":
    main()
