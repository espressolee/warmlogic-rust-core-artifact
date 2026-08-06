use super::constants::PhysicalConstants as C;

#[derive(Debug, Clone, Copy)]
pub struct AtmosphericState {
    pub altitude_m: f64,
    pub temperature_k: f64,
    pub pressure_pa: f64,
    pub density_kg_m3: f64,
    pub speed_of_sound_m_s: f64,
}

pub struct USStandardAtmosphere1976 {
    base_pressures: [f64; 7],
}

impl USStandardAtmosphere1976 {
    const LAYERS: [(f64, f64, f64); 7] = [
        (0.0, 288.15, -0.0065),     // Troposphere
        (11000.0, 216.65, 0.0),     // Tropopause
        (20000.0, 216.65, 0.001),   // Stratosphere 1
        (32000.0, 228.65, 0.0028),  // Stratosphere 2
        (47000.0, 270.65, 0.0),     // Stratopause
        (51000.0, 270.65, -0.0028), // Mesosphere 1
        (71000.0, 214.65, -0.002),  // Mesosphere 2
    ];

    #[must_use]
    pub fn new() -> Self {
        let mut base_pressures = [0.0; 7];
        base_pressures[0] = C::SEA_LEVEL_PRESSURE;

        let g = C::GRAVITY_STANDARD;
        let m = C::AIR_MOLAR_MASS;
        let r = C::UNIVERSAL_GAS_CONSTANT;

        for i in 0..6 {
            let (h_b, t_b, l) = Self::LAYERS[i];
            let h_next = Self::LAYERS[i + 1].0;
            let dh = h_next - h_b;
            let p_b = base_pressures[i];

            if l.abs() < 1e-10 {
                // Isothermal
                base_pressures[i + 1] = p_b * (-g * m * dh / (r * t_b)).exp();
            } else {
                // Gradient
                let t_next = t_b + l * dh;
                base_pressures[i + 1] = p_b * (t_next / t_b).powf(-g * m / (r * l));
            }
        }

        Self { base_pressures }
    }

    #[must_use]
    pub fn get_layer_index(&self, altitude_m: f64) -> usize {
        for i in (0..Self::LAYERS.len()).rev() {
            if altitude_m >= Self::LAYERS[i].0 {
                return i;
            }
        }
        0
    }

    #[must_use]
    pub fn get_state(&self, altitude_m: f64) -> AtmosphericState {
        let alt = altitude_m.clamp(0.0, 86000.0);
        let i = self.get_layer_index(alt);
        let (h_b, t_b, l) = Self::LAYERS[i];
        let p_b = self.base_pressures[i];

        let dh = alt - h_b;
        let temp = t_b + l * dh;

        let g = C::GRAVITY_STANDARD;
        let m = C::AIR_MOLAR_MASS;
        let r = C::UNIVERSAL_GAS_CONSTANT;

        let pressure = if l.abs() < 1e-10 {
            p_b * (-g * m * dh / (r * t_b)).exp()
        } else {
            p_b * (temp / t_b).powf(-g * m / (r * l))
        };

        let density = pressure / (C::AIR_GAS_CONSTANT * temp);
        let speed_of_sound = (C::SPECIFIC_HEAT_RATIO * C::AIR_GAS_CONSTANT * temp).sqrt();

        AtmosphericState {
            altitude_m: alt,
            temperature_k: temp,
            pressure_pa: pressure,
            density_kg_m3: density,
            speed_of_sound_m_s: speed_of_sound,
        }
    }

    #[must_use]
    pub fn get_dynamic_viscosity(&self, altitude_m: f64) -> f64 {
        let temp = self.get_state(altitude_m).temperature_k;
        let t_ref = C::SUTHERLAND_REFERENCE_TEMP;
        let mu_ref = C::SUTHERLAND_REFERENCE_VISCOSITY;
        let s = C::SUTHERLAND_CONSTANT;

        mu_ref * (temp / t_ref).powf(1.5) * (t_ref + s) / (temp + s)
    }

    #[must_use]
    pub fn get_kinematic_viscosity(&self, altitude_m: f64) -> f64 {
        let state = self.get_state(altitude_m);
        self.get_dynamic_viscosity(altitude_m) / state.density_kg_m3
    }
}

impl Default for USStandardAtmosphere1976 {
    fn default() -> Self {
        Self::new()
    }
}
