"""Ciel, sol texturé, puis les plantes. L'image est peinte en 360 et agrandie.

Les gros pixels viennent de là : aplats, herbe, fleurs, troncs. L'interface,
elle, reste dessinée ensuite en 720.
"""

from __future__ import annotations

import math

import numpy as np
import pygame

from device.screen import H, W
from jardin.scene import horizon_color
from jardin.species import sun_vector

EYE = 1.58
VW, VH = 360, 360
HORIZON = 154
FOCAL = 255
NEAR = 0.45
_CX = VW / 2
_MAX_WOODY = 80
_MAX_HIGH = 200
_skies: dict[int, pygame.Surface] = {}
_frame: pygame.Surface | None = None


def _star_row(i: int):
    az = i * 2.399963 + 0.35
    el = 0.16 + (i % 6) * 0.1
    ce = math.cos(el)
    return (math.sin(az) * ce, math.sin(el), math.cos(az) * ce, 1 if i % 3 else 2)


_STARS = tuple(_star_row(i) for i in range(22))


class Camera:
    def __init__(self, z: float, yaw: float, eye: float = EYE):
        self.x = 0.0
        self.z = z
        self.yaw = yaw
        self.eye = eye


def render(surf: pygame.Surface, batch, cam: Camera, hour: int, beat: float):
    view = _view()
    view.blit(_sky(hour), (0, 0))
    _ground(view, cam, hour)
    _sun(view, cam, hour)
    _stars(view, cam, hour)
    pygame.draw.line(view, horizon_color(hour), (0, HORIZON), (VW - 1, HORIZON), 1)
    _plants(view, batch, cam, hour, beat)
    _spores(view, batch, cam)
    _grass(view, cam, hour, beat)
    surf.blit(pygame.transform.scale(view, (W, H)), (0, 0))


def project_direction(direction, yaw: float):
    """Direction monde → pixel de la vue. None si c'est derrière l'œil."""
    dx, dy, dz = direction
    c, s = math.cos(yaw), math.sin(yaw)
    x1 = dx * c - dz * s
    z1 = dx * s + dz * c
    if z1 < 0.12:
        return None
    return _CX + FOCAL * x1 / z1, HORIZON - FOCAL * dy / z1


def _view() -> pygame.Surface:
    global _frame
    if _frame is None:
        _frame = pygame.Surface((VW, VH))
    return _frame


def _sky(hour: int) -> pygame.Surface:
    hit = _skies.get(hour)
    if hit is None:
        hit = _make_sky(hour)
        _skies[hour] = hit
    return hit


def _mix(a, b, t):
    t = np.asarray(t, np.float32)
    a = np.asarray(a, np.float32)
    b = np.asarray(b, np.float32)
    if t.ndim == 1:
        t = t[:, None]
    return a * (1.0 - t) + b * t


def _tone(a, b, hour: int):
    t = max(0, min(4, hour)) / 4.0
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _make_sky(hour: int) -> pygame.Surface:
    t = max(0, min(4, hour)) / 4.0
    top = np.array([4, 2, 10], np.float32)
    mid = _mix(np.array([32, 14, 68], np.float32), np.array([58, 8, 46], np.float32), t)
    hot = np.array(horizon_color(hour), np.float32)
    deep = np.array([3, 4, 9], np.float32)
    y = np.linspace(0, 1, VH, dtype=np.float32)
    hy = HORIZON / VH
    col = np.zeros((VH, 3), np.float32)
    above = y <= hy
    u = np.zeros_like(y)
    u[above] = (y[above] / max(hy, 1e-3)) ** 1.45
    low = above & (u < 0.58)
    high = above & ~low
    col[low] = _mix(top, mid, u[low] / 0.58)
    col[high] = _mix(mid, hot, (u[high] - 0.58) / 0.42)
    below = ~above
    v = np.clip((y[below] - hy) / max(1.0 - hy, 1e-3), 0, 1)
    col[below] = _mix(hot, deep, v ** 0.5)
    yy = y[:, None]
    xx = np.linspace(-1, 1, VW, dtype=np.float32)[None, :]
    vig = 1.0 - np.clip(xx ** 2 * 0.18 + (yy - hy) ** 2 * 0.12, 0, 0.4)
    rgb = np.clip(col[:, None, :] * vig[..., None], 0, 255).astype(np.uint8)
    frame = np.ascontiguousarray(rgb.transpose(1, 0, 2))
    return pygame.surfarray.make_surface(frame)


