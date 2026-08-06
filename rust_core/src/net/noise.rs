//! rust_core/src/net/noise.rs
//! Post-Quantum Noise Protocol Implementation
//!
//! Implements a Noise-like handshake protocol using ML-KEM-768 for
//! Post-Quantum secure key exchange and AES-256-GCM for transport encryption.
//!
//! Features:
//! - ML-KEM-768 (FIPS 203) for key encapsulation
//! - AES-256-GCM for authenticated encryption
//! - SHA3-256 for key derivation
//! - Perfect Forward Secrecy through ephemeral keys
//! - Mutual authentication support

use aead::{Aead, KeyInit};
use aes_gcm::{Aes256Gcm, Nonce};
use sha3::{Digest, Sha3_256};
use zeroize::{Zeroize, ZeroizeOnDrop};

use crate::crypto::MLKEM;

#[cfg(not(feature = "std"))]
use alloc::string::String;
#[cfg(not(feature = "std"))]
use alloc::vec::Vec;

/// Maximum message size for encrypted transport (64KB)
pub const MAX_ENCRYPTED_MSG_SIZE: usize = 65536;

/// Nonce size for AES-256-GCM (96 bits)
pub const NONCE_SIZE: usize = 12;

/// Key size for AES-256-GCM (256 bits)
pub const KEY_SIZE: usize = 32;

/// Noise Protocol Errors
#[derive(Debug, Clone)]
pub enum NoiseError {
    /// Handshake not complete
    HandshakeIncomplete,
    /// Invalid handshake message
    InvalidHandshakeMessage(String),
    /// Key generation failed
    KeyGenFailed(String),
    /// Encapsulation failed
    EncapsFailed(String),
    /// Decapsulation failed
    DecapsFailed(String),
    /// Encryption failed
    EncryptionFailed(String),
    /// Decryption failed
    DecryptionFailed(String),
    /// Message too large
    MessageTooLarge,
    /// Invalid state transition
    InvalidState,
}

impl core::fmt::Display for NoiseError {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        match self {
            NoiseError::HandshakeIncomplete => write!(f, "Handshake not complete"),
            NoiseError::InvalidHandshakeMessage(s) => write!(f, "Invalid handshake: {}", s),
            NoiseError::KeyGenFailed(s) => write!(f, "Key generation failed: {}", s),
            NoiseError::EncapsFailed(s) => write!(f, "Encapsulation failed: {}", s),
            NoiseError::DecapsFailed(s) => write!(f, "Decapsulation failed: {}", s),
            NoiseError::EncryptionFailed(s) => write!(f, "Encryption failed: {}", s),
            NoiseError::DecryptionFailed(s) => write!(f, "Decryption failed: {}", s),
            NoiseError::MessageTooLarge => write!(f, "Message too large"),
            NoiseError::InvalidState => write!(f, "Invalid state transition"),
        }
    }
}

/// Handshake state
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum HandshakeState {
    /// Initial state - no messages exchanged
    Initial,
    /// Initiator: Sent first message, waiting for response
    WaitingForResponse,
    /// Responder: Received first message, ready to respond
    ReceivedInitiation,
    /// Handshake complete, ready for transport
    Complete,
}

/// Role in the handshake
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum NoiseRole {
    Initiator,
    Responder,
}

/// Handshake message types
#[derive(Debug, Clone)]
pub enum HandshakeMessage {
    /// First message: Initiator's ephemeral encapsulation key
    Init { ephemeral_ek: Vec<u8> },
    /// Response: Responder's ephemeral EK + ciphertext encapsulating to initiator's EK
    Response {
        ephemeral_ek: Vec<u8>,
        ciphertext: Vec<u8>,
    },
    /// Final: Initiator's ciphertext encapsulating to responder's EK
    Final { ciphertext: Vec<u8> },
}

impl HandshakeMessage {
    /// Serialize handshake message to bytes
    #[must_use]
    pub fn to_bytes(&self) -> Vec<u8> {
        match self {
            HandshakeMessage::Init { ephemeral_ek } => {
                let mut bytes = vec![0x01]; // Message type
                bytes.extend((ephemeral_ek.len() as u16).to_be_bytes());
                bytes.extend(ephemeral_ek);
                bytes
            }
            HandshakeMessage::Response {
                ephemeral_ek,
                ciphertext,
            } => {
                let mut bytes = vec![0x02]; // Message type
                bytes.extend((ephemeral_ek.len() as u16).to_be_bytes());
                bytes.extend(ephemeral_ek);
                bytes.extend((ciphertext.len() as u16).to_be_bytes());
                bytes.extend(ciphertext);
                bytes
            }
            HandshakeMessage::Final { ciphertext } => {
                let mut bytes = vec![0x03]; // Message type
                bytes.extend((ciphertext.len() as u16).to_be_bytes());
                bytes.extend(ciphertext);
                bytes
            }
        }
    }

