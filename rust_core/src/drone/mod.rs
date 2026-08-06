// Modules requiring mavlink feature (includes nalgebra)
#[cfg(feature = "mavlink")]
pub mod controller;
#[cfg(feature = "mavlink")]
pub mod ekf;
#[cfg(feature = "mavlink")]
pub mod filter;
#[cfg(feature = "mavlink")]
pub mod mavlink;
#[cfg(feature = "mavlink")]
pub mod pid;
#[cfg(feature = "mavlink")]
pub mod pqc_command;
#[cfg(feature = "mavlink")]
pub mod swarm;

// Security scheduler is always available (no external deps)
pub mod security_scheduler;

// Reality simulation (Physics/Aerodynamics)
pub mod reality;
