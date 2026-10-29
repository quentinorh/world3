"""Balayage de la dalle Waveshare, sans SDL kmsdrm.

kmsdrm affiche un tampon 32 bits. Cette dalle, elle, montre le tampon
16 bits du firmware (720x720, RGB565). On allume ce balayage nous-memes
et on y copie chaque image. Le tactile Goodix arrive par evdev : le
pilote video dummy de SDL ne le lit pas.
"""

from __future__ import annotations

import ctypes
import glob
import mmap
import os
import struct

import pygame

_EVENT = struct.Struct("IIHHi")
_EV_SYN = 0
_EV_KEY = 1
_EV_ABS = 3
_BTN_TOUCH = 330
_ABS_X = 0
_ABS_Y = 1
_ABS_MT_X = 0x35
_ABS_MT_Y = 0x36
_ABS_MT_ID = 0x39
_KDSETMODE = 0x4B3A
_KD_TEXT = 0
_KD_GRAPHICS = 1
# Mode releve sur la dalle (le journal y etait lisible).
_CLOCK = 44000
_FLAGS = 6


class _Mode(ctypes.Structure):
    _fields_ = [
        ("clock", ctypes.c_uint32),
        ("hdisplay", ctypes.c_uint16),
        ("hsync_start", ctypes.c_uint16),
        ("hsync_end", ctypes.c_uint16),
        ("htotal", ctypes.c_uint16),
        ("hskew", ctypes.c_uint16),
        ("vdisplay", ctypes.c_uint16),
        ("vsync_start", ctypes.c_uint16),
        ("vsync_end", ctypes.c_uint16),
        ("vtotal", ctypes.c_uint16),
        ("vscan", ctypes.c_uint16),
        ("vrefresh", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("type", ctypes.c_uint32),
        ("name", ctypes.c_char * 32),
    ]


class _Res(ctypes.Structure):
    _fields_ = [
        ("count_fbs", ctypes.c_int),
        ("fbs", ctypes.POINTER(ctypes.c_uint32)),
        ("count_crtcs", ctypes.c_int),
        ("crtcs", ctypes.POINTER(ctypes.c_uint32)),
        ("count_connectors", ctypes.c_int),
        ("connectors", ctypes.POINTER(ctypes.c_uint32)),
        ("count_encoders", ctypes.c_int),
        ("encoders", ctypes.POINTER(ctypes.c_uint32)),
        ("min_width", ctypes.c_uint32),
        ("max_width", ctypes.c_uint32),
        ("min_height", ctypes.c_uint32),
        ("max_height", ctypes.c_uint32),
    ]


class _Crtc(ctypes.Structure):
    _fields_ = [
        ("crtc_id", ctypes.c_uint32),
        ("buffer_id", ctypes.c_uint32),
        ("x", ctypes.c_uint32),
        ("y", ctypes.c_uint32),
        ("width", ctypes.c_uint32),
        ("height", ctypes.c_uint32),
        ("mode_valid", ctypes.c_int),
        ("mode", _Mode),
        ("gamma_size", ctypes.c_int),
    ]


class _Conn(ctypes.Structure):
    _fields_ = [
        ("connector_id", ctypes.c_uint32),
        ("encoder_id", ctypes.c_uint32),
        ("connector_type", ctypes.c_uint32),
        ("connector_type_id", ctypes.c_uint32),
        ("connection", ctypes.c_int),
    ]


class _Enc(ctypes.Structure):
    _fields_ = [
        ("encoder_id", ctypes.c_uint32),
        ("encoder_type", ctypes.c_uint32),
        ("crtc_id", ctypes.c_uint32),
        ("possible_crtcs", ctypes.c_uint32),
        ("possible_clones", ctypes.c_uint32),
    ]


def _drm():
    lib = ctypes.CDLL("libdrm.so.2", use_errno=True)
    lib.drmModeGetResources.restype = ctypes.POINTER(_Res)
    lib.drmModeGetResources.argtypes = [ctypes.c_int]
    lib.drmModeGetCrtc.restype = ctypes.POINTER(_Crtc)
    lib.drmModeGetCrtc.argtypes = [ctypes.c_int, ctypes.c_uint32]
    lib.drmModeFreeCrtc.argtypes = [ctypes.c_void_p]
    lib.drmModeFreeResources.argtypes = [ctypes.c_void_p]
    lib.drmModeGetConnector.restype = ctypes.c_void_p
    lib.drmModeGetConnector.argtypes = [ctypes.c_int, ctypes.c_uint32]
    lib.drmModeFreeConnector.argtypes = [ctypes.c_void_p]
    lib.drmModeGetEncoder.restype = ctypes.c_void_p
    lib.drmModeGetEncoder.argtypes = [ctypes.c_int, ctypes.c_uint32]
    lib.drmModeFreeEncoder.argtypes = [ctypes.c_void_p]
    lib.drmSetMaster.argtypes = [ctypes.c_int]
    lib.drmSetMaster.restype = ctypes.c_int
    lib.drmDropMaster.argtypes = [ctypes.c_int]
    lib.drmDropMaster.restype = ctypes.c_int
    lib.drmModeCreateDumbBuffer.restype = ctypes.c_int
    lib.drmModeCreateDumbBuffer.argtypes = [
        ctypes.c_int,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_uint64),
    ]
    lib.drmModeMapDumbBuffer.restype = ctypes.c_int
    lib.drmModeMapDumbBuffer.argtypes = [
        ctypes.c_int,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint64),
    ]
    lib.drmModeAddFB.restype = ctypes.c_int
    lib.drmModeAddFB.argtypes = [
        ctypes.c_int,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_uint8,
        ctypes.c_uint8,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
    ]
    lib.drmModeSetCrtc.restype = ctypes.c_int
    lib.drmModeSetCrtc.argtypes = [
        ctypes.c_int,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.c_int,
        ctypes.POINTER(_Mode),
    ]
    return lib