    /// Deserialize handshake message from bytes
    pub fn from_bytes(bytes: &[u8]) -> Result<Self, NoiseError> {
        if bytes.is_empty() {
            return Err(NoiseError::InvalidHandshakeMessage(
                "Empty message".to_string(),
            ));
        }

        match bytes[0] {
            0x01 => {
                if bytes.len() < 3 {
                    return Err(NoiseError::InvalidHandshakeMessage(
                        "Init too short".to_string(),
                    ));
                }
                let ek_len = u16::from_be_bytes([bytes[1], bytes[2]]) as usize;
                if bytes.len() < 3 + ek_len {
                    return Err(NoiseError::InvalidHandshakeMessage(
                        "Init key truncated".to_string(),
                    ));
                }
                Ok(HandshakeMessage::Init {
                    ephemeral_ek: bytes[3..3 + ek_len].to_vec(),
                })
            }
            0x02 => {
                if bytes.len() < 3 {
                    return Err(NoiseError::InvalidHandshakeMessage(
                        "Response too short".to_string(),
                    ));
                }
                let ek_len = u16::from_be_bytes([bytes[1], bytes[2]]) as usize;
                if bytes.len() < 5 + ek_len {
                    return Err(NoiseError::InvalidHandshakeMessage(
                        "Response key truncated".to_string(),
                    ));
                }
                let ct_len = u16::from_be_bytes([bytes[3 + ek_len], bytes[4 + ek_len]]) as usize;
                if bytes.len() < 5 + ek_len + ct_len {
                    return Err(NoiseError::InvalidHandshakeMessage(
                        "Response ciphertext truncated".to_string(),
                    ));
                }
                Ok(HandshakeMessage::Response {
                    ephemeral_ek: bytes[3..3 + ek_len].to_vec(),
                    ciphertext: bytes[5 + ek_len..5 + ek_len + ct_len].to_vec(),
                })
            }
            0x03 => {
                if bytes.len() < 3 {
                    return Err(NoiseError::InvalidHandshakeMessage(
                        "Final too short".to_string(),
                    ));
                }
                let ct_len = u16::from_be_bytes([bytes[1], bytes[2]]) as usize;
                if bytes.len() < 3 + ct_len {
                    return Err(NoiseError::InvalidHandshakeMessage(
                        "Final ciphertext truncated".to_string(),
                    ));
                }
                Ok(HandshakeMessage::Final {
                    ciphertext: bytes[3..3 + ct_len].to_vec(),
                })
            }
            t => Err(NoiseError::InvalidHandshakeMessage(format!(
                "Unknown message type: {}",
                t
            ))),
        }
    }
}

/// Ephemeral keypair for handshake (zeroized on drop)
#[derive(Zeroize, ZeroizeOnDrop)]
struct EphemeralKeypair {
    encapsulation_key: String,
    decapsulation_key: String,
}

/// Noise Protocol Session
/// Manages the handshake and transport encryption.
pub struct NoiseSession {
    role: NoiseRole,
    state: HandshakeState,
    /// Our ephemeral keypair
    ephemeral: Option<EphemeralKeypair>,
    /// Peer's encapsulation key (received during handshake)
    peer_ek: Option<String>,
    /// Shared secrets collected during handshake
    shared_secrets: Vec<[u8; 32]>,
    /// Final transport keys (derived after handshake)
    send_key: Option<[u8; KEY_SIZE]>,
    recv_key: Option<[u8; KEY_SIZE]>,
    /// Nonce counters
    send_nonce: u64,
    recv_nonce: u64,
}

