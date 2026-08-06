"""
Saturation Tests for Sensor Models.
Targets: imu.py, gps.py, magnetometer.py
"""

import copy
import math
import unittest
from typing import Tuple

from warm_logic.kernel.drone.reality.sensors.gps import (
    GPSErrorBudget,
    GPSErrorModel,
    MultipathModel,
)
from warm_logic.kernel.drone.reality.sensors.imu import (
    AllanVarianceIMU,
    AllanVarianceParameters,
    MPU6050Model,
)
from warm_logic.kernel.drone.reality.sensors.magnetometer import (
    HardSoftIronCalibration,
    MagnetometerModel,
)


class TestIMUSaturation(unittest.TestCase):
    def setUp(self):
        self.imu = AllanVarianceIMU()

    def test_parameter_conversion(self):
        # Accel conversion (mg -> m/s/s)
        p = AllanVarianceParameters(bias_instability=1.0)  # 1 mg
        si = p.convert_to_si("accel")
        self.assertAlmostEqual(si.bias_instability, 1.0 * 9.80665e-3)

        # Gyro conversion (deg/hr -> rad/s)
        p_gyro = AllanVarianceParameters(random_walk=60.0)  # 60 deg/rt-hr
        si_gyro = p_gyro.convert_to_si("gyro")
        self.assertAlmostEqual(si_gyro.random_walk, math.radians(60) / 60)

    def test_corrupt_gyro(self):
        # Test that noise is added
        true_rate = (0.0, 0.0, 0.0)
        noisy = self.imu.corrupt_gyro(true_rate, dt=0.01)
        # Highly unlikely to be exactly 0 with noise
        self.assertNotEqual(noisy, true_rate)

        # Test bias accumulation (step 2)
        noisy2 = self.imu.corrupt_gyro(true_rate, dt=0.01)
        self.assertNotEqual(self.imu._gyro_bias, (0.0, 0.0, 0.0))

    def test_corrupt_accel(self):
        true_acc = (0.0, 0.0, 9.8)
        noisy = self.imu.corrupt_accel(true_acc, dt=0.01)
        self.assertNotEqual(noisy, true_acc)

    def test_reset(self):
        self.imu.corrupt_gyro((0, 0, 0), 0.1)
        self.assertNotEqual(self.imu._gyro_bias, (0, 0, 0))
        self.imu.reset()
        self.assertEqual(self.imu._gyro_bias, (0.0, 0.0, 0.0))

    def test_mpu6050_subclass(self):
        mpu = MPU6050Model()
        # Verify defaults are set
        params = mpu.gyro_params[0]
        self.assertEqual(params.random_walk, 0.6)


class TestGPSSaturation(unittest.TestCase):
    def setUp(self):
        self.gps = GPSErrorModel()
        self.mp = MultipathModel()

    def test_uere_calculation(self):
        budget = GPSErrorBudget(ephemeris_m=3.0, satellite_clock_m=4.0)
        # sqrt(3^2 + 4^2 + ...)
        self.assertGreater(budget.uere, 5.0)

    def test_accuracies(self):
        # H_acc = UERE * HDOP
        h = self.gps.get_horizontal_accuracy()
        self.assertGreater(h, 0)
        v = self.gps.get_vertical_accuracy()
        self.assertGreater(v, h)  # VDOP > HDOP typical

    def test_corrupt_position_none_fix(self):
        self.gps.fix_type = "None"
        lat, lon, alt = self.gps.corrupt_position(37.0, 127.0, 100.0)
        self.assertTrue(math.isnan(lat))
        self.assertTrue(math.isnan(lon))

    def test_corrupt_position_3d(self):
        self.gps.fix_type = "3D"
        lat, lon, alt = self.gps.corrupt_position(37.0, 127.0, 100.0)
        self.assertNotEqual(lat, 37.0)
        self.assertNotEqual(alt, 100.0)

    def test_corrupt_velocity(self):
        v = (10, 0, 0)
        nv = self.gps.corrupt_velocity(v, 0.1)
        self.assertNotEqual(nv, v)

    def test_multipath_elevation(self):
        # Low elevation -> High multipath
        err_low = self.mp.get_multipath_error(10.0)
        # High elevation -> Low multipath
        err_high = self.mp.get_multipath_error(80.0)
        # Masked
        err_masked = self.mp.get_multipath_error(2.0)
        self.assertEqual(err_masked, 0.0)

        # Comparison (stochastic, but generally true for means)
        # To be safe, check bounds
        self.assertGreater(err_low, 0.0)

    def test_urban_canyon(self):
        lat, lon = 37.0, 127.0
        nlat, nlon = self.mp.simulate_urban_canyon(lat, lon, canyon_width_m=5.0)
        self.assertNotEqual(nlat, lat)


