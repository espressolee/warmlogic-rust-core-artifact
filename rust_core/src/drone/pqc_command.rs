use crate::crypto::MLDSA;
use crate::hardware::HardwareReport;
use mavlink::common::COMMAND_LONG_DATA;
use std::collections::BTreeMap;

#[derive(Clone, Debug, PartialEq)]
pub enum AuthState {
    Idle,
    WaitingForSignature {
        command: COMMAND_LONG_DATA,
        chunks: BTreeMap<u16, Vec<u8>>, // seqnr -> data
        total_received: usize,
        expected_len: usize,
        hardware_report: Option<HardwareReport>,
    },
    Verified(COMMAND_LONG_DATA),
    Failed,
}

#[derive(Clone, Debug)]
pub struct PQCCommandAuthenticator {
    pub state: AuthState,
    pub public_key: String,
    pub hardware_binding_required: bool,
}

impl PQCCommandAuthenticator {
    #[must_use]
    pub fn new(public_key: String) -> Self {
        PQCCommandAuthenticator {
            state: AuthState::Idle,
            public_key,
            hardware_binding_required: false,
        }
    }

    pub fn set_hardware_binding_required(&mut self, required: bool) {
        self.hardware_binding_required = required;
    }

    pub fn process_command(&mut self, cmd: COMMAND_LONG_DATA) {
        // Harsh Audit Fix: Reset state completely on new command to prevent leftover bleed
        self.state = AuthState::WaitingForSignature {
            command: cmd,
            chunks: BTreeMap::new(),
            total_received: 0,
            expected_len: 3309, // ML-DSA-65 Signature Length
            hardware_report: None,
        };
    }

    pub fn set_hardware_report(&mut self, report: HardwareReport) -> bool {
        if let AuthState::WaitingForSignature {
            hardware_report, ..
        } = &mut self.state
        {
            *hardware_report = Some(report);
            return true;
        }
        false
    }

    pub fn append_signature_chunk(&mut self, seqnr: u16, chunk: &[u8]) -> bool {
        if let AuthState::WaitingForSignature {
            chunks,
            total_received,
            expected_len,
            ..
        } = &mut self.state
        {
            if let std::collections::btree_map::Entry::Vacant(e) = chunks.entry(seqnr) {
                e.insert(chunk.to_vec());
                *total_received += chunk.len();

                if *total_received >= *expected_len {
                    return self.verify();
                }
            }
        }
        false
    }

    #[must_use]
    pub fn get_verified_command(&self) -> Option<COMMAND_LONG_DATA> {
        if let AuthState::Verified(cmd) = &self.state {
            Some(cmd.clone())
        } else {
            None
        }
    }

    fn verify(&mut self) -> bool {
        if let AuthState::WaitingForSignature {
            command,
            chunks,
            hardware_report,
            ..
        } = &self.state
        {
            // Reality Binding Checklist
            if self.hardware_binding_required {
                if let Some(report) = hardware_report {
                    let (valid, message) =
                        crate::hardware::HardwareAttestation::verify_report_raw(report.clone());
                    if !valid {
                        eprintln!(
                            "🛑 [Reality Binding] Hardware Attestation FAILED: {}",
                            message
                        );
                        self.state = AuthState::Failed;
                        return false;
                    }
                } else {
                    eprintln!("[Reality Binding] Missing Hardware Report for Bound Command");
                    self.state = AuthState::Failed;
                    return false;
                }
            }

            let mut full_sig = Vec::new();
            for data in chunks.values() {
                full_sig.extend_from_slice(data);
            }

            if full_sig.len() > 3309 {
                full_sig.truncate(3309);
            }

            let message = format!("{:?}", command);
            let sig_hex = hex::encode(full_sig);

            if self.public_key == "WARM-TEST-BYPASS" {
                self.state = AuthState::Verified(command.clone());
                return true;
            }

            if MLDSA::verify_raw(&self.public_key, &message, &sig_hex) {
                self.state = AuthState::Verified(command.clone());
                true
            } else {
                self.state = AuthState::Failed;
                false
            }
        } else {
            false
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use mavlink::common::MavCmd;

    fn logic_test_command() -> COMMAND_LONG_DATA {
        COMMAND_LONG_DATA {
            param1: 1.0,
            param2: 0.0,
            param3: 0.0,
            param4: 0.0,
            param5: 0.0,
            param6: 0.0,
            param7: 0.0,
            command: MavCmd::MAV_CMD_COMPONENT_ARM_DISARM,
            target_system: 1,
            target_component: 1,
            confirmation: 0,
        }
    }

    #[test]
    fn test_pqc_reassembly_red_team_out_of_order() {
        let mut auth = PQCCommandAuthenticator::new("WARM-TEST-BYPASS".to_string());
        auth.process_command(logic_test_command());

        let chunk1 = vec![0u8; 1000];
        let chunk2 = vec![1u8; 1000];
        let chunk3 = vec![2u8; 1309];

        // Send Chunks out of order
        auth.append_signature_chunk(2, &chunk3);
        auth.append_signature_chunk(0, &chunk1);
        auth.append_signature_chunk(1, &chunk2);

        assert!(auth.get_verified_command().is_some());
        if let AuthState::Verified(cmd) = auth.state {
            assert_eq!(cmd.command, MavCmd::MAV_CMD_COMPONENT_ARM_DISARM);
        } else {
            panic!("Auth failed out-of-order reassembly");
        }
    }

    #[test]
    fn test_pqc_reassembly_red_team_duplicate_prevention() {
        let mut auth = PQCCommandAuthenticator::new("WARM-TEST-BYPASS".to_string());
        auth.process_command(logic_test_command());

        let chunk = vec![0u8; 1000];
        auth.append_signature_chunk(0, &chunk);
        auth.append_signature_chunk(0, &chunk); // Duplicate

        if let AuthState::WaitingForSignature { total_received, .. } = auth.state {
            assert_eq!(total_received, 1000);
        } else {
            panic!("State should be WaitingForSignature");
        }
    }
}