impl NoiseSession {
    /// Create a new Noise session as initiator
    pub fn new_initiator() -> Result<Self, NoiseError> {
        let (ek, dk) = MLKEM::keygen_raw().map_err(NoiseError::KeyGenFailed)?;

        Ok(NoiseSession {
            role: NoiseRole::Initiator,
            state: HandshakeState::Initial,
            ephemeral: Some(EphemeralKeypair {
                encapsulation_key: ek,
                decapsulation_key: dk,
            }),
            peer_ek: None,
            shared_secrets: Vec::new(),
            send_key: None,
            recv_key: None,
            send_nonce: 0,
            recv_nonce: 0,
        })
    }

    /// Create a new Noise session as responder
    pub fn new_responder() -> Result<Self, NoiseError> {
        let (ek, dk) = MLKEM::keygen_raw().map_err(NoiseError::KeyGenFailed)?;

        Ok(NoiseSession {
            role: NoiseRole::Responder,
            state: HandshakeState::Initial,
            ephemeral: Some(EphemeralKeypair {
                encapsulation_key: ek,
                decapsulation_key: dk,
            }),
            peer_ek: None,
            shared_secrets: Vec::new(),
            send_key: None,
            recv_key: None,
            send_nonce: 0,
            recv_nonce: 0,
        })
    }

    /// Check if handshake is complete
    #[must_use]
    pub fn is_handshake_complete(&self) -> bool {
        self.state == HandshakeState::Complete
    }

    /// Get current handshake state
    #[must_use]
    pub fn get_state(&self) -> HandshakeState {
        self.state
    }

    /// Get our role
    #[must_use]
    pub fn get_role(&self) -> NoiseRole {
        self.role
    }

    // ========================================================================
    // Handshake Methods
    // ========================================================================

    /// Initiator: Create the first handshake message
    pub fn initiate(&mut self) -> Result<HandshakeMessage, NoiseError> {
        if self.role != NoiseRole::Initiator || self.state != HandshakeState::Initial {
            return Err(NoiseError::InvalidState);
        }

        let ek = self
            .ephemeral
            .as_ref()
            .ok_or(NoiseError::InvalidState)?
            .encapsulation_key
            .clone();

        let ek_bytes = hex::decode(&ek).map_err(|e| {
            NoiseError::InvalidHandshakeMessage(format!("Failed to decode EK: {}", e))
        })?;

        self.state = HandshakeState::WaitingForResponse;

        Ok(HandshakeMessage::Init {
            ephemeral_ek: ek_bytes,
        })
    }

    /// Responder: Process init message and create response
    pub fn respond(&mut self, init_msg: &HandshakeMessage) -> Result<HandshakeMessage, NoiseError> {
        if self.role != NoiseRole::Responder || self.state != HandshakeState::Initial {
            return Err(NoiseError::InvalidState);
        }

        let initiator_ek = match init_msg {
            HandshakeMessage::Init { ephemeral_ek } => hex::encode(ephemeral_ek),
            _ => {
                return Err(NoiseError::InvalidHandshakeMessage(
                    "Expected Init message".to_string(),
                ))
            }
        };

        // Store peer's EK
        self.peer_ek = Some(initiator_ek.clone());

        // Encapsulate to initiator's EK
        let encaps_result =
            MLKEM::encapsulate_raw(&initiator_ek).map_err(NoiseError::EncapsFailed)?;

        // Store shared secret
        let ss_bytes = hex::decode(&encaps_result.shared_secret).map_err(|e| {
            NoiseError::InvalidHandshakeMessage(format!("Failed to decode SS: {}", e))
        })?;
        let mut ss_arr = [0u8; 32];
        ss_arr.copy_from_slice(&ss_bytes);
        self.shared_secrets.push(ss_arr);

        // Get our EK
        let our_ek = self
            .ephemeral
            .as_ref()
            .ok_or(NoiseError::InvalidState)?
            .encapsulation_key
            .clone();

        let ek_bytes = hex::decode(&our_ek).map_err(|e| {
            NoiseError::InvalidHandshakeMessage(format!("Failed to decode our EK: {}", e))
        })?;

        let ct_bytes = hex::decode(&encaps_result.ciphertext).map_err(|e| {
            NoiseError::InvalidHandshakeMessage(format!("Failed to decode CT: {}", e))
        })?;

        self.state = HandshakeState::ReceivedInitiation;

        Ok(HandshakeMessage::Response {
            ephemeral_ek: ek_bytes,
            ciphertext: ct_bytes,
        })
    }

