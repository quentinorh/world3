"""Le parseur SP2050 et le cache, sans reseau."""

import json
import tempfile
from pathlib import Path

from sp2050.library import load_stories, save_library
from sp2050.sync import (
    cover_download_url,
    parse_article,
    parse_index,
    stories_from_kiosk,
    sync,
)

INDEX = """
<html><body>
<a href="/futurs">liste</a>
<a class="index-card" href="/futurs/12">Un</a>
<a href="/futurs/12/export/pdf">pdf</a>
<a href="/futurs/9">Deux</a>
<a href="/futurs/12">encore</a>
<a rel="next" href="/futurs?page=2">suite</a>
</body></html>
"""

ARTICLE = """
<html><head>
<meta property="og:title" content="SP2050 - Brume">
<meta property="og:title" content="Brume">
<meta property="og:image" content="https://res.cloudinary.com/dkv3sh4oq/image/upload/c_fill,h_1400,q_auto,w_1000/v1/utopia2050/abc.jpg?_a=1">
<meta property="article:author" content="Kamille">
<meta property="article:published_time" content="2026-01-03T08:00:00Z">
</head><body>
<div class="show-metadata__group">
  <span>Publié le</span>
  <span class="tabular-nums">03.01.2026</span>
</div>
<div class="show-metadata__group">
  <span>Temps de lecture</span>
  <span class="lg:hidden">Lecture</span>
  <span class="tabular-nums">2 min</span>
</div>
<div class="body-content mt-[24px]">Le port s'endort.

Au matin, la brume reste.</div>
<p class="show-license-notice__text">licence</p>
</body></html>
"""


def test_index():
    ids, nxt = parse_index(INDEX, "https://sp2050.org/futurs")
    assert ids == [12, 9], ids
    assert nxt == "https://sp2050.org/futurs?page=2", nxt


def test_article():
    story = parse_article(ARTICLE)
    assert story["title"] == "Brume", story
    assert story["author"] == "Kamille"
    assert story["published_at"] == "2026-01-03T08:00:00Z"
    assert story["reading_time"] == "2 min", story["reading_time"]
    assert story["body"] == "Le port s'endort.\n\nAu matin, la brume reste.", story["body"]
    assert story["cover_url"].endswith("abc.jpg?_a=1")


def test_cover_url():
    url = cover_download_url(
        "https://res.cloudinary.com/dkv3sh4oq/image/upload/c_fill,h_1400,q_auto,w_1000/v1/utopia2050/abc.jpg?_a=1"
    )
    assert url == (
        "https://res.cloudinary.com/dkv3sh4oq/image/upload/"
        "c_fill,w_480,h_672,q_auto,f_jpg/v1/utopia2050/abc.jpg?_a=1"
    ), url
    assert cover_download_url("https://example.com/a.jpg") == "https://example.com/a.jpg"


def test_kiosk_json():
    rows = stories_from_kiosk(
        {
            "futurs": [
                {
                    "id": "4",
                    "title": "Vallee",
                    "author": "Maï",
                    "published_at": "2024-05-01",
                    "reading_time": "1 min",
                    "body": "Une ligne.\n\n\n\nDeux.",
                    "cover_url": "https://example.com/c.jpg",
                    "updated_at": "2024-05-02",
                }
            ]
        }
    )
    assert rows[0]["id"] == 4
    assert rows[0]["body"] == "Une ligne.\n\nDeux."
    assert rows[0]["stamp"]


def test_cache_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        cache = Path(tmp)
        jpeg = b"\xff\xd8\xff\xd9"
        first = [
            {"id": 1, "title": "A", "author": "A", "body": "aa", "cover_url": "u", "cover_bytes": jpeg},
            {"id": 2, "title": "B", "author": "B", "body": "bb", "cover_url": "v", "cover_bytes": jpeg},
        ]
        assert save_library(cache, first) == 2
        assert (cache / "covers" / "1.jpg").is_file()
        assert (cache / "covers" / "2.jpg").is_file()
        save_library(cache, first[:1])
        assert not (cache / "covers" / "2.jpg").exists()
        stories = load_stories(cache)
        assert [story.id for story in stories] == [1]
        assert stories[0].title == "A"
        assert stories[0].cover is not None
        assert stories[0].when == ""


def test_sync_keeps_cache_offline():
    with tempfile.TemporaryDirectory() as tmp:
        cache = Path(tmp)
        save_library(
            cache,
            [{"id": 3, "title": "Deja", "author": "N", "body": "la", "cover_bytes": b"\xff\xd8"}],
        )

        def offline(url, accept):
            raise OSError("coupe")

        assert sync(cache, offline) is False
        assert [story.id for story in load_stories(cache)] == [3]

        def empty(url, accept):
            if url.endswith("futurs.json"):
                return 200, b'{"futurs": []}'
            return 200, b"<html></html>"

        assert sync(cache, empty) is False
        assert [story.id for story in load_stories(cache)] == [3]


def test_sync_prefers_json():
    with tempfile.TemporaryDirectory() as tmp:
        cache = Path(tmp)
        seen = []
        payload = {
            "futurs": [
                {
                    "id": 8,
                    "title": "Musee",
                    "author": "Jules",
                    "published_at": "2025-02-27T09:53:05Z",
                    "reading_time": "3 min 27",
                    "body": "Un musee.",
                    "cover_url": "https://example.com/cover.jpg",
                    "updated_at": "2025-02-27T09:53:05Z",
                }
            ]
        }

        def opener(url, accept):
            seen.append(url)
            if url.endswith("futurs.json"):
                return 200, json.dumps(payload).encode()
            if url.endswith("cover.jpg"):
                return 200, b"\xff\xd8\xff\xd9"
            raise AssertionError(url)

        assert sync(cache, opener) is True
        assert seen[0].endswith("futurs.json")
        assert not any("/futurs/8" in url for url in seen)
        stories = load_stories(cache)
        assert stories[0].title == "Musee"
        assert stories[0].when == "27.02.2025"
        assert stories[0].reading_time == "3 min 27"
        assert (cache / "covers" / "8.jpg").read_bytes().startswith(b"\xff\xd8")


def test_pixel_cover():
    import pygame

    from sp2050.app import pixel_cover, pixel_size

    assert pixel_size(720, 480, 672) == (720, 1008)
    width, height = pixel_size(720, 48, 67)
    assert width == 720
    assert height % 3 == 0
    pygame.init()
    try:
        pygame.display.set_mode((8, 8))
        src = pygame.Surface((48, 67))
        src.fill((20, 40, 60))
        pygame.draw.rect(src, (220, 30, 30), (0, 0, 24, 67))
        out = pixel_cover(src, 720)
        assert out.get_size() == (width, height)
        corner = out.get_at((0, 0))
        assert out.get_at((2, 2)) == corner
        assert out.get_at((0, 0)) != out.get_at((700, 20))
    finally:
        pygame.quit()


def main():
    test_index()
    test_article()
    test_cover_url()
    test_kiosk_json()
    test_cache_roundtrip()
    test_sync_keeps_cache_offline()
    test_sync_prefers_json()
    test_pixel_cover()
    print("sp2050 ok")


if __name__ == "__main__":
    main()
