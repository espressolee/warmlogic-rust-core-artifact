use std::f64::consts::PI;

/// Blade geometry for multirotor propellers.
#[derive(Debug, Clone, Copy)]
pub struct BladeGeometry {
    pub radius_m: f64,
    pub chord_m: f64,
    pub num_blades: usize,
    pub twist_deg: f64,
    pub root_cutout: f64,
}

impl Default for BladeGeometry {
    fn default() -> Self {
        Self {
            radius_m: 0.127, // Matches bemt.py baseline (which treats 5-inch as radius)
            chord_m: 0.015,
            num_blades: 2,
            twist_deg: 15.0,
            root_cutout: 0.1,
        }
    }
}

impl BladeGeometry {
    #[must_use]
    pub fn disk_area_m2(&self) -> f64 {
        PI * self.radius_m.powi(2)
    }

    #[must_use]
    pub fn solidity(&self) -> f64 {
        (self.num_blades as f64 * self.chord_m) / (PI * self.radius_m)
    }
}

/// 2D airfoil aerodynamic characteristics.
#[derive(Debug, Clone, Copy)]
pub struct AirfoilData {
    pub cl_alpha: f64,
    pub cl_max: f64,
    pub cd_0: f64,
    pub cd_stall: f64,
    pub alpha_stall_deg: f64,
}

impl Default for AirfoilData {
    fn default() -> Self {
        Self {
            cl_alpha: 5.73,
            cl_max: 1.0,
            cd_0: 0.008,
            cd_stall: 0.3,
            alpha_stall_deg: 12.0,
        }
    }
}

impl AirfoilData {
    #[must_use]
    pub fn get_cl(&self, alpha_deg: f64) -> f64 {
        let alpha_rad = alpha_deg.to_radians();
        if alpha_deg.abs() < self.alpha_stall_deg {
            self.cl_alpha * alpha_rad
        } else {
            let sign = if alpha_deg > 0.0 { 1.0 } else { -1.0 };
            sign * 0.7 * self.cl_max
        }
    }

    #[must_use]
    pub fn get_cd(&self, alpha_deg: f64) -> f64 {
        if alpha_deg.abs() < self.alpha_stall_deg {
            let cl = self.get_cl(alpha_deg);
            self.cd_0 + cl.powi(2) / (PI * 6.0 * 0.85)
        } else {
            self.cd_stall
        }
    }
}

/// Blade Element Momentum Theory (BEMT) engine.
#[derive(Debug, Clone)]
pub struct BemtEngine {
    pub blade: BladeGeometry,
    pub airfoil: AirfoilData,
    pub num_elements: usize,
}

impl Default for BemtEngine {
    fn default() -> Self {
        Self {
            blade: BladeGeometry::default(),
            airfoil: AirfoilData::default(),
            num_elements: 20,
        }
    }
}

impl BemtEngine {
    #[must_use]
    pub fn new(blade: BladeGeometry, airfoil: AirfoilData, num_elements: usize) -> Self {
        Self {
            blade,
            airfoil,
            num_elements,
        }
    }

    /// Calculate thrust coefficient CT at a given operating point.
    #[must_use]
    pub fn calculate_ct(&self, rpm: f64, _rho: f64, axial_velocity: f64) -> f64 {
        let omega = rpm * 2.0 * PI / 60.0;
        let tip_speed = omega * self.blade.radius_m;

        if tip_speed < 1.0 {
            return 0.0;
        }

        let lambda_c = axial_velocity / tip_speed;
        let sigma = self.blade.solidity();
        let a = self.airfoil.cl_alpha;
        let theta_0 = (self.blade.twist_deg / 2.0).to_radians();

        // Iterative solution for induced inflow radio (lambda_i)
        let mut lambda_i = 0.0;
        for _ in 0..10 {
            let ct_est = sigma * a * (theta_0 / 3.0 - (lambda_c + lambda_i) / 2.0) / 2.0;
            let flow_factor = (lambda_c.powi(2) + ct_est.abs()).sqrt();
            if flow_factor > 1e-6 {
                lambda_i = ct_est.abs() / (2.0 * flow_factor);
            } else {
                lambda_i = 0.0;
            }
        }

        sigma * a * (theta_0 / 3.0 - (lambda_c + lambda_i) / 2.0) / 2.0
    }