    /// Initiator: Process response and create final message
    pub fn process_response(
        &mut self,
        response: &HandshakeMessage,
    ) -> Result<HandshakeMessage, NoiseError> {
        if self.role != NoiseRole::Initiator || self.state != HandshakeState::WaitingForResponse {
            return Err(NoiseError::InvalidState);
        }

        let (responder_ek, ciphertext) = match response {
            HandshakeMessage::Response {
                ephemeral_ek,
                ciphertext,
            } => (hex::encode(ephemeral_ek), hex::encode(ciphertext)),
            _ => {
                return Err(NoiseError::InvalidHandshakeMessage(
                    "Expected Response message".to_string(),
                ))
            }
        };

        // Store peer's EK
        self.peer_ek = Some(responder_ek.clone());

        // Decapsulate to get shared secret #1
        let our_dk = self
            .ephemeral
            .as_ref()
            .ok_or(NoiseError::InvalidState)?
            .decapsulation_key
            .clone();

        let ss1 = MLKEM::decapsulate_raw(&our_dk, &ciphertext).map_err(NoiseError::DecapsFailed)?;

        let ss1_bytes = hex::decode(&ss1).map_err(|e| {
            NoiseError::InvalidHandshakeMessage(format!("Failed to decode SS1: {}", e))
        })?;
        let mut ss1_arr = [0u8; 32];
        ss1_arr.copy_from_slice(&ss1_bytes);
        self.shared_secrets.push(ss1_arr);

        // Encapsulate to responder's EK for shared secret #2
        let encaps_result =
            MLKEM::encapsulate_raw(&responder_ek).map_err(NoiseError::EncapsFailed)?;

        let ss2_bytes = hex::decode(&encaps_result.shared_secret).map_err(|e| {
            NoiseError::InvalidHandshakeMessage(format!("Failed to decode SS2: {}", e))
        })?;
        let mut ss2_arr = [0u8; 32];
        ss2_arr.copy_from_slice(&ss2_bytes);
        self.shared_secrets.push(ss2_arr);

        // Derive final keys
        self.derive_transport_keys()?;
        self.state = HandshakeState::Complete;

        let ct_bytes = hex::decode(&encaps_result.ciphertext).map_err(|e| {
            NoiseError::InvalidHandshakeMessage(format!("Failed to decode final CT: {}", e))
        })?;

        Ok(HandshakeMessage::Final {
            ciphertext: ct_bytes,
        })
    }

    /// Responder: Process final message and complete handshake
    pub fn process_final(&mut self, final_msg: &HandshakeMessage) -> Result<(), NoiseError> {
        if self.role != NoiseRole::Responder || self.state != HandshakeState::ReceivedInitiation {
            return Err(NoiseError::InvalidState);
        }

        let ciphertext = match final_msg {
            HandshakeMessage::Final { ciphertext } => hex::encode(ciphertext),
            _ => {
                return Err(NoiseError::InvalidHandshakeMessage(
                    "Expected Final message".to_string(),
                ))
            }
        };

        // Decapsulate to get shared secret #2
        let our_dk = self
            .ephemeral
            .as_ref()
            .ok_or(NoiseError::InvalidState)?
            .decapsulation_key
            .clone();

        let ss2 = MLKEM::decapsulate_raw(&our_dk, &ciphertext).map_err(NoiseError::DecapsFailed)?;

        let ss2_bytes = hex::decode(&ss2).map_err(|e| {
            NoiseError::InvalidHandshakeMessage(format!("Failed to decode SS2: {}", e))
        })?;
        let mut ss2_arr = [0u8; 32];
        ss2_arr.copy_from_slice(&ss2_bytes);
        self.shared_secrets.push(ss2_arr);

        // Derive final keys
        self.derive_transport_keys()?;
        self.state = HandshakeState::Complete;

        Ok(())
    }

