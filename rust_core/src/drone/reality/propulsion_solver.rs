use super::aerodynamics::BemtEngine;
use super::atmosphere::USStandardAtmosphere1976;
use super::motor::{ESCModel, MotorModel};

pub struct PropulsionSolver {
    pub motor: MotorModel,
    pub esc: ESCModel,
    pub aero: BemtEngine,
    pub atm: USStandardAtmosphere1976,
}

impl PropulsionSolver {
    #[must_use]
    pub fn default() -> Self {
        Self {
            motor: MotorModel::default(),
            esc: ESCModel::default(),
            aero: BemtEngine::default(),
            atm: USStandardAtmosphere1976::default(),
        }
    }

    /// Calculate equilibrium thrust for a given throttle, altitude, and axial velocity.
    /// Uses bisection to find the steady-state RPM where Motor Torque == Aero Torque.
    #[must_use]
    pub fn solve_thrust(
        &self,
        throttle: f64,
        altitude: f64,
        v_axial: f64,
        bus_voltage: f64,
    ) -> f64 {
        let voltage = self.esc.get_output_voltage(throttle, bus_voltage);
        if voltage <= 1.0 {
            return 0.0;
        }

        let rho = self.atm.get_state(altitude).density_kg_m3;

        // Bisection to find equilibrium RPM
        // f(rpm) = MotorTorque(rpm, voltage) - AeroTorque(rpm, rho, v_axial)
        // Equilibrium is at f(rpm) == 0

        let mut rpm_low = 0.0;
        let mut rpm_high = voltage * self.motor.kv; // Theoretical max no-load RPM

        for _ in 0..15 {
            let rpm_mid = (rpm_low + rpm_high) / 2.0;

            // 1. Aerodynamic Torque at this RPM
            let t_aero = self.aero.calculate_torque(rpm_mid, rho, v_axial);

            // 2. Motor torque available at this RPM:
            // V = E + I*Rm -> I = (V - E)/Rm
            // Torque_motor = Kt * (I - I0)
            let e = self.motor.get_back_emf(rpm_mid);
            let current = ((voltage - e) / self.motor.rm).max(0.0);
            let t_motor = (self.motor.kt() * (current - self.motor.io)).max(0.0);

            if t_motor > t_aero {
                rpm_low = rpm_mid;
            } else {
                rpm_high = rpm_mid;
            }
        }

        let final_rpm = (rpm_low + rpm_high) / 2.0;
        self.aero.calculate_thrust(final_rpm, rho, v_axial)
    }
}
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_propulsion_solver_steady_state() {
        let solver = PropulsionSolver::default();
        // 50% throttle, 0m altitude, 0 m/s axial velocity
        let thrust = solver.solve_thrust(0.5, 0.0, 0.0, 22.2);
        assert!(thrust > 0.0);
        assert!(thrust < 20.0); // Reasonable upper bound for default motor/aero
    }

    #[test]
    fn test_propulsion_solver_zero_voltage() {
        let solver = PropulsionSolver::default();
        let thrust = solver.solve_thrust(0.0, 0.0, 0.0, 22.2);
        assert_eq!(thrust, 0.0);
    }

    #[test]
    fn test_propulsion_solver_high_altitude() {
        let solver = PropulsionSolver::default();
        // At 10,000m, density is low, thrust should be lower than at 0m
        let thrust0 = solver.solve_thrust(0.8, 0.0, 0.0, 22.2);
        let thrust10k = solver.solve_thrust(0.8, 10000.0, 0.0, 22.2);
        assert!(thrust10k < thrust0);
    }
}
