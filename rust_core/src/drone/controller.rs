#![cfg_attr(not(feature = "std"), no_std)]

use super::ekf::ExtendedKalmanFilter;
use super::pid::RobustPID;
use nalgebra::Vector3;

#[derive(Clone, Debug, PartialEq)]
#[non_exhaustive]
pub enum FlightMode {
    Stabilize,
    Guided,
    Land,
}

#[derive(Clone, Debug)]
pub struct PIDConfig {
    pub p: f64,
    pub i: f64,
    pub d: f64,
    pub imax: f64,
    pub out_min: f64,
    pub out_max: f64,
}

#[derive(Clone, Debug)]
pub struct ControllerConfig {
    pub roll_angle: PIDConfig,
    pub pitch_angle: PIDConfig,
    pub yaw_angle: PIDConfig,
    pub roll_rate: PIDConfig,
    pub pitch_rate: PIDConfig,
    pub yaw_rate: PIDConfig,
    pub thrust: PIDConfig,
}

impl Default for ControllerConfig {
    fn default() -> Self {
        ControllerConfig {
            roll_angle: PIDConfig {
                p: 2.0,
                i: 0.0,
                d: 0.0,
                imax: 0.01,
                out_min: -500.0,
                out_max: 500.0,
            },
            pitch_angle: PIDConfig {
                p: 2.0,
                i: 0.0,
                d: 0.0,
                imax: 0.01,
                out_min: -500.0,
                out_max: 500.0,
            },
            yaw_angle: PIDConfig {
                p: 0.0,
                i: 0.0,
                d: 0.0,
                imax: 0.01,
                out_min: -500.0,
                out_max: 500.0,
            },

            roll_rate: PIDConfig {
                p: 0.002,
                i: 0.0,
                d: 0.002,
                imax: 0.01,
                out_min: -0.3,
                out_max: 0.3,
            },
            pitch_rate: PIDConfig {
                p: 0.002,
                i: 0.0,
                d: 0.002,
                imax: 0.01,
                out_min: -0.3,
                out_max: 0.3,
            },
            yaw_rate: PIDConfig {
                p: 0.01,
                i: 0.0,
                d: 0.002,
                imax: 0.01,
                out_min: -0.3,
                out_max: 0.3,
            },

            thrust: PIDConfig {
                p: 0.25,
                i: 0.02,
                d: 0.05,
                imax: 0.01,
                out_min: -0.3,
                out_max: 0.5,
            },
        }
    }
}

#[derive(Clone, Debug)]
pub struct RustController {
    // State
    pub mode: FlightMode,
    pub armed: bool,

    // Components
    pub ekf: ExtendedKalmanFilter,

    // PIDs
    pid_roll_angle: RobustPID,
    pid_pitch_angle: RobustPID,
    pid_yaw_angle: RobustPID,

    pid_roll_rate: RobustPID,
    pid_pitch_rate: RobustPID,
    pid_yaw_rate: RobustPID,

    pub pid_thrust: RobustPID,

    // Target State
    pub target_pos: Vector3<f64>, // N, E, D (D is -Alt)
    pub target_yaw: f64,

    // Last sensor data
    pub last_gyro: Vector3<f64>,

    // Security
    pub authenticator: super::pqc_command::PQCCommandAuthenticator,

    // Phase 5: Hybrid Security
    pub security: super::security_scheduler::SecurityScheduler,
    pub async_signer: Option<super::security_scheduler::AsyncPQCSigner>,

    // Swarm
    pub swarm_manager: super::swarm::SwarmManager,
}

