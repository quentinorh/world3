"""BMA220 (DFRobot SEN0168) sur I2C : inclinaison de l'ecran.

Branchement sur le Raspberry Pi 3 B+ (bus I2C1, deja allume pour la dalle) :

  Capteur     Pi (GPIO, broches physiques)
  ---------   ----------------------------
  VCC         3,3 V  (broche 1) — pas le 5 V
  GND         GND    (broche 6 ou 9)
  SDA         GPIO2  (broche 3)
  SCL         GPIO3  (broche 5)
  INT         non branche (polling)

Adresse I2C : 0x0A ou 0x0B selon CSB. On essaie les deux.

Hypothese de pose : le module est fixe par rapport a l'ecran, axes du
chip alignes a peu pres avec l'ecran (X vers la droite, Y vers le haut,
Z vers l'utilisateur). Si le globe penche a l'envers, inverser un signe
dans `AXIS_ROLL` / `AXIS_PITCH`, ou tourner le module.

`WORLD3_ACCEL=0` desactive la lecture. Sans capteur, le module renvoie
None et le jeu ignore l'inclinaison (les fleches haut/bas restent un
ersatz sur ordinateur).
"""

from __future__ import annotations

import math
import os
import time

# Adresses DFRobot (CSB) et Bosch par defaut.
_ADDRS = (0x0A, 0x0B)
_REG_ACC_X = 0x04
_REG_ACC_Y = 0x06
_REG_ACC_Z = 0x08
_REG_FILTER = 0x20
_REG_RANGE = 0x22
# Ne pas lire 0x32 : une lecture bascule le soft-reset.

_I2C_SLAVE = 0x0703
# Filtre bas : moins de bruit pour l'inclinaison (datasheet 0x00..0x05).
_FILTER = 0x05
# ±2 g.
_RANGE = 0x00
_DIV = 16.0

# Sens capteur → angles ecran. Inverser (±1) si la pose differe.
AXIS_ROLL = 1.0
AXIS_PITCH = 1.0
# Signe de l'axe Y vers le decalage de yaw du globe WORLD3.
AXIS_Y = -1.0


def _disabled():
    return os.environ.get("WORLD3_ACCEL", "1") == "0"


def decode_axis(raw: int) -> float:
    """Octet registre → acceleration en g (6 bits signes, bits 7:2)."""
    value = (raw & 0xFF) >> 2
    if value & 0x20:
        value -= 0x40
    return value / _DIV


def tilt_from_gravity(x: float, y: float, z: float, rest=None):
    """Roulement et tangage (radians) d'apres le vecteur g.

    Au repos ecran debout face a l'utilisateur, g ≈ (0, ±1, 0) :
    les deux angles sont nuls apres calibration.
    """
    roll = math.atan2(x, math.hypot(y, z))
    pitch = math.atan2(z, math.hypot(x, y))
    if rest is not None:
        roll -= rest[0]
        pitch -= rest[1]
    return AXIS_ROLL * roll, AXIS_PITCH * pitch


class _Bus:
    def __init__(self, path: str):
        self.fd = os.open(path, os.O_RDWR)
        self._addr = None

    def close(self):
        fd = self.fd
        self.fd = -1
        if fd >= 0:
            os.close(fd)

    def _select(self, addr: int):
        if self._addr == addr:
            return
        import fcntl

        fcntl.ioctl(self.fd, _I2C_SLAVE, addr)
        self._addr = addr

    def write_reg(self, addr: int, reg: int, value: int):
        self._select(addr)
        os.write(self.fd, bytes((reg & 0xFF, value & 0xFF)))

    def read_reg(self, addr: int, reg: int) -> int:
        self._select(addr)
        os.write(self.fd, bytes((reg & 0xFF,)))
        data = os.read(self.fd, 1)
        if not data:
            raise OSError("lecture I2C vide")
        return data[0]


