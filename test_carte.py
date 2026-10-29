"""Tuiles, filtre des routes, dessin terre et mer. Sans reseau."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import tempfile
from datetime import date
from pathlib import Path

from carte.fetch import asset_token, choose_asset, recent_build_urls
from carte.mvt import decode_tile
from carte.pmtiles import (
    NONE,
    Archive,
    find_entry,
    parse_directory,
    serialize_directory,
    tileid_to_zxy,
    write_archive,
    zxy_to_tileid,
)
from carte.style import (
    LAND,
    PAPER,
    SEA,
    WATER,
    label_allowed,
    place_name,
    road_kept,
    road_paint,
)
from carte.view import (
    HOME_LAT,
    HOME_LON,
    TILE,
    approach_zoom,
    data_zoom,
    lonlat_to_px,
    paint_zoom,
    pan,
    parent_tile,
    px_to_lonlat,
    screen_box,
    tile_pixels,
    tile_screen_rects,
    tiles_in_view,
)


def _uvarint(number):
    out = bytearray()
    while number >= 0x80:
        out.append((number & 0x7F) | 0x80)
        number >>= 7
    out.append(number)
    return bytes(out)


def _key(field, wire):
    return _uvarint((field << 3) | wire)


def _blob(field, data):
    return _key(field, 2) + _uvarint(len(data)) + data


def _var(field, number):
    return _key(field, 0) + _uvarint(number)


def _packed(field, numbers):
    return _blob(field, b"".join(_uvarint(number) for number in numbers))


def _zigzag(number):
    if number >= 0:
        return number << 1
    return ((-number) << 1) - 1


def _move_line(points):
    words = [9, _zigzag(points[0][0]), _zigzag(points[0][1])]
    words.append((len(points) - 1) << 3 | 2)
    x, y = points[0]
    for px, py in points[1:]:
        words.extend((_zigzag(px - x), _zigzag(py - y)))
        x, y = px, py
    return words


def _ring(points):
    # ClosePath vaut 7, pas 3. Un seul anneau se dessinait quand meme :
    # le suivant etait abandonne.
    return _move_line(points) + [(1 << 3) | 7]


def _layer(name, features, keys, values):
    body = _blob(1, name.encode())
    for feature in features:
        body += _blob(2, feature)
    for key in keys:
        body += _blob(3, key.encode())
    for value in values:
        body += _blob(4, value)
    body += _var(5, 4096) + _var(15, 2)
    return _blob(3, body)


def _string(text):
    return _blob(1, text.encode())


def _sample_tile():
    earth = _var(3, 3) + _packed(4, _ring([(1024, 0), (4096, 0), (4096, 4096), (1024, 4096)]))
    lake = _var(3, 3) + _packed(4, _ring([(2000, 2000), (2800, 2000), (2800, 2800), (2000, 2800)]))
    service = (
        _var(3, 2)
        + _packed(2, [0, 0])
        + _packed(4, _move_line([(0, 3500), (4096, 3500)]))
    )
    city = (
        _var(3, 1)
        + _packed(2, [0, 0, 1, 1, 2, 2, 3, 3, 4, 4])
        + _packed(4, [9, _zigzag(2048), _zigzag(2048)])
    )
    building = _var(3, 3) + _packed(4, _ring([(0, 0), (10, 0), (10, 10), (0, 10)]))
    return (
        _layer("earth", [earth], [], [])
        + _layer("water", [lake], [], [])
        + _layer("roads", [service], ["kind_detail"], [_string("service")])
        + _layer(
            "places",
            [city],
            ["kind", "kind_detail", "name:fr", "name", "min_zoom"],
            [_string("locality"), _string("city"), _string("Paris"), _string("Москва"), _var_value(4)],
        )
        + _layer("buildings", [building], [], [])
    )


def _var_value(number):
    # Valeur protobuf int, champ 4.
    return _var(4, number)


def test_hilbert():
    assert zxy_to_tileid(0, 0, 0) == 0
    assert zxy_to_tileid(1, 0, 0) == 1
    assert zxy_to_tileid(1, 0, 1) == 2
    assert zxy_to_tileid(1, 1, 1) == 3
    assert zxy_to_tileid(1, 1, 0) == 4
    assert zxy_to_tileid(2, 0, 0) == 5
    for z in range(5):
        side = 1 << z
        for x in range(side):
            for y in range(side):
                assert tileid_to_zxy(zxy_to_tileid(z, x, y)) == (z, x, y)
    assert tileid_to_zxy(zxy_to_tileid(12, 2048, 1400)) == (12, 2048, 1400)


def test_repertoire():
    entries = [(1, 0, 10, 1), (2, 10, 5, 1), (8, 15, 7, 2)]
    assert parse_directory(serialize_directory(entries, NONE), NONE) == entries
    assert find_entry([(5, 0, 4, 3)], 7)[0] == 5
    assert find_entry([(5, 0, 4, 3)], 8) is None
    assert find_entry([(5, 0, 4, 3)], 4) is None


def test_archive_feuille():
    payload = _sample_tile()
    other = b"autre"
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "terre.pmtiles"
        write_archive(path, [(0, 0, 0, payload), (1, 0, 1, other)], leaf_size=1)
        archive = Archive(path)
        try:
            assert archive.tile(0, 0, 0) == payload
            assert archive.tile(1, 0, 1) == other
            assert archive.tile(1, 1, 1) is None
        finally:
            archive.close()
        root = Path(tmp) / "racine.pmtiles"
        write_archive(root, [(2, 1, 1, payload)])
        archive = Archive(root)
        try:
            assert archive.tile(2, 1, 1) == payload
        finally:
            archive.close()


def test_deux_anneaux():
    # Le second anneau est relatif au curseur laisse par le premier.
    words = []
    cursor = (0, 0)
    for points in (
        [(0, 0), (100, 0), (100, 100), (0, 100)],
        [(20, 20), (40, 20), (40, 40), (20, 40)],
    ):
        dx = points[0][0] - cursor[0]
        dy = points[0][1] - cursor[1]
        words.extend((9, _zigzag(dx), _zigzag(dy)))
        cursor = points[0]
        words.append(((len(points) - 1) << 3) | 2)
        for px, py in points[1:]:
            words.extend((_zigzag(px - cursor[0]), _zigzag(py - cursor[1])))
            cursor = (px, py)
        words.append((1 << 3) | 7)
    tile = _layer("earth", [_var(3, 3) + _packed(4, words)], [], [])
    rings = decode_tile(tile)[0].features[0].rings
    assert len(rings) == 2
    assert rings[0][0] == (0, 0)
    assert rings[1][0] == (20, 20)


def test_tuile_mvt():
    layers = {layer.name: layer for layer in decode_tile(_sample_tile())}
    assert "buildings" not in layers
    earth = layers["earth"].features[0].rings[0]
    assert (1024, 0) in earth
    assert (4096, 4096) in earth
    lake = layers["water"].features[0].rings[0]
    assert lake[0] == (2000, 2000)
    road = layers["roads"].features[0]
    assert road.props["kind_detail"] == "service"
    assert road.lines[0] == [(0, 3500), (4096, 3500)]
    place = layers["places"].features[0]
    assert place.points == [(2048, 2048)]
    assert place_name(place.props) == "Paris"


def test_noms_et_routes():
    assert place_name({"name:fr": "Lyon", "name": "Москва"}) == "Lyon"
    assert place_name({"name:en": "Moscow", "name": "Москва"}) == "Moscow"
    assert place_name({"name": "Москва"}) == ""
    assert place_name({"name": "Île-de-France"}) == "Île-de-France"
    assert road_kept("highway", "service", 12) is False
    assert road_kept("highway", "path", 12) is False
    assert road_kept("highway", "track", 12) is False
    assert road_kept("highway", "steps", 13) is False
    assert road_kept("path", "footway", 12) is False
    assert road_kept("highway", "residential", 11) is False
    assert road_kept("highway", "residential", 12) is True
    assert road_kept("highway", "motorway", 3) is True
    assert road_paint("highway", "motorway", 3)[1] == 1
    assert road_paint("highway", "motorway", 10)[1] == 2
    assert road_paint("highway", "motorway", 12)[1] == 3
    assert road_paint("highway", "primary", 6)[1] == 1
    assert road_paint("highway", "secondary", 11)[1] == 1
    assert road_kept("highway", "motorway_link", 5) is True
    assert label_allowed("locality", "city", 4, 6) is True
    assert label_allowed("country", "country", 0, 8) is False
    assert label_allowed("neighbourhood", "neighbourhood", 12, 13) is False


def test_zoom_fluide():
    assert abs(approach_zoom(2, 3) - 2.35) < 1e-9
    assert abs(approach_zoom(3, 2) - 2.65) < 1e-9
    assert approach_zoom(2.999, 3) == 3
    span, tiles = tiles_in_view(10.0, 20.0, 2, 720, 720)
    z, x, y, sx, sy = tiles[0]
    rects = tile_screen_rects(10.0, 20.0, 2, z, x, y, 720, 720)
    assert any(
        abs(left - sx) < 1e-6 and abs(top - sy) < 1e-6 and abs(cote - span) < 1e-6
        for left, top, cote in rects
    )
    here = screen_box(10.2, 4.0, 100.2)
    nxt = screen_box(110.4, 4.0, 100.2)
    assert here[0] + here[2] == nxt[0]

    import pygame

    from carte.app import MapApp

    pygame.init()
    try:
        pygame.display.set_mode((720, 720))
        span, tiles = tiles_in_view(HOME_LON, HOME_LAT, 3, 720, 720)
        hit = None
        for tz, tx, ty, left, top in tiles:
            if left <= 360 < left + span and top <= 360 < top + span:
                hit = (tz, tx, ty)
        assert hit is not None
        parent = (hit[0] - 1, hit[1] // 2, hit[2] // 2)
        green = pygame.Surface((256, 256))
        green.fill((20, 180, 40))
        with tempfile.TemporaryDirectory() as tmp:
            screen = _Screen()
            app = MapApp(screen, Path(tmp) / "absent.pmtiles")
            app.archive = object()
            app.zoom = 3
            app.zoom_target = 3
            app.drag = True
            app.cache[parent] = (green, [])
            app._paint()
            assert screen.surf.get_at((360, 360))[:3] == (20, 180, 40)
            app._set_zoom(4)
            assert parent in app.cache
            assert app.zoom == 3
            assert app.zoom_target == 4
    finally:
        pygame.quit()


def test_vue():
    assert data_zoom(13) == 12
    assert data_zoom(15) == 12
    assert data_zoom(2.9) == 2
    assert paint_zoom(0) == 0
    assert paint_zoom(1) == 0
    assert paint_zoom(2) == 0
    assert paint_zoom(3) == 1
    assert paint_zoom(12) == 10
    assert paint_zoom(13) == 11
    assert paint_zoom(14) == 12
    assert paint_zoom(15) == 12
    # Deux crans sous la vue : cote d'ecran au moins 4 x TILE.
    assert tile_pixels(12) == 1024
    assert tile_pixels(13) == 1024
    assert tile_pixels(14) == 1024
    assert tile_pixels(15) == 2048
    assert parent_tile(3, 5, 6) == (2, 2, 3)
    assert parent_tile(0, 0, 0) is None
    x, y = lonlat_to_px(10.0, 20.0, 2)
    lat, lon = px_to_lonlat(x, y, 2)
    assert abs(lat - 20.0) < 1e-6
    assert abs(lon - 10.0) < 1e-6
    span, tiles = tiles_in_view(0.0, 0.0, 2, 720, 720)
    assert abs(span - 1024) < 1e-6
    keys = {(z, tx, ty) for z, tx, ty, _sx, _sy in tiles}
    assert keys == {(0, 0, 0)}
    _size, padded = tiles_in_view(0.0, 0.0, 5, 720, 720, pad=1)
    bare = {(z, tx, ty) for z, tx, ty, _sx, _sy in tiles_in_view(0.0, 0.0, 5, 720, 720)[1]}
    wide = {(z, tx, ty) for z, tx, ty, _sx, _sy in padded}
    assert bare < wide
    _size, edge = tiles_in_view(179.0, 0.0, 2, 720, 720)
    xs = {tx for _z, tx, _ty, _sx, _sy in edge}
    assert xs == {0}
    _lat, lon = pan(0.0, 0.0, 2, 100, 0)
    assert lon < 0


def test_tuile_pixel():
    """Les tuiles restent a 256 px ; l'ecran les agrandit."""
    import pygame

    from carte.app import MapApp

    pygame.init()
    try:
        pygame.display.set_mode((720, 720))
        payload = _sample_tile()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "terre.pmtiles"
            write_archive(path, [(2, 1, 1, payload)])
            screen = _Screen()
            app = MapApp(screen, path)
            try:
                assert app.archive is not None
                image, _labels = app._load(2, 1, 1)
                assert image.get_width() == TILE
                assert image.get_height() == TILE
                app.lon = HOME_LON
                app.lat = HOME_LAT
                app.cache[(2, 1, 1)] = (image, [])
                # Zoom artificiel : la meme tuile reste a 256 px en cache.
                app.zoom = 15
                app.zoom_target = 15
                app._paint()
                assert (2, 1, 1) in app.cache
                assert app.cache[(2, 1, 1)][0].get_width() == TILE
            finally:
                if app.archive is not None:
                    app.archive.close()
                    app.archive = None
    finally:
        pygame.quit()


