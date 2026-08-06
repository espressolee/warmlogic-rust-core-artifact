/// Physical Constants with Academic Sources.
/// Mirror of constants.py for the Sovereignty substrate.
pub struct PhysicalConstants;

impl PhysicalConstants {
    // ===== Earth & Atmosphere [WGS84, US Std Atm 1976] =====
    pub const GRAVITY_STANDARD: f64 = 9.80665;
    pub const SEA_LEVEL_PRESSURE: f64 = 101325.0;
    pub const SEA_LEVEL_TEMPERATURE: f64 = 288.15;

    pub const AIR_MOLAR_MASS: f64 = 0.0289644;
    pub const AIR_GAS_CONSTANT: f64 = 287.058;
    pub const SPECIFIC_HEAT_RATIO: f64 = 1.4;
    pub const UNIVERSAL_GAS_CONSTANT: f64 = 8.31447;

    // Sutherland's Law constants
    pub const SUTHERLAND_REFERENCE_VISCOSITY: f64 = 1.716e-5;
    pub const SUTHERLAND_REFERENCE_TEMP: f64 = 273.15;
    pub const SUTHERLAND_CONSTANT: f64 = 110.4;
}
