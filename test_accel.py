"""Decode BMA220 et angles d'inclinaison, sans materiel."""

from device.accel import decode_axis, tilt_from_gravity


def test_decode_axis():
    assert decode_axis(0x00) == 0.0
    # 16 << 2 = 0x40 : +1 g a ±2 g (divi 16).
    assert abs(decode_axis(0x40) - 1.0) < 1e-9
    # Valeur signee 6 bits : 0b111111 << 2 → -1/16 g.
    assert abs(decode_axis(0xFC) - (-1.0 / 16.0)) < 1e-9


def test_tilt_rest_upright():
    roll, pitch = tilt_from_gravity(0.0, -1.0, 0.0)
    assert abs(roll) < 1e-9
    assert abs(pitch) < 1e-9


def test_tilt_lean():
    roll, pitch = tilt_from_gravity(0.5, -0.866, 0.0)
    assert roll > 0.4
    assert abs(pitch) < 0.05
    roll2, pitch2 = tilt_from_gravity(0.0, -0.866, 0.5)
    assert abs(roll2) < 0.05
    assert pitch2 > 0.4


def test_tilt_calibration():
    rest = tilt_from_gravity(0.1, -0.99, 0.05)
    roll, pitch = tilt_from_gravity(0.1, -0.99, 0.05, rest=rest)
    assert abs(roll) < 1e-9
    assert abs(pitch) < 1e-9


if __name__ == "__main__":
    test_decode_axis()
    test_tilt_rest_upright()
    test_tilt_lean()
    test_tilt_calibration()
    print("ok")
