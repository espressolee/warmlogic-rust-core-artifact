"""
Saturation Tests for Computing Module.
Targets: computing/__init__.py
"""

import unittest

from warm_logic.kernel.drone.reality.computing import (
    FloatingPointPrecision,
    TimerOverflow,
)


class TestComputingSaturation(unittest.TestCase):
    def test_float_quantize(self):
        fp = FloatingPointPrecision()
        val = 1.0 / 3.0
        q = fp.quantize_float32(val)
        self.assertNotEqual(q, val)  # Should lose precision
        self.assertAlmostEqual(q, val, places=6)

    def test_ulp(self):
        fp = FloatingPointPrecision()
        # Zero
        self.assertEqual(fp.get_ulp(0.0), 1.4e-45)
        # One
        self.assertEqual(fp.get_ulp(1.0), 1.1920928955078125e-07)
        # (2**(0-23) = 2^-23 ≈ 1.19e-7)

    def test_timer_overflow(self):
        t = TimerOverflow(max_value=10, current_value=0)

        # Normal tick
        t.tick(5)
        self.assertEqual(t.current_value, 5)
        self.assertEqual(t.overflow_count, 0)

        # Overflow
        t.tick(6)  # 5 + 6 = 11 > 10
        # 11 % 11 = 0
        self.assertEqual(t.current_value, 0)
        self.assertEqual(t.overflow_count, 1)
