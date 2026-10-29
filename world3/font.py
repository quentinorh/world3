"""Police 5x7, sans antialiasing. Dessinee, pas chargee.

Le jeu l'emploie en capitales. Les autres ecrans peuvent garder la casse :
les minuscules tiennent dans le meme corps, les descendantes sous la
ligne. Les accents du jeu restent deux rangees au-dessus du corps, la
cedille deux rangees en dessous.
"""

import unicodedata

import pygame

# Chaque glyphe : 7 rangees de 5 bits. 1 = encre.
_RAW = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01111", "10000", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "J": ("00111", "00010", "00010", "00010", "10010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "10101", "01010"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ",": ("00000", "00000", "00000", "00000", "00100", "00100", "01000"),
    ":": ("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    "=": ("00000", "00000", "11111", "00000", "11111", "00000", "00000"),
    "+": ("00000", "00100", "00100", "11111", "00100", "00100", "00000"),
    "%": ("11001", "11010", "00010", "00100", "01000", "01011", "10011"),
    "/": ("00001", "00001", "00010", "00100", "01000", "10000", "10000"),
    "?": ("01110", "10001", "00001", "00010", "00100", "00000", "00100"),
    "!": ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    ">": ("10000", "01000", "00100", "00010", "00100", "01000", "10000"),
    "<": ("00001", "00010", "00100", "01000", "00100", "00010", "00001"),
    "'": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    "(": ("00110", "01000", "10000", "10000", "10000", "01000", "00110"),
    ")": ("01100", "00010", "00001", "00001", "00001", "00010", "01100"),
    ";": ("00000", "01100", "01100", "00000", "00110", "00100", "01000"),
    '"': ("01010", "01010", "01010", "00000", "00000", "00000", "00000"),
    "&": ("01100", "10010", "10100", "01000", "10101", "10010", "01101"),
    "©": ("01110", "10001", "11101", "11001", "11101", "10001", "01110"),
    "«": ("01000", "00100", "00010", "00100", "01000", "00000", "00000"),
    "»": ("00010", "00100", "01000", "00100", "00010", "00000", "00000"),
}

# Deux rangees. L'aigu monte vers la droite, le grave vers la gauche.
_ABOVE = {
    "acute": ("00100", "01000"),
    "grave": ("00100", "00010"),
    "circ": ("00100", "01010"),
    "diaer": ("01010", "00000"),
}

_BELOW = {
    "cedilla": ("00100", "01000"),
}

# base, accent au-dessus, signe en dessous.
_ACCENTS = {
    "É": ("E", "acute", None),
    "È": ("E", "grave", None),
    "Ê": ("E", "circ", None),
    "Ë": ("E", "diaer", None),
    "À": ("A", "grave", None),
    "Â": ("A", "circ", None),
    "Ä": ("A", "diaer", None),
    "Ç": ("C", None, "cedilla"),
    "Î": ("I", "circ", None),
    "Ï": ("I", "diaer", None),
    "Ô": ("O", "circ", None),
    "Ö": ("O", "diaer", None),
    "Ù": ("U", "grave", None),
    "Û": ("U", "circ", None),
    "Ü": ("U", "diaer", None),
}

_ASCENT = 2
_DESCENT = 2


def _bits(rows):
    glyph = []
    for row in rows:
        glyph.append(tuple(ch == "1" for ch in row))
    return tuple(glyph)


def _compose(base, above, below):
    rows = []
    ascent = 0
    if above:
        rows.extend(_ABOVE[above])
        ascent = len(_ABOVE[above])
    rows.extend(_RAW[base])
    if below:
        rows.extend(_BELOW[below])
    return _bits(rows), ascent


