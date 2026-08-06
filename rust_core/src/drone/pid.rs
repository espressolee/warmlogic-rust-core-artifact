#![cfg_attr(not(feature = "std"), no_std)]

use super::filter::LowPassFilter;

#[derive(Clone, Debug)]
pub struct RobustPID {
    kp: f64,
    ki: f64,
    kd: f64,
    dt: f64,

    // Limits
    output_min: f64,
    output_max: f64,
    integrator_min: f64,
    integrator_max: f64,

    // State
    integrator: f64,
    prev_error: f64,
    d_filter: Option<LowPassFilter>,
}

impl RobustPID {
    #[must_use]
    pub fn new(
        kp: f64,
        ki: f64,
        kd: f64,
        dt: f64,
        output_min: f64,
        output_max: f64,
        d_filter_hz: Option<f64>,
    ) -> Self {
        let d_filter = d_filter_hz.map(|hz| LowPassFilter::new(hz, dt));
        RobustPID {
            kp,
            ki,
            kd,
            dt,
            output_min,
            output_max,
            integrator_min: -0.5, // Default from Python
            integrator_max: 0.5,  // Default from Python
            integrator: 0.0,
            prev_error: 0.0,
            d_filter,
        }
    }

    pub fn set_integrator_limits(&mut self, min: f64, max: f64) {
        self.integrator_min = min;
        self.integrator_max = max;
    }

    pub fn update(&mut self, error: f64, feedforward: f64) -> f64 {
        // P Term
        let p_term = self.kp * error;

        // I Term (Anti-windup)
        self.integrator += self.ki * error * self.dt;
        if self.integrator > self.integrator_max {
            self.integrator = self.integrator_max;
        } else if self.integrator < self.integrator_min {
            self.integrator = self.integrator_min;
        }
        let i_term = self.integrator;

        // D Term
        let mut derivative = (error - self.prev_error) / self.dt;
        if let Some(filter) = &mut self.d_filter {
            derivative = filter.update(derivative);
        }
        let d_term = self.kd * derivative;

        // Total
        let mut output = p_term + i_term + d_term + feedforward;

        // Saturation
        if output > self.output_max {
            output = self.output_max;
        } else if output < self.output_min {
            output = self.output_min;
        }

        self.prev_error = error;
        output
    }

    pub fn reset(&mut self) {
        self.integrator = 0.0;
        self.prev_error = 0.0;
        if let Some(filter) = &mut self.d_filter {
            filter.reset();
        }
    }
}