def _carpet(hour: int):
    """Pré qui reste vert, un peu plus chaud au couchant."""
    return {
        "deep": _tone((18, 74, 32), (32, 64, 36), hour),
        "mid": _tone((30, 114, 42), (48, 102, 44), hour),
        "light": _tone((54, 150, 48), (78, 132, 42), hour),
        "sun": _tone((112, 176, 46), (164, 148, 40), hour),
        "soil": _tone((38, 24, 14), (44, 22, 18), hour),
        "blue": _tone((70, 130, 245), (110, 170, 255), hour),
        "gold": _tone((245, 210, 50), (255, 186, 60), hour),
        "pink": _tone((255, 110, 186), (255, 80, 196), hour),
    }


def _noise(ix: np.ndarray, iz: np.ndarray) -> np.ndarray:
    n = (ix * np.int64(374761393) + iz * np.int64(668265263)) & np.int64(0x7FFFFFFF)
    n = (n ^ (n >> 13)) * np.int64(1274126177)
    return (n >> 16) & np.int64(255)


def _ground(view: pygame.Surface, cam: Camera, hour: int):
    y0 = HORIZON + 1
    height = VH - y0
    if height <= 0:
        return
    gw, gh = 180, 92
    sy = y0 + (np.arange(gh, dtype=np.float32) + 0.5) * ((VH - y0) / gh)
    depth = (FOCAL * np.float32(cam.eye)) / np.maximum(sy - HORIZON, 1.0)
    depth = np.minimum(depth, np.float32(36.0))
    xx = (np.arange(gw, dtype=np.float32) + 0.5) * (VW / gw)
    x_cam = (xx[None, :] - np.float32(_CX)) * (depth[:, None] / np.float32(FOCAL))
    c = math.cos(cam.yaw)
    s = math.sin(cam.yaw)
    depth_c = depth[:, None]
    wx = np.float32(cam.x) + x_cam * c + depth_c * s
    wz = np.float32(cam.z) - x_cam * s + depth_c * c
    tones = _carpet(hour)
    grain = _noise(
        np.floor(wx * 42.0).astype(np.int64), np.floor(wz * 42.0).astype(np.int64)
    ).astype(np.float32)
    patch = _noise(
        np.floor(wx * 1.5).astype(np.int64), np.floor(wz * 1.5).astype(np.int64)
    ).astype(np.float32)
    base = np.array(tones["mid"], np.float32)
    img = base + (grain[..., None] - 128.0) * np.array([0.045, 0.08, 0.03], np.float32)
    img += (patch[..., None] - 128.0) * np.array([0.07, 0.11, 0.035], np.float32)
    wobble = (patch - 128.0) / 128.0 * 0.16
    path = np.abs(wx) < (0.58 + wobble)
    soil = np.array(tones["soil"], np.float32)
    img[path] = soil + (grain[path, None] - 128.0) * np.float32(0.035)
    near = depth[:, None] < 8.5
    flower = (~path) & near & ((grain.astype(np.int64) % 97) == 0)
    names = ("blue", "gold", "pink")
    ys, xs = np.nonzero(flower)
    for y, x in zip(ys.tolist(), xs.tolist()):
        col = np.array(tones[names[int(patch[y, x]) % 3]], np.float32)
        y1, x1 = min(gh, y + 2), min(gw, x + 2)
        img[y:y1, x:x1] = col
    fog = np.clip((depth - 8.0) / 18.0, 0.0, 1.0) ** 1.15
    hot = np.array(horizon_color(hour), np.float32)
    img = img * (1.0 - fog[:, None, None]) + hot * fog[:, None, None]
    frame = np.ascontiguousarray(np.clip(img, 0, 255).astype(np.uint8).transpose(1, 0, 2))
    small = pygame.surfarray.make_surface(frame)
    view.blit(pygame.transform.scale(small, (VW, height)), (0, y0))