impl RustController {
    #[must_use]
    pub fn new(
        config: Option<ControllerConfig>,
        public_key: String,
        local_id: crate::net::kademlia::NodeId,
    ) -> Self {
        let cfg = config.unwrap_or_default();

        RustController {
            mode: FlightMode::Stabilize,
            armed: false,
            ekf: ExtendedKalmanFilter::new(0.01),

            pid_roll_angle: RobustPID::new(
                cfg.roll_angle.p,
                cfg.roll_angle.i,
                cfg.roll_angle.d,
                cfg.roll_angle.imax,
                cfg.roll_angle.out_min,
                cfg.roll_angle.out_max,
                None,
            ),
            pid_pitch_angle: RobustPID::new(
                cfg.pitch_angle.p,
                cfg.pitch_angle.i,
                cfg.pitch_angle.d,
                cfg.pitch_angle.imax,
                cfg.pitch_angle.out_min,
                cfg.pitch_angle.out_max,
                None,
            ),
            pid_yaw_angle: RobustPID::new(
                cfg.yaw_angle.p,
                cfg.yaw_angle.i,
                cfg.yaw_angle.d,
                cfg.yaw_angle.imax,
                cfg.yaw_angle.out_min,
                cfg.yaw_angle.out_max,
                None,
            ),

            pid_roll_rate: RobustPID::new(
                cfg.roll_rate.p,
                cfg.roll_rate.i,
                cfg.roll_rate.d,
                cfg.roll_rate.imax,
                cfg.roll_rate.out_min,
                cfg.roll_rate.out_max,
                None,
            ),
            pid_pitch_rate: RobustPID::new(
                cfg.pitch_rate.p,
                cfg.pitch_rate.i,
                cfg.pitch_rate.d,
                cfg.pitch_rate.imax,
                cfg.pitch_rate.out_min,
                cfg.pitch_rate.out_max,
                None,
            ),
            pid_yaw_rate: RobustPID::new(
                cfg.yaw_rate.p,
                cfg.yaw_rate.i,
                cfg.yaw_rate.d,
                cfg.yaw_rate.imax,
                cfg.yaw_rate.out_min,
                cfg.yaw_rate.out_max,
                None,
            ),

            pid_thrust: RobustPID::new(
                cfg.thrust.p,
                cfg.thrust.i,
                cfg.thrust.d,
                cfg.thrust.imax,
                cfg.thrust.out_min,
                cfg.thrust.out_max,
                None,
            ),

            target_pos: Vector3::new(0.0, 0.0, -10.0), // Default 10m Alt
            target_yaw: 0.0,
            last_gyro: Vector3::zeros(),

            authenticator: super::pqc_command::PQCCommandAuthenticator::new(public_key),

            // Phase 5: Default to AmortizedPQC (400 ticks = 1Hz PQC on 400Hz loop)
            security: super::security_scheduler::SecurityScheduler::new(
                super::security_scheduler::SecurityLevel::AmortizedPQC,
                400,
            ),
            async_signer: None, // Can be spawned later or via config

            swarm_manager: super::swarm::SwarmManager::new(local_id),
        }
    }

    pub fn update_imu(&mut self, gyro: Vector3<f64>, accel: Vector3<f64>) {
        self.last_gyro = gyro;
        self.ekf.predict(gyro);
        self.ekf.update_accel(-accel);

        // Phase 5: Amortized Security Hashing (O(1)µs on RISC-V)
        let mut data = [0u8; 48];
        data[0..8].copy_from_slice(&gyro.x.to_le_bytes());
        data[8..16].copy_from_slice(&gyro.y.to_le_bytes());
        data[16..24].copy_from_slice(&gyro.z.to_le_bytes());
        data[24..32].copy_from_slice(&accel.x.to_le_bytes());
        data[32..40].copy_from_slice(&accel.y.to_le_bytes());
        data[40..48].copy_from_slice(&accel.z.to_le_bytes());

        if self.security.tick(&data) {
            // PQC Epoch Boundary Reached (e.g. 1Hz)
            if let Some(payload) = self.security.get_signing_payload() {
                if let Some(signer) = &self.async_signer {
                    // Strategy 2: Offload to async signer core (Big Core)
                    let _ = signer.request_sign(self.security.tick_count, payload);
                }
            }
        }

        // Strategy 2: Poll for results from async signer regularly
        if let Some(signer) = &self.async_signer {
            if let Some(result) = signer.poll_result() {
                self.security.set_pqc_signature(result.signature);
            }
        }
    }

    /// Spawns the async PQC signer on a background thread (Strategy 2).
    pub fn spawn_signer(&mut self, private_key: String) {
        self.async_signer = Some(super::security_scheduler::AsyncPQCSigner::spawn(
            private_key,
        ));
    }