def _check(rc, label):
    if rc == 0:
        return
    err = ctypes.get_errno()
    raise OSError(err or abs(rc), label)


def _fallback_mode():
    mode = _Mode()
    mode.clock = _CLOCK
    mode.hdisplay = 720
    mode.hsync_start = 820
    mode.hsync_end = 900
    mode.htotal = 976
    mode.vdisplay = 720
    mode.vsync_start = 738
    mode.vsync_end = 742
    mode.vtotal = 754
    mode.vrefresh = 60
    mode.flags = _FLAGS
    mode.name = b"720x720"
    return mode


def _copy_mode(src):
    mode = _Mode()
    for name, _typ in _Mode._fields_:
        setattr(mode, name, getattr(src, name))
    return mode


class Panel:
    def __init__(self):
        self.fd = -1
        self.mm = None
        self.touch = -1
        self.view = None
        self.pitch = 0
        self.width = 0
        self.height = 0
        self._graphics = False
        self._x = 0
        self._y = 0
        self._down = False
        self._buf = b""
        self._lib = None

    @staticmethod
    def available():
        if os.environ.get("WORLD3_PANEL") == "0":
            return False
        try:
            with open("/sys/class/graphics/fb0/name", encoding="ascii") as handle:
                name = handle.read().strip()
        except OSError:
            return False
        return name.startswith("vc4") and os.path.exists("/dev/dri/card0")

    @classmethod
    def open(cls, width, height):
        panel = cls()
        try:
            panel._open(width, height)
        except Exception:
            panel.close()
            raise
        return panel

    def _open(self, width, height):
        self.width = int(width)
        self.height = int(height)
        self._lib = _drm()
        self.fd = os.open("/dev/dri/card0", os.O_RDWR | os.O_CLOEXEC)
        connector, crtc, mode = self._output()
        handle = ctypes.c_uint32()
        pitch = ctypes.c_uint32()
        size = ctypes.c_uint64()
        _check(
            self._lib.drmModeCreateDumbBuffer(
                self.fd, self.width, self.height, 16, 0,
                ctypes.byref(handle), ctypes.byref(pitch), ctypes.byref(size),
            ),
            "drmModeCreateDumbBuffer",
        )
        self.pitch = int(pitch.value)
        offset = ctypes.c_uint64()
        _check(
            self._lib.drmModeMapDumbBuffer(self.fd, handle.value, ctypes.byref(offset)),
            "drmModeMapDumbBuffer",
        )
        self.mm = mmap.mmap(
            self.fd, int(size.value), mmap.MAP_SHARED,
            mmap.PROT_READ | mmap.PROT_WRITE, offset=int(offset.value),
        )
        fb = ctypes.c_uint32()
        _check(
            self._lib.drmModeAddFB(
                self.fd, self.width, self.height, 16, 16,
                self.pitch, handle.value, ctypes.byref(fb),
            ),
            "drmModeAddFB",
        )
        _check(self._lib.drmSetMaster(self.fd), "drmSetMaster")
        cid = ctypes.c_uint32(connector)
        rc = self._lib.drmModeSetCrtc(
            self.fd, crtc, fb.value, 0, 0, ctypes.byref(cid), 1, ctypes.byref(mode),
        )
        if rc != 0:
            mode = _fallback_mode()
            _check(
                self._lib.drmModeSetCrtc(
                    self.fd, crtc, fb.value, 0, 0, ctypes.byref(cid), 1, ctypes.byref(mode),
                ),
                "drmModeSetCrtc",
            )
        self.view = pygame.Surface(
            (self.width, self.height), depth=16, masks=(0xF800, 0x07E0, 0x001F, 0),
        )
        self._graphics = self._set_console(_KD_GRAPHICS)
        self.touch = self._open_touch()
        print(
            "Ecran : {}x{} RGB565, {} octets/ligne.".format(self.width, self.height, self.pitch),
            flush=True,
        )

    def _output(self):
        lib = self._lib
        res_ptr = lib.drmModeGetResources(self.fd)
        if not res_ptr:
            raise OSError("drmModeGetResources")
        res = res_ptr.contents
        connector = None
        encoder_crtc = 0
        try:
            for i in range(res.count_connectors):
                raw = lib.drmModeGetConnector(self.fd, int(res.connectors[i]))
                if not raw:
                    continue
                head = ctypes.cast(raw, ctypes.POINTER(_Conn)).contents
                connected = int(head.connection) == 1
                encoder_id = int(head.encoder_id)
                connector_id = int(head.connector_id)
                lib.drmModeFreeConnector(raw)
                if not connected:
                    continue
                connector = connector_id
                if encoder_id:
                    enc_raw = lib.drmModeGetEncoder(self.fd, encoder_id)
                    if enc_raw:
                        enc = ctypes.cast(enc_raw, ctypes.POINTER(_Enc)).contents
                        encoder_crtc = int(enc.crtc_id)
                        lib.drmModeFreeEncoder(enc_raw)
                break
            crtc_id = None
            mode = None
            fallback_crtc = encoder_crtc or None
            for i in range(res.count_crtcs):
                cid = int(res.crtcs[i])
                if fallback_crtc is None:
                    fallback_crtc = cid
                ptr = lib.drmModeGetCrtc(self.fd, cid)
                if not ptr:
                    continue
                crtc = ptr.contents
                valid = crtc.mode_valid and crtc.mode.hdisplay == self.width and crtc.mode.vdisplay == self.height
                if valid:
                    crtc_id = int(crtc.crtc_id)
                    mode = _copy_mode(crtc.mode)
                lib.drmModeFreeCrtc(ptr)
                if crtc_id is not None:
                    break
        finally:
            lib.drmModeFreeResources(res_ptr)
        if connector is None or (crtc_id is None and fallback_crtc is None):
            raise OSError("sortie HDMI introuvable")
        if crtc_id is None:
            crtc_id = fallback_crtc
            mode = _fallback_mode()
        elif mode is None or mode.clock == 0:
            mode = _fallback_mode()
        return connector, crtc_id, mode

    def _set_console(self, mode):
        targets = [0]
        try:
            targets.append(os.open("/dev/tty1", os.O_RDWR | os.O_NOCTTY))
        except OSError:
            pass
        try:
            for fd in targets:
                try:
                    import fcntl
                    fcntl.ioctl(fd, _KDSETMODE, mode)
                    return True
                except OSError:
                    continue
        finally:
            for fd in targets:
                if fd > 2:
                    os.close(fd)
        return False

    def _open_touch(self):
        import fcntl
        request = (2 << 30) | (256 << 16) | (ord("E") << 8) | 0x06
        for path in sorted(glob.glob("/dev/input/event*")):
            try:
                fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
            except OSError:
                continue
            try:
                raw = fcntl.ioctl(fd, request, b"\x00" * 256)
            except OSError:
                os.close(fd)
                continue
            name = raw.split(b"\x00", 1)[0].decode("ascii", "replace").lower()
            if "goodix" in name or "touch" in name:
                return fd
            os.close(fd)
        return -1

    def blit(self, surface):
        self.view.blit(surface, (0, 0))
        src_pitch = self.view.get_pitch()
        raw = self.view.get_buffer().raw
        if src_pitch == self.pitch:
            self.mm.seek(0)
            self.mm.write(raw)
        else:
            row = min(src_pitch, self.pitch, self.width * 2)
            for y in range(self.height):
                start = y * self.pitch
                src = y * src_pitch
                self.mm[start:start + row] = raw[src:src + row]

    def poll(self):
        if self.touch < 0:
            return
        try:
            chunk = os.read(self.touch, 64 * _EVENT.size)
        except BlockingIOError:
            return
        except OSError:
            return
        self._buf += chunk
        down = self._down
        x, y = self._x, self._y
        moved = False
        while len(self._buf) >= _EVENT.size:
            _sec, _usec, kind, code, value = _EVENT.unpack_from(self._buf)
            self._buf = self._buf[_EVENT.size:]
            if kind == _EV_ABS:
                if code in (_ABS_X, _ABS_MT_X):
                    x = value
                    moved = True
                elif code in (_ABS_Y, _ABS_MT_Y):
                    y = value
                    moved = True
                elif code == _ABS_MT_ID:
                    down = value >= 0
            elif kind == _EV_KEY and code == _BTN_TOUCH:
                down = value != 0
            elif kind == _EV_SYN and code == 0:
                self._emit(down, x, y, moved)
                moved = False

    def _emit(self, down, x, y, moved):
        x = max(0, min(self.width - 1, int(x)))
        y = max(0, min(self.height - 1, int(y)))
        was = self._down
        old = (self._x, self._y)
        self._x, self._y, self._down = x, y, down
        if down and not was:
            pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(x, y), button=1))
        elif down and was and (moved or (x, y) != old):
            pygame.event.post(
                pygame.event.Event(pygame.MOUSEMOTION, pos=(x, y), rel=(0, 0), buttons=(1, 0, 0))
            )
        elif (not down) and was:
            pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(x, y), button=1))

    def close(self):
        if self._graphics:
            self._set_console(_KD_TEXT)
            self._graphics = False
        if self.touch >= 0:
            os.close(self.touch)
            self.touch = -1
        if self.mm is not None:
            self.mm.close()
            self.mm = None
        if self.fd >= 0 and self._lib is not None:
            self._lib.drmDropMaster(self.fd)
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1