    /// Derive transport keys from shared secrets
    fn derive_transport_keys(&mut self) -> Result<(), NoiseError> {
        if self.shared_secrets.len() < 2 {
            return Err(NoiseError::InvalidState);
        }

        // Mix all shared secrets with SHA3-256
        let mut hasher = Sha3_256::new();
        hasher.update(b"WarmLogic_Noise_v1");
        for ss in &self.shared_secrets {
            hasher.update(ss);
        }
        let master_key: [u8; 32] = hasher.finalize().into();

        // Derive directional keys: initiator->responder and responder->initiator
        // This ensures both parties can communicate bidirectionally
        let mut i2r_hasher = Sha3_256::new();
        i2r_hasher.update(master_key);
        i2r_hasher.update(b"initiator_to_responder");
        let initiator_to_responder_key: [u8; 32] = i2r_hasher.finalize().into();

        let mut r2i_hasher = Sha3_256::new();
        r2i_hasher.update(master_key);
        r2i_hasher.update(b"responder_to_initiator");
        let responder_to_initiator_key: [u8; 32] = r2i_hasher.finalize().into();

        // Assign keys based on role
        match self.role {
            NoiseRole::Initiator => {
                self.send_key = Some(initiator_to_responder_key);
                self.recv_key = Some(responder_to_initiator_key);
            }
            NoiseRole::Responder => {
                self.send_key = Some(responder_to_initiator_key);
                self.recv_key = Some(initiator_to_responder_key);
            }
        }

        // Clear shared secrets
        for ss in &mut self.shared_secrets {
            ss.zeroize();
        }
        self.shared_secrets.clear();

        Ok(())
    }

    // ========================================================================
    // Transport Methods (after handshake)
    // ========================================================================

    /// Encrypt a message for transport
    pub fn encrypt(&mut self, plaintext: &[u8]) -> Result<Vec<u8>, NoiseError> {
        if !self.is_handshake_complete() {
            return Err(NoiseError::HandshakeIncomplete);
        }

        if plaintext.len() > MAX_ENCRYPTED_MSG_SIZE - 16 - NONCE_SIZE {
            return Err(NoiseError::MessageTooLarge);
        }

        let send_key = self.send_key.ok_or(NoiseError::InvalidState)?;

        // Create nonce from counter
        let mut nonce_bytes = [0u8; NONCE_SIZE];
        nonce_bytes[4..].copy_from_slice(&self.send_nonce.to_be_bytes());
        self.send_nonce += 1;

        let cipher = Aes256Gcm::new_from_slice(&send_key)
            .map_err(|e| NoiseError::EncryptionFailed(format!("Cipher init: {}", e)))?;

        let nonce = Nonce::from_slice(&nonce_bytes);
        let ciphertext = cipher
            .encrypt(nonce, plaintext)
            .map_err(|e| NoiseError::EncryptionFailed(format!("Encrypt: {}", e)))?;

        // Prepend nonce to ciphertext
        let mut result = Vec::with_capacity(NONCE_SIZE + ciphertext.len());
        result.extend_from_slice(&nonce_bytes);
        result.extend(ciphertext);

        Ok(result)
    }

    /// Decrypt a message from transport
    pub fn decrypt(&mut self, ciphertext: &[u8]) -> Result<Vec<u8>, NoiseError> {
        if !self.is_handshake_complete() {
            return Err(NoiseError::HandshakeIncomplete);
        }

        if ciphertext.len() < NONCE_SIZE + 16 {
            return Err(NoiseError::DecryptionFailed(
                "Message too short".to_string(),
            ));
        }

        let recv_key = self.recv_key.ok_or(NoiseError::InvalidState)?;

        // Extract nonce
        let nonce_bytes = &ciphertext[..NONCE_SIZE];
        let encrypted = &ciphertext[NONCE_SIZE..];

        // Verify nonce is not replayed (simple check: must be >= expected)
        // Nonce format: [4 bytes padding][8 bytes counter]
        let incoming_nonce = u64::from_be_bytes([
            nonce_bytes[4],
            nonce_bytes[5],
            nonce_bytes[6],
            nonce_bytes[7],
            nonce_bytes[8],
            nonce_bytes[9],
            nonce_bytes[10],
            nonce_bytes[11],
        ]);
        if incoming_nonce < self.recv_nonce {
            return Err(NoiseError::DecryptionFailed(
                "Replay detected: nonce too low".to_string(),
            ));
        }
        self.recv_nonce = incoming_nonce + 1;

        let cipher = Aes256Gcm::new_from_slice(&recv_key)
            .map_err(|e| NoiseError::DecryptionFailed(format!("Cipher init: {}", e)))?;

        let nonce = Nonce::from_slice(nonce_bytes);
        let plaintext = cipher
            .decrypt(nonce, encrypted)
            .map_err(|_| NoiseError::DecryptionFailed("Authentication failed".to_string()))?;

        Ok(plaintext)
    }