def test_preparation():
    urls = recent_build_urls(date(2026, 10, 27), 3)
    assert urls[0].endswith("/20261027.pmtiles")
    assert urls[1].endswith("/20261026.pmtiles")
    assert asset_token("Windows", "AMD64") == "Windows_x86_64"
    assert asset_token("Darwin", "arm64") == "Darwin_arm64"
    try:
        asset_token("Linux", "armv7l")
    except ValueError:
        pass
    else:
        raise AssertionError("le Pi 32 bits ne doit pas preparer la carte")
    asset = choose_asset(
        [
            {"name": "go-pmtiles_1.31.2_Windows_arm64.zip"},
            {"name": "go-pmtiles_1.31.2_Windows_x86_64.zip"},
        ],
        "Windows_x86_64",
    )
    assert asset["name"].endswith("Windows_x86_64.zip")


def test_dessin_et_ecran_vide():
    import pygame

    from carte.app import MapApp, paint_missing
    from carte.draw import render_tile

    pygame.init()
    try:
        pygame.display.set_mode((720, 720))
        _surf, labels = render_tile(_sample_tile(), 64, 6)
        assert _surf.get_at((4, 4))[:3] == SEA
        assert _surf.get_at((50, 20))[:3] == LAND
        assert _surf.get_at((36, 36))[:3] == WATER
        assert _surf.get_at((40, 54))[:3] == LAND
        assert any(label["text"] == "Paris" for label in labels)

        missing = pygame.Surface((720, 720))
        missing.fill((255, 0, 0))
        paint_missing(missing, False)
        assert missing.get_at((0, 0))[:3] == PAPER

        with tempfile.TemporaryDirectory() as tmp:
            screen = _Screen()
            app = MapApp(screen, Path(tmp) / "absent.pmtiles")
            assert app.archive is None
            app._paint()
            assert screen.surf.get_at((10, 10))[:3] == PAPER

        from kiosk.app import Menu

        screen = _Screen()
        menu = Menu(screen)
        menu._draw()
        assert screen.surf.get_at((360, 90))[:3] == (16, 14, 12)
        assert screen.surf.get_at((360, 450))[:3] == (214, 206, 188)
        assert screen.surf.get_at((360, 630))[:3] == (250, 250, 249)
    finally:
        pygame.quit()


class _Screen:
    def __init__(self):
        import pygame

        self.surf = pygame.Surface((720, 720))

    def poll(self):
        return None

    def present(self):
        return None

    def logical(self, pos):
        return pos


def main():
    test_hilbert()
    test_repertoire()
    test_archive_feuille()
    test_deux_anneaux()
    test_tuile_mvt()
    test_noms_et_routes()
    test_zoom_fluide()
    test_vue()
    test_tuile_pixel()
    test_preparation()
    test_dessin_et_ecran_vide()
    print("carte ok")


if __name__ == "__main__":
    main()