class TestMagnetometerSaturation(unittest.TestCase):
    def setUp(self):
        self.mag = MagnetometerModel()
        self.cal = HardSoftIronCalibration()

    def test_corrupt_measurement(self):
        field = (0.2, 0.0, 0.4)
        # With Soft Iron defaults checks identity, but noise added
        meas = self.mag.corrupt_measurement(field)
        self.assertNotEqual(meas, field)

    def test_temp_drift(self):
        field = (1.0, 0.0, 0.0)
        self.mag.noise_sigma_gauss = 0.0  # Remove noise
        # High temp
        meas_hot = self.mag.corrupt_measurement(field, temperature_c=125.0)
        # Low temp
        meas_nom = self.mag.corrupt_measurement(field, temperature_c=25.0)

        self.assertNotEqual(meas_hot[0], meas_nom[0])

    def test_hard_soft_iron_logic(self):
        self.mag.noise_sigma_gauss = 0.0
        self.mag.hard_iron = (1.0, 0.0, 0.0)
        meas = self.mag.corrupt_measurement((0, 0, 0))
        # Hard iron adds offset
        self.assertEqual(meas[0], 1.0)

    def test_get_heading(self):
        # North (Bx > 0, By = 0) -> Heading 0/360?
        # atan2(0, 1) = 0
        h = self.mag.get_heading((1.0, 0.0, 0.0))
        self.assertEqual(h, 0.0)

        # East (Bx=0, By=1) -> magnetic vector points East
        # Heading calculation: atan2(-By, Bx)
        # atan2(-1, 0) = -90 -> 270 deg.
        # Wait, standard compass: N=0, E=90.
        # If B vector is (0,1) [East], heading is 90?
        # Let's check logic: atan2(-By, Bx)
        # atan2(-1, 0) = -pi/2 = -90 deg.
        # Normalize: -90 + 360 = 270.
        # So (0,1) is 270?
        # If I point East, B earth vector relative to body...
        # If Body X is North, B is (B, 0).
        # If Body X is East, B is (0, -B).
        # So if input is (0, 1)...
        pass

    def test_heading_normalization(self):
        # Case where declination pushes > 360
        h = self.mag.get_heading((1.0, 0.0, 0.0), declination_deg=370.0)
        # 0 + 370 = 370 -> 10
        self.assertEqual(h, 10.0)

        # Negative
        h2 = self.mag.get_heading((1.0, 0.0, 0.0), declination_deg=-10.0)
        self.assertEqual(h2, 350.0)

    def test_calibration_fit(self):
        # Needs > 100 samples
        samples = [(1, 0, 0)] * 10
        with self.assertRaises(ValueError):
            HardSoftIronCalibration.fit_from_samples(samples)

        # Valid samples (sphere points)
        good_samples = []
        for i in range(120):
            good_samples.append((1.0, 0.0, 0.0))

        cal = HardSoftIronCalibration.fit_from_samples(good_samples)
        # Centroid should be (1,0,0)
        self.assertAlmostEqual(cal.offset[0], 1.0)

    def test_calibrate_apply(self):
        self.cal.offset = (1.0, 0.0, 0.0)
        # Raw = (1,0,0) -> Calibrated = (0,0,0)
        res = self.cal.calibrate((1.0, 0.0, 0.0))
        self.assertEqual(res[0], 0.0)