def _sun(surf, cam: Camera, hour: int):
    spot = project_direction(sun_vector(hour), cam.yaw)
    if spot is None:
        return
    sx, sy = int(spot[0]), int(spot[1])
    hot = horizon_color(hour)
    halo = tuple(min(255, int(c * 0.55 + 24)) for c in hot)
    core = tuple(min(255, c + 70) for c in hot)
    ray = tuple(max(0, min(255, int(c * 0.38))) for c in hot)
    pygame.draw.circle(surf, halo, (sx, sy), 22)
    for k in range(6):
        ang = -2.55 + k * 0.32
        length = 34 + (k % 3) * 12
        pygame.draw.line(
            surf, ray, (sx, sy),
            (sx + int(math.cos(ang) * length), sy + int(math.sin(ang) * length)),
            1,
        )
    pygame.draw.circle(surf, hot, (sx, sy), 12)
    pygame.draw.circle(surf, core, (sx, sy), 5)


def _stars(surf, cam: Camera, hour: int):
    v = int(80 + 140 * (hour / 4.0))
    col = (v // 3, max(40, v // 2), min(255, v))
    for dx, dy, dz, size in _STARS:
        spot = project_direction((dx, dy, dz), cam.yaw)
        if spot is None or spot[1] > HORIZON - 4:
            continue
        x, y = int(spot[0]), int(spot[1])
        if 0 <= x < VW and 0 <= y < VH:
            pygame.draw.rect(surf, col, (x, y, size, size))


def _sway(pts: np.ndarray, beat: float) -> np.ndarray:
    if len(pts) == 0:
        return pts
    out = np.array(pts, np.float32, copy=True)
    wave = np.sin(beat * 0.85 + out[:, 2] * 0.42).astype(np.float32)
    out[:, 0] += wave * out[:, 1] * np.float32(0.03)
    return out


def _to_camera(pts: np.ndarray, cam: Camera) -> np.ndarray:
    dx = pts[:, 0] - cam.x
    dy = pts[:, 1] - cam.eye
    dz = pts[:, 2] - cam.z
    c, s = math.cos(cam.yaw), math.sin(cam.yaw)
    out = np.empty_like(pts)
    out[:, 0] = dx * c - dz * s
    out[:, 1] = dy
    out[:, 2] = dx * s + dz * c
    return out


def _clip_pair(a: np.ndarray, b: np.ndarray):
    """Coupe au plan proche. Renvoie aussi le masque des segments gardés."""
    za = a[:, 2]
    zb = b[:, 2]
    keep = (za >= NEAR) | (zb >= NEAR)
    if not np.any(keep):
        empty = a[:0]
        return empty, empty, keep
    a = a[keep].copy()
    b = b[keep].copy()
    za = a[:, 2]
    zb = b[:, 2]
    denom = np.where(np.abs(zb - za) < 1e-5, np.float32(1e-5), zb - za)
    t = np.clip((NEAR - za) / denom, 0.0, 1.0)[:, None]
    hit = a + (b - a) * t
    a = np.where((za < NEAR)[:, None], hit, a)
    b = np.where((zb < NEAR)[:, None], hit, b)
    return a, b, keep


def _project(pts: np.ndarray):
    z = np.maximum(pts[:, 2], NEAR)
    sx = _CX + FOCAL * pts[:, 0] / z
    sy = HORIZON - FOCAL * pts[:, 1] / z
    return sx, sy, z


def _haze(hour: int) -> np.ndarray:
    hot = np.array(horizon_color(hour), np.float32)
    return hot * 0.22 + np.array([6, 8, 12], np.float32)


def _fog_of(z: float, hour: int, rgb) -> tuple[int, int, int]:
    haze = _haze(hour)
    fog = min(1.0, max(0.0, (z - 6.0) / 20.0)) ** 1.25
    return tuple(int(rgb[k] * (1.0 - fog) + haze[k] * fog) for k in range(3))


def _dab(surf, x, int_y, ri: float, col, seed: int):
    """Plusieurs aplats, pas un disque : une touche de feuille."""
    y = int_y
    shade = tuple(max(0, int(c * 0.55)) for c in col)
    lit = tuple(min(255, int(c * 0.65 + 78)) for c in col)
    side = max(3, int(ri * 0.8))
    count = 5 if ri < 9 else 7
    for k in range(count):
        h = seed * 13 + k * 17
        ox = ((h % 7) - 3) * ri * 0.18
        oy = (((h // 7) % 7) - 3) * ri * 0.16
        paint = col if k % 3 else (lit if (k % 2) else shade)
        pygame.draw.rect(
            surf, paint,
            (int(x + ox - side * 0.5), int(y + oy - side * 0.4), side, int(side * 1.1)),
        )


def _plants(surf, batch, cam: Camera, hour: int, beat: float):
    items = []
    items.extend(_woody(batch, cam, hour, beat))
    items.extend(_leaf_items(batch, cam, hour, beat))
    items.extend(_bloom_items(batch, cam, hour))
    items.sort(key=lambda item: -item[0])
    for _z, kind, payload in items:
        if kind == 0:
            pygame.draw.polygon(surf, payload[1], payload[0])
        elif kind == 1:
            _dab(surf, *payload)
        else:
            x, y, rad, col, core = payload
            if rad < 3:
                pygame.draw.rect(surf, core, (x, y, rad, rad))
                continue
            pygame.draw.circle(surf, col, (x, y), rad)
            pygame.draw.circle(surf, core, (x, y), max(2, rad // 2))
            for k in range(5):
                ang = k * math.tau / 5.0 + 0.4
                pygame.draw.rect(
                    surf, col,
                    (x + int(math.cos(ang) * rad * 1.35), y + int(math.sin(ang) * rad * 1.15), 2, 2),
                )


def _bundle(batch, beat: float):
    return _sway(batch.a, beat), _sway(batch.b, beat + 0.4), batch.rgb, batch.wide


def _woody(batch, cam: Camera, hour: int, beat: float):
    if len(batch.a) == 0:
        return []
    world_a, world_b, world_c, world_w = _bundle(batch, beat)
    cam_a = _to_camera(world_a, cam)
    cam_b = _to_camera(world_b, cam)
    cam_a, cam_b, keep = _clip_pair(cam_a, cam_b)
    if len(cam_a) == 0:
        return []
    rgb = world_c[keep]
    wide = world_w[keep]
    wa = world_a[keep]
    wb = world_b[keep]
    dy = np.abs(wb[:, 1] - wa[:, 1])
    horiz = np.hypot(wb[:, 0] - wa[:, 0], wb[:, 2] - wa[:, 2])
    trunk = (wide >= 1.45) | ((dy > horiz * 0.9) & (wide >= 1.0))
    show = trunk
    if not np.any(show):
        return []
    zmid = (cam_a[:, 2] + cam_b[:, 2]) * 0.5
    show &= (zmid > 0.6) & (zmid < 20.0)
    idx = np.flatnonzero(show)
    if len(idx) == 0:
        return []
    if len(idx) > _MAX_WOODY:
        idx = idx[np.argpartition(zmid[idx], _MAX_WOODY)[:_MAX_WOODY]]
    out = []
    span = 70
    for i in idx:
        z = float(zmid[i])
        thick = bool(trunk[i])
        half = (0.085 if thick else 0.02) + 0.018 * float(wide[i])
        px = FOCAL * half / max(z, 0.6)
        if px < 1.3:
            continue
        poly = _ribbon(cam_a[i], cam_b[i], half)
        if poly is None:
            continue
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        if max(xs) < -span or min(xs) > VW + span or max(ys) < -span or min(ys) > VH + span:
            continue
        if max(xs) - min(xs) > 160 or max(ys) - min(ys) > 150:
            continue
        col = _fog_of(z, hour, rgb[i])
        if thick:
            col = tuple(max(0, int(c * 0.82)) for c in col)
        out.append((z, 0, (poly, col)))
    return out


def _ribbon(a, b, half: float):
    ax, ay, az = float(a[0]), float(a[1]), float(a[2])
    bx, by, bz = float(b[0]), float(b[1]), float(b[2])
    dx, dy = bx - ax, by - ay
    mag = math.hypot(dx, dy)
    if mag < 1e-4:
        sx, sy = half, 0.0
    else:
        sx, sy = dy / mag * half, -dx / mag * half
    pts = (
        (ax + sx, ay + sy, az),
        (ax - sx, ay - sy, az),
        (bx - sx, by - sy, bz),
        (bx + sx, by + sy, bz),
    )
    screen = []
    for x, y, z in pts:
        if z < NEAR:
            return None
        screen.append((int(_CX + FOCAL * x / z), int(HORIZON - FOCAL * y / z)))
    return screen


def _leaf_items(batch, cam: Camera, hour: int, beat: float):
    lc = batch.leaf_c
    if len(lc) == 0:
        return []
    swayed = _sway(lc, beat)
    cam_pts = _to_camera(swayed, cam)
    z = cam_pts[:, 2]
    safe = np.maximum(z, NEAR)
    world_r = np.maximum(batch.leaf_r, np.float32(0.46))
    rad = FOCAL * world_r * np.float32(1.15) / safe
    sx = _CX + FOCAL * cam_pts[:, 0] / safe
    sy = HORIZON - FOCAL * cam_pts[:, 1] / safe
    keep = (swayed[:, 1] > 0.5) & (z > 0.9) & (z < 12.0) & (rad > 2.0)
    keep &= (sx > -24) & (sx < VW + 24) & (sy > -24) & (sy < VH + 24)
    idx = np.flatnonzero(keep)
    if len(idx) == 0:
        return []
    if len(idx) > _MAX_HIGH:
        idx = idx[np.argpartition(z[idx], _MAX_HIGH)[:_MAX_HIGH]]
    rgb = batch.leaf_rgb
    out = []
    for i in idx:
        zi = float(z[i])
        ri = min(float(rad[i]), 16.0)
        col = _fog_of(zi, hour, rgb[i])
        out.append((zi, 1, (int(sx[i]), int(sy[i]), ri, col, int(i))))
    return out


def _bloom_items(batch, cam: Camera, hour: int):
    if len(batch.blooms) == 0:
        return []
    pts = _to_camera(batch.blooms, cam)
    sx, sy, z = _project(pts)
    visible = (z >= NEAR) & (z <= 14) & (batch.bloom_r >= 0.04)
    visible &= (sx > -12) & (sx < VW + 12) & (sy > -12) & (sy < VH + 12)
    idx = np.flatnonzero(visible)
    if len(idx) == 0:
        return []
    if len(idx) > 160:
        idx = idx[np.argpartition(z[idx], 160)[:160]]
    out = []
    for i in idx:
        zi = float(z[i])
        col = _fog_of(zi, hour, batch.bloom_rgb[i])
        core = tuple(min(255, c + 70) for c in col)
        world_r = float(batch.bloom_r[i])
        if world_r < 0.04:
            continue
        rad = int(max(2, min(8, FOCAL * world_r / zi)))
        out.append((zi, 2, (int(sx[i]), int(sy[i]), rad, col, core)))
    return out


def _spores(surf, batch, cam: Camera):
    pts = getattr(batch, "spores", None)
    if pts is None or len(pts) == 0:
        return
    cam_pts = _to_camera(pts, cam)
    sx, sy, z = _project(cam_pts)
    rgb = batch.spore_rgb
    for i in range(len(pts)):
        zi = float(z[i])
        if zi < NEAR or zi > 22:
            continue
        x, y = int(sx[i]), int(sy[i])
        if not (0 <= x < VW and 0 <= y < HORIZON + 30):
            continue
        pygame.draw.rect(surf, (int(rgb[i, 0]), int(rgb[i, 1]), int(rgb[i, 2])), (x, y, 2, 2))


def _grass(surf, cam: Camera, hour: int, beat: float):
    step = 0.22
    anchor = math.floor(cam.z / step) * step
    xs = np.arange(-3.0, 3.01, step, dtype=np.float32)
    zs = anchor + np.arange(0.25, 4.4, step, dtype=np.float32)
    grid_x, grid_z = np.meshgrid(xs, zs)
    x = grid_x.ravel()
    z = grid_z.ravel()
    hsh = _noise(np.floor(x * 8.0).astype(np.int64), np.floor(z * 8.0).astype(np.int64))
    keep = (np.abs(x) > 0.58) & ((hsh % 3) != 0)
    x, z, hsh = x[keep], z[keep], hsh[keep]
    if len(x) > 200:
        pick = np.arange(0, len(x), max(1, len(x) // 200))[:200]
        x, z, hsh = x[pick], z[pick], hsh[pick]
    if len(x) == 0:
        return
    jitter = (hsh.astype(np.float32) - 128.0) * np.float32(0.0011)
    x = x + jitter
    height = 0.16 + (hsh % 11).astype(np.float32) * 0.028
    height = np.where((hsh % 8) == 0, height * 1.85, height)
    lean = np.sin(np.float32(beat) * 1.4 + z * 0.9).astype(np.float32) * np.float32(0.04)
    base = np.stack([x, np.zeros_like(x), z], axis=1)
    tip = np.stack([x + lean, height, z + lean * 0.25], axis=1)
    wide = 0.045 + (hsh % 4).astype(np.float32) * 0.012
    side = np.stack([wide, np.zeros_like(x), np.zeros_like(x)], axis=1)
    cam_a = _to_camera(base - side, cam)
    cam_b = _to_camera(base + side, cam)
    cam_t = _to_camera(tip, cam)
    ok = (cam_a[:, 2] > NEAR) & (cam_t[:, 2] > NEAR) & (cam_t[:, 2] < 7.0)
    tones = _carpet(hour)
    colors = (tones["deep"], tones["mid"], tones["light"], tones["sun"])
    flowers = (tones["blue"], tones["gold"], tones["pink"])
    for i in np.flatnonzero(ok):
        za = max(float(cam_a[i, 2]), NEAR)
        zt = max(float(cam_t[i, 2]), NEAR)
        ax = int(_CX + FOCAL * float(cam_a[i, 0]) / za)
        ay = int(HORIZON - FOCAL * float(cam_a[i, 1]) / za)
        bx = int(_CX + FOCAL * float(cam_b[i, 0]) / float(cam_b[i, 2]))
        by = int(HORIZON - FOCAL * float(cam_b[i, 1]) / float(cam_b[i, 2]))
        tx = int(_CX + FOCAL * float(cam_t[i, 0]) / zt)
        ty = int(HORIZON - FOCAL * float(cam_t[i, 1]) / zt)
        if max(ax, bx, tx) < -8 or min(ax, bx, tx) > VW + 8:
            continue
        if ty > VH + 4 or ay < HORIZON - 8:
            continue
        col = colors[int(hsh[i]) % 4]
        pygame.draw.polygon(surf, col, ((ax, ay), (bx, by), (tx, ty)))
        if int(hsh[i]) % 7 == 0:
            pygame.draw.rect(surf, flowers[int(hsh[i]) % 3], (tx - 1, ty - 1, 3, 3))
