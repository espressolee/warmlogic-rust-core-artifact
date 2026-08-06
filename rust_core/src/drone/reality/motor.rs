use core::f64::consts::PI;

pub struct MotorModel {
    pub kv: f64, // RPM/V
    pub rm: f64, // Winding resistance (Ω)
    pub io: f64, // No-load current (A)
}

impl Default for MotorModel {
    fn default() -> Self {
        Self::new()
    }
}

impl MotorModel {
    /// Create a standard T-Motor U8-type drone motor model
    #[must_use]
    pub fn new() -> Self {
        Self {
            kv: 920.0,
            rm: 0.1,
            io: 0.5,
        }
    }

    #[must_use]
    pub fn kt(&self) -> f64 {
        // Kt = 60 / (2π × Kv) = 9.549296 / Kv
        9.54929658 / self.kv
    }

    #[must_use]
    pub fn ke(&self) -> f64 {
        self.kt()
    }

    #[must_use]
    pub fn get_back_emf(&self, rpm: f64) -> f64 {
        let omega = rpm * 2.0 * PI / 60.0;
        self.ke() * omega
    }

    /// Calculate steady-state operating point given voltage and load torque.
    /// Returns (rpm, current, efficiency)
    #[must_use]
    pub fn calculate_operating_point(&self, voltage: f64, load_torque: f64) -> (f64, f64, f64) {
        // I = Load_torque / Kt + I0
        let current = load_torque / self.kt() + self.io;

        // E = V - I*Rm
        let e = voltage - current * self.rm;

        if e <= 0.0 {
            return (0.0, self.io, 0.0);
        }

        // RPM = E * Kv
        let rpm = e * self.kv;

        let power_elec = voltage * current;
        let power_mech = load_torque * (rpm * 2.0 * PI / 60.0);
        let efficiency = if power_elec > 0.0 {
            power_mech / power_elec
        } else {
            0.0
        };

        (rpm, current, efficiency)
    }
}

pub struct ESCModel {
    pub max_current_a: f64,
    pub pwm_frequency_hz: f64,
    pub dead_time_ns: f64,
    pub mosfet_rds_on: f64,
    pub min_throttle: f64,
    pub max_throttle: f64,
}

impl Default for ESCModel {
    fn default() -> Self {
        Self::new_default()
    }
}

impl ESCModel {
    #[must_use]
    pub fn new_default() -> Self {
        Self {
            max_current_a: 30.0,
            pwm_frequency_hz: 24000.0,
            dead_time_ns: 1000.0,
            mosfet_rds_on: 0.002,
            min_throttle: 0.05,
            max_throttle: 1.0,
        }
    }

    #[must_use]
    pub fn get_output_voltage(&self, throttle: f64, bus_voltage: f64) -> f64 {
        let t = throttle.clamp(0.0, 1.0);

        if t < self.min_throttle {
            return 0.0;
        }

        let duty = (t - self.min_throttle) / (self.max_throttle - self.min_throttle);
        let dead_time_loss = self.dead_time_ns * 1e-9 * self.pwm_frequency_hz * 2.0;
        let effective_duty = duty * (1.0 - dead_time_loss);

        bus_voltage * effective_duty
    }

    #[must_use]
    pub fn get_switching_losses(&self, current_a: f64) -> f64 {
        let p_conduction = current_a.powi(2) * self.mosfet_rds_on * 6.0;
        let p_switching = current_a * 0.01 * self.pwm_frequency_hz / 1000.0;
        p_conduction + p_switching
    }
}