    /// Calculate total rotor thrust (N) using a Multi-Element Vectorized Solver.
    /// This replaces the simple CT approximation with a high-fidelity BEMT sweep.
    #[must_use]
    pub fn calculate_thrust(&self, rpm: f64, rho: f64, axial_velocity: f64) -> f64 {
        let omega = rpm * 2.0 * PI / 60.0;
        if omega < 1.0 {
            return 0.0;
        }

        let r_root = self.blade.root_cutout * self.blade.radius_m;
        let r_tip = self.blade.radius_m;
        let dr = (r_tip - r_root) / self.num_elements as f64;

        let mut total_thrust = 0.0;

        // This loop is a prime candidate for RVV acceleration.
        // We calculate lift/drag for N elements in parallel.
        for i in 0..self.num_elements {
            let r = r_root + (i as f64 + 0.5) * dr;
            let v_theta = omega * r;
            let v_resultant = (v_theta.powi(2) + axial_velocity.powi(2)).sqrt();

            // local inflow angle
            let phi = axial_velocity.atan2(v_theta);
            let theta = (self.blade.twist_deg * (1.0 - r / r_tip)).to_radians();
            let alpha_deg = (theta - phi).to_degrees();

            let cl = self.airfoil.get_cl(alpha_deg);

            // dL = 0.5 * rho * V^2 * c * dr * num_blades
            let d_thrust = 0.5
                * rho
                * v_resultant.powi(2)
                * self.blade.chord_m
                * dr
                * self.blade.num_blades as f64
                * cl
                * phi.cos();
            total_thrust += d_thrust;
        }

        total_thrust
    }

    /// Calculate rotor power (W) using Multi-Element Vectorized Solver.
    #[must_use]
    pub fn calculate_power(&self, rpm: f64, rho: f64, axial_velocity: f64) -> f64 {
        let omega = rpm * 2.0 * PI / 60.0;
        if omega < 1.0 {
            return 0.0;
        }

        let r_root = self.blade.root_cutout * self.blade.radius_m;
        let r_tip = self.blade.radius_m;
        let dr = (r_tip - r_root) / self.num_elements as f64;

        let mut total_power = 0.0;

        for i in 0..self.num_elements {
            let r = r_root + (i as f64 + 0.5) * dr;
            let v_theta = omega * r;
            let v_resultant = (v_theta.powi(2) + axial_velocity.powi(2)).sqrt();
            let phi = axial_velocity.atan2(v_theta);
            let theta = (self.blade.twist_deg * (1.0 - r / r_tip)).to_radians();
            let alpha_deg = (theta - phi).to_degrees();

            let cl = self.airfoil.get_cl(alpha_deg);
            let cd = self.airfoil.get_cd(alpha_deg);

            // dD = 0.5 * rho * V^2 * c * dr * num_blades * cd
            let d_drag = 0.5
                * rho
                * v_resultant.powi(2)
                * self.blade.chord_m
                * dr
                * self.blade.num_blades as f64
                * cd;
            let d_torque = d_drag * r * phi.cos()
                + (0.5
                    * rho
                    * v_resultant.powi(2)
                    * self.blade.chord_m
                    * dr
                    * self.blade.num_blades as f64
                    * cl)
                    * r
                    * phi.sin();
            total_power += d_torque * omega;
        }

        total_power
    }

    /// Calculate rotor torque (N*m).
    #[must_use]
    pub fn calculate_torque(&self, rpm: f64, rho: f64, axial_velocity: f64) -> f64 {
        let omega = rpm * 2.0 * PI / 60.0;
        if omega < 1.0 {
            return 0.0;
        }
        self.calculate_power(rpm, rho, axial_velocity) / omega
    }
}