class Accel:
    """Lecteur BMA220. `open()` renvoie None hors Pi ou sans capteur."""

    def __init__(self, bus: _Bus, addr: int):
        self._bus = bus
        self.addr = addr
        self.rest = None
        self._rest_n = 0
        self._rest_sum = (0.0, 0.0)
        self.rest_y = None
        self._rest_y_n = 0
        self._rest_y_sum = 0.0
        self._last = None
        self._last_t = 0.0
        self._last_y = None
        self._last_y_t = 0.0

    @classmethod
    def open(cls, bus_id: int | None = None):
        sensor, _reason = cls.open_with_reason(bus_id)
        return sensor

    @classmethod
    def open_with_reason(cls, bus_id: int | None = None):
        """(Accel|None, motif). Le motif sert a l'ecran de test du menu."""
        if _disabled():
            return None, "WORLD3_ACCEL=0"
        if bus_id is None:
            raw = os.environ.get("WORLD3_ACCEL_BUS", "1")
            try:
                bus_id = int(raw)
            except ValueError:
                bus_id = 1
        path = f"/dev/i2c-{bus_id}"
        if not os.path.exists(path):
            return None, f"pas de {path} (modprobe i2c-dev)"
        try:
            bus = _Bus(path)
        except OSError as err:
            return None, f"ouverture {path}: {err}"
        last_err = "aucune adresse 0x0A/0x0B"
        for addr in _ADDRS:
            try:
                bus.write_reg(addr, _REG_RANGE, _RANGE)
                bus.write_reg(addr, _REG_FILTER, _FILTER)
                raw = bus.read_reg(addr, _REG_ACC_X)
                decode_axis(raw)
            except OSError as err:
                last_err = f"0x{addr:02X}: {err}"
                continue
            return cls(bus, addr), f"ok 0x{addr:02X}"
        bus.close()
        return None, last_err

    def close(self):
        bus = self._bus
        self._bus = None
        if bus is not None:
            bus.close()

    def recalibrate(self):
        """Reprend le zero a la pose actuelle de l'ecran."""
        self.rest = None
        self._rest_n = 0
        self._rest_sum = (0.0, 0.0)
        self.rest_y = None
        self._rest_y_n = 0
        self._rest_y_sum = 0.0
        self._last = None
        self._last_t = 0.0
        self._last_y = None
        self._last_y_t = 0.0

    def read_g(self):
        """Triplet (x, y, z) en g, ou None si la lecture echoue."""
        bus = self._bus
        if bus is None:
            return None
        try:
            x = decode_axis(bus.read_reg(self.addr, _REG_ACC_X))
            y = decode_axis(bus.read_reg(self.addr, _REG_ACC_Y))
            z = decode_axis(bus.read_reg(self.addr, _REG_ACC_Z))
        except OSError:
            return None
        return x, y, z

    def read_y_delta(self, min_interval=0.06):
        """Ecart de l'axe Y par rapport au repos, en g (signe AXIS_Y)."""
        now = time.perf_counter()
        if self._last_y is not None and now - self._last_y_t < min_interval:
            return self._last_y
        sample = self.read_g()
        if sample is None:
            return self._last_y
        _x, y, _z = sample
        if self.rest_y is None:
            self._rest_y_n += 1
            self._rest_y_sum += y
            if self._rest_y_n >= 8:
                self.rest_y = self._rest_y_sum / float(self._rest_y_n)
            self._last_y = 0.0
            self._last_y_t = now
            return self._last_y
        self._last_y = AXIS_Y * (y - self.rest_y)
        self._last_y_t = now
        return self._last_y

    def read_tilt(self, min_interval=0.04):
        """(roll, pitch) en radians, calibres au repos. None si indisponible."""
        now = time.perf_counter()
        if self._last is not None and now - self._last_t < min_interval:
            return self._last
        sample = self.read_g()
        if sample is None:
            return self._last
        roll, pitch = tilt_from_gravity(*sample)
        if self.rest is None:
            self._rest_n += 1
            self._rest_sum = (self._rest_sum[0] + roll, self._rest_sum[1] + pitch)
            # Quelques lectures pour figer le zero (ecran deja en place).
            if self._rest_n >= 8:
                n = float(self._rest_n)
                self.rest = (self._rest_sum[0] / n, self._rest_sum[1] / n)
            self._last = (0.0, 0.0)
            self._last_t = now
            return self._last
        roll, pitch = tilt_from_gravity(*sample, rest=self.rest)
        self._last = (roll, pitch)
        self._last_t = now
        return self._last


def main(argv=None):
    """Diag : affiche x/y/z et les angles jusqu'a Ctrl+C."""
    del argv
    sensor = Accel.open()
    if sensor is None:
        print("Pas de BMA220 (bus, alimentation, ou WORLD3_ACCEL=0).")
        return 1
    print(f"BMA220 sur 0x{sensor.addr:02X}")
    try:
        while True:
            g = sensor.read_g()
            tilt = sensor.read_tilt(min_interval=0.0)
            if g is None or tilt is None:
                print("lecture ratee")
            else:
                x, y, z = g
                roll, pitch = tilt
                print(
                    f"x={x:+.3f} y={y:+.3f} z={z:+.3f}  "
                    f"roll={math.degrees(roll):+.1f}° pitch={math.degrees(pitch):+.1f}°"
                )
            time.sleep(0.15)
    except KeyboardInterrupt:
        print()
    finally:
        sensor.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