# Minuscules. Le haut du corps (deux rangees) reste vide pour l'accent,
# sauf les hampes. Les descendantes ajoutent deux rangees sous la ligne.
_LOWER = {
    "a": ("00000", "00000", "01110", "00001", "01111", "10001", "01111"),
    "b": ("10000", "10000", "11110", "10001", "10001", "10001", "11110"),
    "c": ("00000", "00000", "01111", "10000", "10000", "10000", "01111"),
    "d": ("00001", "00001", "01111", "10001", "10001", "10001", "01111"),
    "e": ("00000", "00000", "01110", "10001", "11110", "10000", "01110"),
    "f": ("00111", "01000", "01000", "11100", "01000", "01000", "01000"),
    "g": ("00000", "00000", "01111", "10001", "10001", "10001", "01111", "00001", "01111"),
    "h": ("10000", "10000", "11110", "10001", "10001", "10001", "10001"),
    "i": ("00100", "00000", "00100", "00100", "00100", "00100", "00100"),
    "j": ("00010", "00000", "00010", "00010", "00010", "00010", "00010", "10010", "01100"),
    "k": ("10000", "10000", "10010", "10100", "11000", "10100", "10010"),
    "l": ("00100", "00100", "00100", "00100", "00100", "00100", "00110"),
    "m": ("00000", "00000", "11011", "10101", "10101", "10101", "10001"),
    "n": ("00000", "00000", "11110", "10001", "10001", "10001", "10001"),
    "o": ("00000", "00000", "01110", "10001", "10001", "10001", "01110"),
    "p": ("00000", "00000", "11110", "10001", "10001", "10001", "11110", "10000", "10000"),
    "q": ("00000", "00000", "01111", "10001", "10001", "10001", "01111", "00001", "00001"),
    "r": ("00000", "00000", "11110", "10001", "10000", "10000", "10000"),
    "s": ("00000", "00000", "01111", "10000", "01110", "00001", "11110"),
    "t": ("00100", "00100", "01110", "00100", "00100", "00100", "00011"),
    "u": ("00000", "00000", "10001", "10001", "10001", "10001", "01111"),
    "v": ("00000", "00000", "10001", "10001", "10001", "01010", "00100"),
    "w": ("00000", "00000", "10001", "10101", "10101", "10101", "01010"),
    "x": ("00000", "00000", "10001", "01010", "00100", "01010", "10001"),
    "y": ("00000", "00000", "10001", "10001", "01010", "00100", "00100", "00100", "01100"),
    "z": ("00000", "00000", "11111", "00010", "00100", "01000", "11111"),
}

_LOWER_ACCENT = (
    ("à", "a", "grave", None),
    ("â", "a", "circ", None),
    ("ä", "a", "diaer", None),
    ("ç", "c", None, "cedilla"),
    ("é", "e", "acute", None),
    ("è", "e", "grave", None),
    ("ê", "e", "circ", None),
    ("ë", "e", "diaer", None),
    ("î", "i", "circ", None),
    ("ï", "i", "diaer", None),
    ("ô", "o", "circ", None),
    ("ö", "o", "diaer", None),
    ("ù", "u", "grave", None),
    ("û", "u", "circ", None),
    ("ü", "u", "diaer", None),
    ("ÿ", "y", "diaer", None),
)

# Apostrophes et tirets des textes colles depuis le web.
_FOLD = {
    "œ": "oe",
    "Œ": "OE",
    "æ": "ae",
    "Æ": "AE",
    "ß": "ss",
    "’": "'",
    "‘": "'",
    "´": "'",
    "`": "'",
    "“": '"',
    "”": '"',
    "„": '"',
    "–": "-",
    "—": "-",
    "…": "...",
    "«": '"',
    "»": '"',
    "\u00a0": " ",
    "\u202f": " ",
    "\u2009": " ",
}


def _accent_lower(base, above, below):
    rows = list(_LOWER[base])
    if above:
        mark = _ABOVE[above]
        rows[0] = mark[0]
        rows[1] = mark[1]
    if below:
        rows.extend(_BELOW[below])
    return _bits(rows)


GLYPHS = {ch: _bits(rows) for ch, rows in _RAW.items()}
ASCENT = {ch: 0 for ch in _RAW}
for _ch, (_base, _above, _below) in _ACCENTS.items():
    GLYPHS[_ch], ASCENT[_ch] = _compose(_base, _above, _below)
for _ch, _rows in _LOWER.items():
    GLYPHS[_ch] = _bits(_rows)
    ASCENT[_ch] = 0
for _ch, _base, _above, _below in _LOWER_ACCENT:
    GLYPHS[_ch] = _accent_lower(_base, _above, _below)
    ASCENT[_ch] = 0