    pub fn handle_mavlink_msg(
        &mut self,
        node: &mut super::mavlink::MavlinkNode,
        msg: &mavlink::common::MavMessage,
    ) -> Option<Vec<u8>> {
        use super::pqc_command::AuthState;
        use mavlink::common::{MavMessage, MavResult};

        match msg {
            MavMessage::COMMAND_LONG(data) => {
                // Harsh Audit: All sensitive commands must be PQC-authenticated
                self.authenticator.process_command(data.clone());
                // Return DENIED or TEMPORARILY_REJECTED to signal auth needed
                node.encode_command_ack(data.command as u16, MavResult::MAV_RESULT_DENIED)
                    .ok()
            }
            MavMessage::ENCAPSULATED_DATA(data) => {
                // Route between PQC signatures and Swarm Sync
                if let AuthState::WaitingForSignature { .. } = self.authenticator.state {
                    if self
                        .authenticator
                        .append_signature_chunk(data.seqnr, &data.data)
                    {
                        if let AuthState::Verified(cmd) = self.authenticator.state.clone() {
                            // Single-drone PQC verified! Now check Swarm Consensus
                            let mission_hash = hex::encode(format!("{:?}", cmd));
                            self.swarm_manager.propose_mission(&mission_hash);

                            // If we already have quorum (SITL debug or fast network), execute
                            if self.swarm_manager.check_agreement() {
                                let cmd_id = cmd.command as u16;
                                self.execute_command(cmd);
                                return node
                                    .encode_command_ack(cmd_id, MavResult::MAV_RESULT_ACCEPTED)
                                    .ok();
                            } else {
                                // Wait for peers to vote
                                return node
                                    .encode_command_ack(
                                        cmd.command as u16,
                                        MavResult::MAV_RESULT_TEMPORARILY_REJECTED,
                                    )
                                    .ok();
                            }
                        }
                    }
                } else {
                    // Treat as Swarm Sync / BFT Vote
                    self.swarm_manager.handle_peer_packet(data);

                    // Periodically check if quorum was reached while waiting
                    if self.swarm_manager.check_agreement() {
                        if let AuthState::Verified(cmd) = self.authenticator.state.clone() {
                            let cmd_id = cmd.command as u16;
                            self.execute_command(cmd);
                            return node
                                .encode_command_ack(cmd_id, MavResult::MAV_RESULT_ACCEPTED)
                                .ok();
                        }
                    }
                }
                None
            }
            _ => None,
        }
    }

    fn execute_command(&mut self, data: mavlink::common::COMMAND_LONG_DATA) {
        use mavlink::common::MavCmd;
        match data.command {
            MavCmd::MAV_CMD_COMPONENT_ARM_DISARM => {
                self.armed = data.param1 == 1.0;
            }
            MavCmd::MAV_CMD_DO_SET_MODE => match data.param2 as u32 {
                0 => self.mode = FlightMode::Stabilize,
                1 => self.mode = FlightMode::Guided,
                2 => self.mode = FlightMode::Land,
                _ => {}
            },
            _ => {}
        }
    }

    pub fn get_control_output(&mut self, current_alt: f64) -> (f64, f64, f64, f64) {
        if !self.armed {
            return (0.0, 0.0, 0.0, 0.0);
        }

        let (roll_deg, pitch_deg, yaw_deg) = self.ekf.get_euler_angles();

        // 1. Altitude Control
        let target_alt = -self.target_pos.z;
        let alt_error = target_alt - current_alt;
        let thrust_offset = self.pid_thrust.update(alt_error, 0.0);
        let mut thrust_total = 0.31 + thrust_offset;
        thrust_total = thrust_total.clamp(0.0, 1.0);

        // 2. Attitude Control
        let target_roll = 0.0;
        let target_pitch = 0.0;
        let yaw_err = self.target_yaw - yaw_deg;

        let target_roll_rate = self.pid_roll_angle.update(target_roll - roll_deg, 0.0);
        let target_pitch_rate = self.pid_pitch_angle.update(target_pitch - pitch_deg, 0.0);
        let target_yaw_rate = self.pid_yaw_angle.update(yaw_err, 0.0);

        // 3. Rate Control
        let p_deg = self.last_gyro.x.to_degrees();
        let q_deg = self.last_gyro.y.to_degrees();
        let r_deg = self.last_gyro.z.to_degrees();

        let r_cmd = self.pid_roll_rate.update(target_roll_rate - p_deg, 0.0);
        let p_cmd = self.pid_pitch_rate.update(target_pitch_rate - q_deg, 0.0);
        let y_cmd = self.pid_yaw_rate.update(target_yaw_rate - r_deg, 0.0);

        // Mixer Quad-X
        let fl = thrust_total + r_cmd + p_cmd + y_cmd;
        let fr = thrust_total - r_cmd + p_cmd - y_cmd;
        let bl = thrust_total + r_cmd - p_cmd - y_cmd;
        let br = thrust_total - r_cmd - p_cmd + y_cmd;

        (
            fl.clamp(0.0, 1.0),
            fr.clamp(0.0, 1.0),
            bl.clamp(0.0, 1.0),
            br.clamp(0.0, 1.0),
        )
    }
}