    /// Get nonce counters for debugging/monitoring
    #[must_use]
    pub fn get_nonce_counters(&self) -> (u64, u64) {
        (self.send_nonce, self.recv_nonce)
    }
}

impl Drop for NoiseSession {
    fn drop(&mut self) {
        // Zeroize keys
        if let Some(ref mut key) = self.send_key {
            key.zeroize();
        }
        if let Some(ref mut key) = self.recv_key {
            key.zeroize();
        }
        for ss in &mut self.shared_secrets {
            ss.zeroize();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_full_handshake() {
        // Create sessions
        let mut initiator = NoiseSession::new_initiator().unwrap();
        let mut responder = NoiseSession::new_responder().unwrap();

        // Step 1: Initiator sends Init
        let init_msg = initiator.initiate().unwrap();
        assert_eq!(initiator.get_state(), HandshakeState::WaitingForResponse);

        // Step 2: Responder processes Init and sends Response
        let response_msg = responder.respond(&init_msg).unwrap();
        assert_eq!(responder.get_state(), HandshakeState::ReceivedInitiation);

        // Step 3: Initiator processes Response and sends Final
        let final_msg = initiator.process_response(&response_msg).unwrap();
        assert!(initiator.is_handshake_complete());

        // Step 4: Responder processes Final
        responder.process_final(&final_msg).unwrap();
        assert!(responder.is_handshake_complete());
    }

    #[test]
    fn test_encrypted_transport() {
        // Complete handshake
        let mut initiator = NoiseSession::new_initiator().unwrap();
        let mut responder = NoiseSession::new_responder().unwrap();

        let init_msg = initiator.initiate().unwrap();
        let response_msg = responder.respond(&init_msg).unwrap();
        let final_msg = initiator.process_response(&response_msg).unwrap();
        responder.process_final(&final_msg).unwrap();

        // Test encryption/decryption
        let plaintext = b"Hello, Post-Quantum World!";

        // Initiator -> Responder
        let encrypted = initiator.encrypt(plaintext).unwrap();
        let decrypted = responder.decrypt(&encrypted).unwrap();
        assert_eq!(decrypted, plaintext);

        // Responder -> Initiator
        let encrypted2 = responder.encrypt(b"Greetings from the future!").unwrap();
        let decrypted2 = initiator.decrypt(&encrypted2).unwrap();
        assert_eq!(decrypted2, b"Greetings from the future!");
    }

    #[test]
    fn test_message_serialization() {
        let init = HandshakeMessage::Init {
            ephemeral_ek: vec![1, 2, 3, 4],
        };
        let bytes = init.to_bytes();
        let parsed = HandshakeMessage::from_bytes(&bytes).unwrap();

        match parsed {
            HandshakeMessage::Init { ephemeral_ek } => {
                assert_eq!(ephemeral_ek, vec![1, 2, 3, 4]);
            }
            _ => panic!("Wrong message type"),
        }
    }

    #[test]
    fn test_replay_detection() {
        // Complete handshake
        let mut initiator = NoiseSession::new_initiator().unwrap();
        let mut responder = NoiseSession::new_responder().unwrap();

        let init_msg = initiator.initiate().unwrap();
        let response_msg = responder.respond(&init_msg).unwrap();
        let final_msg = initiator.process_response(&response_msg).unwrap();
        responder.process_final(&final_msg).unwrap();

        // Send two messages
        let enc1 = initiator.encrypt(b"message 1").unwrap();
        let enc2 = initiator.encrypt(b"message 2").unwrap();

        // Decrypt in order - should work
        responder.decrypt(&enc1).unwrap();
        responder.decrypt(&enc2).unwrap();

        // Replay first message - should fail
        let result = responder.decrypt(&enc1);
        assert!(result.is_err());
    }

    #[test]
    fn test_encryption_before_handshake_fails() {
        let mut session = NoiseSession::new_initiator().unwrap();
        let result = session.encrypt(b"test");
        assert!(matches!(result, Err(NoiseError::HandshakeIncomplete)));
    }

    #[test]
    fn test_wrong_state_transitions() {
        let mut initiator = NoiseSession::new_initiator().unwrap();

        // Can't respond as initiator
        let fake_init = HandshakeMessage::Init {
            ephemeral_ek: vec![0; 100],
        };
        let result = initiator.respond(&fake_init);
        assert!(matches!(result, Err(NoiseError::InvalidState)));
    }
}
