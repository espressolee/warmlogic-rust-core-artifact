use mavlink::common::*;
use nalgebra::Vector3;
use num_traits::FromPrimitive;
use std::io::Cursor;

pub struct MavlinkNode {
    header: mavlink::MavHeader,
}

impl MavlinkNode {
    #[must_use]
    pub fn new(system_id: u8, component_id: u8) -> Self {
        MavlinkNode {
            header: mavlink::MavHeader {
                system_id,
                component_id,
                sequence: 0,
            },
        }
    }

    /// Encodes a HIL_SENSOR message into bytes.
    #[allow(clippy::too_many_arguments)]
    pub fn encode_hil_sensor(
        &mut self,
        time_usec: u64,
        accel: Vector3<f64>,
        gyro: Vector3<f64>,
        mag: Vector3<f64>,
        abs_pressure: f32,
        diff_pressure: f32,
        pressure_alt: f32,
        temperature: f32,
    ) -> anyhow::Result<Vec<u8>> {
        let msg = MavMessage::HIL_SENSOR(HIL_SENSOR_DATA {
            time_usec,
            xacc: accel.x as f32,
            yacc: accel.y as f32,
            zacc: accel.z as f32,
            xgyro: gyro.x as f32,
            ygyro: gyro.y as f32,
            zgyro: gyro.z as f32,
            xmag: mag.x as f32,
            ymag: mag.y as f32,
            zmag: mag.z as f32,
            abs_pressure,
            diff_pressure,
            pressure_alt,
            temperature,
            fields_updated: HilSensorUpdatedFlags::all(),
        });

        let mut buf = Vec::new();
        mavlink::write_v2_msg(&mut buf, self.header, &msg)
            .map_err(|e| anyhow::anyhow!("MAVLink encode failed: {:?}", e))?;

        self.header.sequence = self.header.sequence.wrapping_add(1);
        Ok(buf)
    }

    /// Decodes a MAVLink packet from bytes.
    pub fn decode(&self, data: &[u8]) -> anyhow::Result<MavMessage> {
        let cursor = Cursor::new(data);
        let mut reader = mavlink::peek_reader::PeekReader::new(cursor);
        match mavlink::read_v2_msg::<MavMessage, _>(&mut reader) {
            Ok((_header, msg)) => Ok(msg),
            Err(e) => Err(anyhow::anyhow!("MAVLink decode failed: {:?}", e)),
        }
    }

    /// Encodes a HEARTBEAT message.
    pub fn encode_heartbeat(&mut self) -> anyhow::Result<Vec<u8>> {
        let msg = MavMessage::HEARTBEAT(HEARTBEAT_DATA {
            custom_mode: 0,
            mavtype: mavlink::common::MavType::MAV_TYPE_ONBOARD_CONTROLLER,
            autopilot: mavlink::common::MavAutopilot::MAV_AUTOPILOT_INVALID,
            base_mode: mavlink::common::MavModeFlag::empty(),
            system_status: mavlink::common::MavState::MAV_STATE_ACTIVE,
            mavlink_version: 0x03,
        });

        let mut buf = Vec::new();
        mavlink::write_v2_msg(&mut buf, self.header, &msg)
            .map_err(|e| anyhow::anyhow!("HEARTBEAT encode failed: {:?}", e))?;

        self.header.sequence = self.header.sequence.wrapping_add(1);
        Ok(buf)
    }

    /// Encodes HIL_ACTUATOR_CONTROLS for the simulator.
    pub fn encode_hil_actuator_controls(
        &mut self,
        controls: [f32; 16],
        mode: u8,
        flags: u64,
    ) -> anyhow::Result<Vec<u8>> {
        let msg = MavMessage::HIL_ACTUATOR_CONTROLS(HIL_ACTUATOR_CONTROLS_DATA {
            time_usec: 0,
            controls,
            mode: MavModeFlag::from_bits_truncate(mode),
            flags: HilActuatorControlsFlags::from_bits_truncate(flags),
        });

        let mut buf = Vec::new();
        mavlink::write_v2_msg(&mut buf, self.header, &msg)
            .map_err(|e| anyhow::anyhow!("HIL_ACTUATOR_CONTROLS encode failed: {:?}", e))?;

        self.header.sequence = self.header.sequence.wrapping_add(1);
        Ok(buf)
    }

    /// Encodes a COMMAND_ACK message.
    pub fn encode_command_ack(
        &mut self,
        command: u16,
        result: mavlink::common::MavResult,
    ) -> anyhow::Result<Vec<u8>> {
        let msg = MavMessage::COMMAND_ACK(COMMAND_ACK_DATA {
            command: MavCmd::from_u16(command).unwrap_or(MavCmd::MAV_CMD_NAV_LAND),
            result,
        });

        let mut buf = Vec::new();
        mavlink::write_v2_msg(&mut buf, self.header, &msg)
            .map_err(|e| anyhow::anyhow!("COMMAND_ACK encode failed: {:?}", e))?;

        self.header.sequence = self.header.sequence.wrapping_add(1);
        Ok(buf)
    }
}

#[must_use]
pub fn extract_command(msg: &MavMessage) -> Option<&COMMAND_LONG_DATA> {
    if let MavMessage::COMMAND_LONG(data) = msg {
        Some(data)
    } else {
        None
    }
}