# Le magenta n'est pas dans la palette. Une surface a cle est bien
# plus rapide qu'un canal alpha, et ces glyphes sont pleins ou vides.
_KEY = (255, 0, 255)

# Ces signes existent pour les lectures. Le jeu les laissait vides :
# les y montrer changerait ses textes.
_GAME_BLANK = set("()«»")


class Font:
    def __init__(self):
        self._cache = {}
        self._lines = {}

    def _resolve(self, ch, keep=False):
        if not keep and ch in _GAME_BLANK:
            return " "
        if ch in GLYPHS:
            return ch
        base = unicodedata.normalize("NFD", ch)[:1]
        if base in GLYPHS and (keep or base not in _GAME_BLANK):
            return base
        return " "

    def _normalize(self, text, case="upper"):
        raw = str(text)
        keep = case == "keep"
        if not keep:
            raw = raw.upper()
        else:
            raw = "".join(_FOLD.get(ch, ch) for ch in raw)
        return "".join(self._resolve(ch, keep) for ch in raw)

    def width(self, text, scale, case="upper"):
        text = self._normalize(text, case)
        if not text:
            return 0
        return len(text) * 6 * scale - scale

    def height(self, scale):
        return 7 * scale

    def ascent(self, scale):
        return _ASCENT * scale

    def descent(self, scale):
        return _DESCENT * scale

    def _glyph(self, ch, scale, color):
        key = (ch, scale, color)
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        rows = GLYPHS[ch]
        surf = pygame.Surface((5 * scale, len(rows) * scale))
        surf.fill(_KEY)
        surf.set_colorkey(_KEY)
        for y, row in enumerate(rows):
            for x, on in enumerate(row):
                if on:
                    pygame.draw.rect(surf, color, (x * scale, y * scale, scale, scale))
        self._cache[key] = surf
        return surf

    def _line(self, text, scale, color):
        key = (text, scale, color)
        hit = self._lines.get(key)
        if hit is not None:
            return hit
        if len(self._lines) > 800:
            self._lines.clear()
        above = max(ASCENT[ch] for ch in text) * scale
        height = 1
        for ch in text:
            top = above - ASCENT[ch] * scale
            height = max(height, top + len(GLYPHS[ch]) * scale)
        width = len(text) * 6 * scale - scale
        image = pygame.Surface((width, height))
        image.fill(_KEY)
        image.set_colorkey(_KEY)
        cursor = 0
        for ch in text:
            image.blit(
                self._glyph(ch, scale, color),
                (cursor, above - ASCENT[ch] * scale),
            )
            cursor += 6 * scale
        # Format de l'ecran : les copies suivantes ne reconvertissent plus.
        if pygame.display.get_surface() is not None:
            image = image.convert()
        self._lines[key] = (image, above)
        return image, above

    def blit(self, dest, text, x, y, scale, color, align="left", case="upper"):
        text = self._normalize(text, case)
        if not text:
            return 0
        width = len(text) * 6 * scale - scale
        if align == "center":
            x -= width // 2
        elif align == "right":
            x -= width
        image, above = self._line(text, scale, color)
        dest.blit(image, (int(x), int(y) - above))
        return width

    def blit_center(self, dest, text, rect, scale, color, case="upper"):
        width = self.width(text, scale, case=case)
        height = self.height(scale)
        x = rect.x + (rect.w - width) // 2
        y = rect.y + (rect.h - height) // 2
        self.blit(dest, text, x, y, scale, color, case=case)

    def step(self, scale):
        """Pas de ligne : corps, accents, descendantes, et un cran d'air."""
        return (7 + _ASCENT + _DESCENT + 1) * scale

    def wrap(self, text, width, scale, case="keep"):
        words = str(text).split()
        if not words or width <= 0:
            return []
        lines = []
        current = ""
        for word in words:
            trial = word if not current else f"{current} {word}"
            if self.width(trial, scale, case=case) <= width:
                current = trial
                continue
            if current:
                lines.append(current)
                current = ""
            if self.width(word, scale, case=case) <= width:
                current = word
                continue
            buf = ""
            for ch in word:
                trial = buf + ch
                if buf and self.width(trial, scale, case=case) > width:
                    lines.append(buf)
                    buf = ch
                else:
                    buf = trial
            current = buf
        if current:
            lines.append(current)
        return lines
