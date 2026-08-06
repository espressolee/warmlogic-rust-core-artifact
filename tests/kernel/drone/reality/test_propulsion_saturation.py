"""
Saturation Tests for Propulsion Module.
Targets: motor.py, battery.py
"""

import math
import unittest
from warm_logic.kernel.drone.reality.propulsion.motor import BLDCMotor, ESCModel
from warm_logic.kernel.drone.reality.propulsion.battery import TheveninBattery, PeukertCapacity


class TestMotorSaturation(unittest.TestCase):
    def setUp(self):
        self.motor = BLDCMotor(kv=1000, rm=0.1, i0=0.5)
        self.esc = ESCModel()

    def test_bldc_constants(self):
        # Kt = 9.55 / Kv
        self.assertAlmostEqual(self.motor.kt, 0.00955)
        self.assertEqual(self.motor.kt, self.motor.ke)

    def test_back_emf(self):
        rpm = 6000
        # closure = 6000 * 2pi / 60 = 200pi ~ 628 rad/s
        # V = Ke * w
        bemf = self.motor.get_back_emf(rpm)
        self.assertGreater(bemf, 0)

    def test_operating_point_normal(self):
        # 10V, low torque
        rpm, i, eff = self.motor.calculate_operating_point(voltage=10.0, load_torque=0.01)
        self.assertGreater(rpm, 0)
        self.assertGreater(i, self.motor.i0)
        self.assertGreater(eff, 0)

    def test_operating_point_stall(self):
        # High torque that stalls motor (Back EMF <= 0 logic)
        # Torque = Kt * (I - I0) -> I_load very high
        # E = V - I*Rm. If I is huge, E becomes negative.
        stall_torque = 10.0 # Huge
        rpm, i, eff = self.motor.calculate_operating_point(voltage=10.0, load_torque=stall_torque)
        self.assertEqual(rpm, 0.0)
        self.assertEqual(eff, 0.0)

    def test_max_rpm(self):
        # V_eff = V - I0*Rm
        # RPM = V_eff * Kv
        max_rpm = self.motor.get_max_rpm(10.0)
        expected_v = 10.0 - (0.5 * 0.1)
        self.assertAlmostEqual(max_rpm, expected_v * 1000)
        
        # Zero max rpm (Low voltage)
        self.assertEqual(self.motor.get_max_rpm(0.01), 0.0)

    def test_esc_voltage(self):
        # Deadband
        self.assertEqual(self.esc.get_output_voltage(0.0, 10.0), 0.0)
        self.assertEqual(self.esc.get_output_voltage(0.04, 10.0), 0.0)
        
        # Linear region
        v_mid = self.esc.get_output_voltage(0.5, 10.0)
        self.assertGreater(v_mid, 0.0)
        self.assertLess(v_mid, 10.0)
        
        # Max
        v_max = self.esc.get_output_voltage(1.2, 10.0) # clamped
        # Slightly less than 10.0 due to dead time
        self.assertLess(v_max, 10.0) 

    def test_esc_losses(self):
        loss = self.esc.get_switching_losses(current_a=10.0)
        self.assertGreater(loss, 0)

    def test_esc_limit(self):
        self.assertEqual(self.esc.limit_current(10.0), 10.0)
        self.assertEqual(self.esc.limit_current(100.0), 30.0)


class TestBatterySaturation(unittest.TestCase):
    def setUp(self):
        self.lipo = TheveninBattery(cell_chemistry="LiPo")
        self.life = TheveninBattery(cell_chemistry="LiFePO4")
        self.liion = TheveninBattery(cell_chemistry="Li-ion")

    def test_ocv_lipo(self):
        # Full
        self.assertGreater(self.lipo.get_ocv(1.0), 4.0)
        # Empty
        self.assertLess(self.lipo.get_ocv(0.0), 3.5)
        # Clamped
        self.assertEqual(self.lipo.get_ocv(1.5), 4.2)
        
        # Direct property usage
        self.lipo.soc = 0.5
        self.assertGreater(self.lipo.get_ocv(), 3.0)

    def test_ocv_lifepo4(self):
        # Branches
        # > 0.9
        self.life.soc = 0.95
        v1 = self.life.get_ocv()
        self.assertGreater(v1, 3.35)
        
        # > 0.1
        self.life.soc = 0.5
        v2 = self.life.get_ocv()
        self.assertAlmostEqual(v2, 3.25 + 0.1 * 0.4 / 0.8)
        
        # <= 0.1
        self.life.soc = 0.05
        v3 = self.life.get_ocv()
        self.assertLess(v3, 3.0)

    def test_ocv_liion(self):
        self.liion.soc = 1.0
        self.assertEqual(self.liion.get_ocv(), 4.2)

    def test_terminal_voltage_dynamics(self):
        # Zero dt (static)
        v0 = self.lipo.get_terminal_voltage(current_a=10.0, dt=0.0)
        ocv = self.lipo.get_ocv() * 4
        ir = 10.0 * self.lipo.total_r0
        self.assertAlmostEqual(v0, ocv - ir)
        
        # Positive dt (dynamics)
        v1 = self.lipo.get_terminal_voltage(current_a=10.0, dt=1.0)
        # Internal states should occupy
        self.assertNotEqual(self.lipo._v_rc1, 0.0)
        
        # Test Temperature effect on Resistance
        self.lipo._temperature_c = 0.0
        r_cold = self.lipo.total_r0
        self.lipo._temperature_c = 25.0
        r_nom = self.lipo.total_r0
        self.assertGreater(r_cold, r_nom)

    def test_update_soc(self):
        self.lipo.soc = 1.0
        # Discharge 5A for 1 hour (capacity 5Ah)
        self.lipo.update_soc(current_a=5.0, dt=3600)
        self.assertAlmostEqual(self.lipo.soc, 0.0)
        
        # Clamp
        self.lipo.update_soc(current_a=5.0, dt=3600)
        self.assertEqual(self.lipo.soc, 0.0)


class TestPeukertSaturation(unittest.TestCase):
    def setUp(self):
        self.pc = PeukertCapacity(rated_capacity_ah=5.0, rated_current_a=1.0, peukert_exponent=1.1)

    def test_effective_capacity(self):
        # At rated current -> reduced capacity?
        # ratio = 1 -> capacity = rated
        cap1 = self.pc.get_effective_capacity(1.0)
        self.assertEqual(cap1, 5.0)
        
        # Higher current -> lower capacity
        cap2 = self.pc.get_effective_capacity(10.0)
        self.assertLess(cap2, 5.0)
        
        # Zero current
        self.assertEqual(self.pc.get_effective_capacity(0), 5.0)

    def test_runtime(self):
        # 0 amps
        self.assertEqual(self.pc.get_runtime_hours(5.0, 0), float("inf"))
        
        # Rated
        t = self.pc.get_runtime_hours(5.0, 1.0)
        # t = Cp / I^n
        # Cp = 5 * 1^1.1 = 5
        # t = 5 / 1 = 5 hours
        self.assertEqual(t, 5.0)
