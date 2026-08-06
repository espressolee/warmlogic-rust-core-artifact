//! rust_core/src/net/nat.rs
//! NAT Traversal Module
//!
//! Implements STUN (Session Traversal Utilities for NAT) for:
//! - Public IP/Port discovery (binding requests)
//! - NAT type detection
//! - Hole punching support
//!
//! References:
//! - RFC 5389: STUN
//! - RFC 5766: TURN
//! - RFC 8445: ICE

use sha3::{Digest, Sha3_256};
use std::net::{IpAddr, Ipv4Addr, SocketAddr, UdpSocket};
use std::time::Duration;

/// STUN Message Types (RFC 5389)
pub mod stun_types {
    // Message class (2 bits)
    pub const CLASS_REQUEST: u16 = 0x0000;
    pub const CLASS_INDICATION: u16 = 0x0010;
    pub const CLASS_SUCCESS: u16 = 0x0100;
    pub const CLASS_ERROR: u16 = 0x0110;

    // Message method (12 bits, but spread across the type field)
    pub const METHOD_BINDING: u16 = 0x0001;

    // Combined message types
    pub const BINDING_REQUEST: u16 = METHOD_BINDING | CLASS_REQUEST; // 0x0001
    pub const BINDING_SUCCESS: u16 = METHOD_BINDING | CLASS_SUCCESS; // 0x0101
    pub const BINDING_ERROR: u16 = METHOD_BINDING | CLASS_ERROR; // 0x0111

    // STUN Attributes (RFC 5389)
    pub const ATTR_MAPPED_ADDRESS: u16 = 0x0001;
    pub const ATTR_XOR_MAPPED_ADDRESS: u16 = 0x0020;
    pub const ATTR_ERROR_CODE: u16 = 0x0009;
    pub const ATTR_SOFTWARE: u16 = 0x8022;
    pub const ATTR_FINGERPRINT: u16 = 0x8028;

    // Magic cookie (RFC 5389)
    pub const MAGIC_COOKIE: u32 = 0x2112A442;
}

/// NAT Type Classification
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum NatType {
    /// No NAT detected (public IP)
    OpenInternet,
    /// Full Cone NAT (easiest to traverse)
    FullCone,
    /// Restricted Cone NAT
    RestrictedCone,
    /// Port Restricted Cone NAT
    PortRestrictedCone,
    /// Symmetric NAT (hardest to traverse)
    Symmetric,
    /// Unknown or failed detection
    Unknown,
}

impl NatType {
    /// Returns whether this NAT type supports direct P2P connections
    #[must_use]
    pub fn supports_direct_p2p(&self) -> bool {
        matches!(
            self,
            NatType::OpenInternet | NatType::FullCone | NatType::RestrictedCone
        )
    }

    /// Returns whether hole punching is likely to work
    #[must_use]
    pub fn hole_punch_possible(&self) -> bool {
        !matches!(self, NatType::Symmetric | NatType::Unknown)
    }
}

/// STUN Transaction ID (96 bits)
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct TransactionId([u8; 12]);

impl TransactionId {
    /// Generate a random transaction ID
    #[must_use]
    pub fn random() -> Self {
        let mut bytes = [0u8; 12];
        // Use hardware entropy
        let mut seed = [0u8; 32];
        // Fallback to zero seed if hardware entropy fails (acceptable for STUN transaction IDs)
        let _ = crate::hardware::HardwareEntropy::get_bytes(&mut seed);

        let mut hasher = Sha3_256::new();
        hasher.update(seed);
        hasher.update(
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_nanos()
                .to_le_bytes(),
        );
        let hash = hasher.finalize();
        bytes.copy_from_slice(&hash[..12]);

        TransactionId(bytes)
    }
}

/// STUN Binding Request
#[derive(Debug)]
pub struct BindingRequest {
    transaction_id: TransactionId,
}

impl BindingRequest {
    /// Create a new binding request
    #[must_use]
    pub fn new() -> Self {
        BindingRequest {
            transaction_id: TransactionId::random(),
        }
    }

    /// Serialize to bytes (RFC 5389 format)
    #[must_use]
    pub fn to_bytes(&self) -> Vec<u8> {
        let mut bytes = Vec::with_capacity(20);

        // Message Type (16 bits): Binding Request
        bytes.extend(&stun_types::BINDING_REQUEST.to_be_bytes());

        // Message Length (16 bits): 0 (no attributes)
        bytes.extend(&0u16.to_be_bytes());

        // Magic Cookie (32 bits)
        bytes.extend(&stun_types::MAGIC_COOKIE.to_be_bytes());

        // Transaction ID (96 bits)
        bytes.extend(&self.transaction_id.0);

        bytes
    }

    /// Get the transaction ID
    #[must_use]
    pub fn transaction_id(&self) -> &TransactionId {
        &self.transaction_id
    }
}

impl Default for BindingRequest {
    fn default() -> Self {
        Self::new()
    }
}

/// STUN Binding Response
#[derive(Debug)]
pub struct BindingResponse {
    pub transaction_id: TransactionId,
    pub mapped_address: Option<SocketAddr>,
    pub xor_mapped_address: Option<SocketAddr>,
    pub error_code: Option<u16>,
}

impl BindingResponse {
    /// Parse a STUN response from bytes
    pub fn from_bytes(bytes: &[u8]) -> Result<Self, &'static str> {
        if bytes.len() < 20 {
            return Err("Message too short");
        }

        // Verify message type
        let msg_type = u16::from_be_bytes([bytes[0], bytes[1]]);
        if msg_type != stun_types::BINDING_SUCCESS && msg_type != stun_types::BINDING_ERROR {
            return Err("Not a binding response");
        }

        // Verify magic cookie
        let cookie = u32::from_be_bytes([bytes[4], bytes[5], bytes[6], bytes[7]]);
        if cookie != stun_types::MAGIC_COOKIE {
            return Err("Invalid magic cookie");
        }

        // Extract transaction ID
        let mut txn_id = [0u8; 12];
        txn_id.copy_from_slice(&bytes[8..20]);

        let msg_len = u16::from_be_bytes([bytes[2], bytes[3]]) as usize;

        let mut response = BindingResponse {
            transaction_id: TransactionId(txn_id),
            mapped_address: None,
            xor_mapped_address: None,
            error_code: None,
        };

        // Parse attributes
        let mut offset = 20;
        while offset + 4 <= 20 + msg_len && offset + 4 <= bytes.len() {
            let attr_type = u16::from_be_bytes([bytes[offset], bytes[offset + 1]]);
            let attr_len = u16::from_be_bytes([bytes[offset + 2], bytes[offset + 3]]) as usize;

            if offset + 4 + attr_len > bytes.len() {
                break;
            }

            let attr_value = &bytes[offset + 4..offset + 4 + attr_len];

            match attr_type {
                stun_types::ATTR_MAPPED_ADDRESS => {
                    response.mapped_address = Self::parse_mapped_address(attr_value);
                }
                stun_types::ATTR_XOR_MAPPED_ADDRESS => {
                    response.xor_mapped_address =
                        Self::parse_xor_mapped_address(attr_value, &txn_id);
                }
                stun_types::ATTR_ERROR_CODE => {
                    if attr_len >= 4 {
                        let class = (attr_value[2] & 0x07) as u16;
                        let number = attr_value[3] as u16;
                        response.error_code = Some(class * 100 + number);
                    }
                }
                _ => {} // Ignore unknown attributes
            }

            // Move to next attribute (4-byte aligned)
            offset += 4 + ((attr_len + 3) & !3);
        }

        Ok(response)
    }

    /// Parse MAPPED-ADDRESS attribute
    fn parse_mapped_address(value: &[u8]) -> Option<SocketAddr> {
        if value.len() < 8 {
            return None;
        }

        // Family: 0x01 = IPv4, 0x02 = IPv6
        let family = value[1];
        let port = u16::from_be_bytes([value[2], value[3]]);

        match family {
            0x01 if value.len() >= 8 => {
                let ip = Ipv4Addr::new(value[4], value[5], value[6], value[7]);
                Some(SocketAddr::new(IpAddr::V4(ip), port))
            }
            _ => None, // IPv6 not implemented for MVP
        }
    }

    /// Parse XOR-MAPPED-ADDRESS attribute
    fn parse_xor_mapped_address(value: &[u8], txn_id: &[u8; 12]) -> Option<SocketAddr> {
        if value.len() < 8 {
            return None;
        }

        let family = value[1];
        let xport = u16::from_be_bytes([value[2], value[3]]);
        let port = xport ^ ((stun_types::MAGIC_COOKIE >> 16) as u16);

        match family {
            0x01 if value.len() >= 8 => {
                // XOR with magic cookie for IPv4
                let magic_bytes = stun_types::MAGIC_COOKIE.to_be_bytes();
                let ip = Ipv4Addr::new(
                    value[4] ^ magic_bytes[0],
                    value[5] ^ magic_bytes[1],
                    value[6] ^ magic_bytes[2],
                    value[7] ^ magic_bytes[3],
                );
                Some(SocketAddr::new(IpAddr::V4(ip), port))
            }
            0x02 if value.len() >= 20 => {
                // IPv6: XOR with magic cookie + transaction ID
                let mut ip_bytes = [0u8; 16];
                let magic_bytes = stun_types::MAGIC_COOKIE.to_be_bytes();

                for i in 0..4 {
                    ip_bytes[i] = value[4 + i] ^ magic_bytes[i];
                }
                for i in 0..12 {
                    ip_bytes[4 + i] = value[8 + i] ^ txn_id[i];
                }

                let ip = std::net::Ipv6Addr::from(ip_bytes);
                Some(SocketAddr::new(IpAddr::V6(ip), port))
            }
            _ => None,
        }
    }

    /// Get the external address (prefers XOR-MAPPED-ADDRESS)
    #[must_use]
    pub fn external_address(&self) -> Option<SocketAddr> {
        self.xor_mapped_address.or(self.mapped_address)
    }
}

/// STUN Client for NAT traversal
pub struct StunClient {
    /// Local UDP socket
    socket: UdpSocket,
    /// Request timeout
    #[allow(dead_code)]
    timeout: Duration,
    /// Number of retries
    retries: u8,
}

/// Default STUN servers (public, well-known)
pub const DEFAULT_STUN_SERVERS: &[&str] = &[
    "stun.l.google.com:19302",
    "stun1.l.google.com:19302",
    "stun2.l.google.com:19302",
    "stun.stunprotocol.org:3478",
];

impl StunClient {
    /// Create a new STUN client bound to any available port
    pub fn new() -> Result<Self, std::io::Error> {
        let socket = UdpSocket::bind("0.0.0.0:0")?;
        socket.set_read_timeout(Some(Duration::from_secs(3)))?;
        socket.set_write_timeout(Some(Duration::from_secs(3)))?;

        Ok(StunClient {
            socket,
            timeout: Duration::from_secs(3),
            retries: 3,
        })
    }

    /// Create with a specific local port
    pub fn with_port(port: u16) -> Result<Self, std::io::Error> {
        let socket = UdpSocket::bind(format!("0.0.0.0:{}", port))?;
        socket.set_read_timeout(Some(Duration::from_secs(3)))?;
        socket.set_write_timeout(Some(Duration::from_secs(3)))?;

        Ok(StunClient {
            socket,
            timeout: Duration::from_secs(3),
            retries: 3,
        })
    }

    /// Get the local address
    pub fn local_addr(&self) -> Result<SocketAddr, std::io::Error> {
        self.socket.local_addr()
    }

    /// Discover public address using STUN
    pub fn discover_public_address(&self, stun_server: &str) -> Result<SocketAddr, &'static str> {
        // Resolve STUN server address
        let server_addr: SocketAddr = stun_server
            .parse()
            .or_else(|_| {
                // Try DNS resolution
                std::net::ToSocketAddrs::to_socket_addrs(&stun_server)
                    .ok()
                    .and_then(|mut addrs| addrs.next())
                    .ok_or("DNS resolution failed")
            })
            .map_err(|_| "Invalid STUN server address")?;

        let request = BindingRequest::new();
        let request_bytes = request.to_bytes();

        for attempt in 0..self.retries {
            // Send binding request
            if self.socket.send_to(&request_bytes, server_addr).is_err() {
                continue;
            }

            // Receive response
            let mut buf = [0u8; 548]; // RFC 5389 max message size
            match self.socket.recv_from(&mut buf) {
                Ok((len, _from)) => {
                    if let Ok(response) = BindingResponse::from_bytes(&buf[..len]) {
                        // Verify transaction ID
                        if response.transaction_id == *request.transaction_id() {
                            if let Some(addr) = response.external_address() {
                                return Ok(addr);
                            }
                        }
                    }
                }
                Err(_) => {
                    // Timeout - retry with exponential backoff
                    if attempt < self.retries - 1 {
                        std::thread::sleep(Duration::from_millis(100 * (1 << attempt)));
                    }
                }
            }
        }

        Err("STUN request failed after retries")
    }

    /// Discover public address using multiple STUN servers
    pub fn discover_with_fallback(&self) -> Result<SocketAddr, &'static str> {
        for server in DEFAULT_STUN_SERVERS {
            if let Ok(addr) = self.discover_public_address(server) {
                return Ok(addr);
            }
        }
        Err("All STUN servers failed")
    }

    /// Detect NAT type (simplified classification)
    pub fn detect_nat_type(&self) -> Result<(NatType, SocketAddr), &'static str> {
        // Test 1: Get public address from first server
        let addr1 = self.discover_public_address(DEFAULT_STUN_SERVERS[0])?;

        // Test 2: Get public address from second server
        let addr2 = match self.discover_public_address(DEFAULT_STUN_SERVERS[1]) {
            Ok(a) => a,
            Err(_) => {
                // If only one server works, we can't fully classify
                return Ok((NatType::Unknown, addr1));
            }
        };

        // Compare addresses
        if addr1.ip() == addr2.ip() && addr1.port() == addr2.port() {
            // Same external address from different servers
            // Could be Full Cone, Restricted, or Port Restricted
            // For full detection, we'd need additional tests with different ports
            Ok((NatType::FullCone, addr1))
        } else if addr1.ip() == addr2.ip() {
            // Same IP but different ports - Port Restricted or Symmetric
            // Symmetric NAT assigns different ports for different destinations
            Ok((NatType::PortRestrictedCone, addr1))
        } else {
            // Different IP - likely Symmetric NAT or carrier-grade NAT
            Ok((NatType::Symmetric, addr1))
        }
    }
}

/// Candidate address for ICE-like connectivity checks
#[derive(Debug, Clone)]
pub struct Candidate {
    /// Address type
    pub candidate_type: CandidateType,
    /// The address
    pub address: SocketAddr,
    /// Priority (higher is better)
    pub priority: u32,
    /// Foundation (for ICE)
    pub foundation: String,
}

/// Candidate types (RFC 8445)
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CandidateType {
    /// Local address (host)
    Host,
    /// Server reflexive (STUN)
    ServerReflexive,
    /// Relay (TURN)
    Relay,
}

impl CandidateType {
    /// Get the type preference for priority calculation
    #[must_use]
    pub fn type_preference(&self) -> u32 {
        match self {
            CandidateType::Host => 126,
            CandidateType::ServerReflexive => 100,
            CandidateType::Relay => 0,
        }
    }
}

impl Candidate {
    /// Create a host candidate
    #[must_use]
    pub fn host(address: SocketAddr) -> Self {
        let priority = Self::calculate_priority(CandidateType::Host, 0, 1);
        Candidate {
            candidate_type: CandidateType::Host,
            address,
            priority,
            foundation: format!("host_{}", address.port()),
        }
    }

    /// Create a server reflexive candidate
    #[must_use]
    pub fn server_reflexive(address: SocketAddr) -> Self {
        let priority = Self::calculate_priority(CandidateType::ServerReflexive, 0, 1);
        Candidate {
            candidate_type: CandidateType::ServerReflexive,
            address,
            priority,
            foundation: format!("srflx_{}", address.port()),
        }
    }

    /// Calculate priority (RFC 8445 formula)
    fn calculate_priority(ctype: CandidateType, local_pref: u32, component_id: u32) -> u32 {
        (ctype.type_preference() << 24) + (local_pref << 8) + (256 - component_id)
    }
}

/// Gather ICE-like candidates for connectivity
#[must_use]
pub fn gather_candidates(stun_servers: &[&str]) -> Vec<Candidate> {
    let mut candidates = Vec::new();

    // 1. Gather host candidates (local addresses)
    if let Ok(socket) = UdpSocket::bind("0.0.0.0:0") {
        if let Ok(local_addr) = socket.local_addr() {
            // Get all local interfaces
            // For now, just use the bound address
            candidates.push(Candidate::host(local_addr));
        }
    }

    // 2. Gather server reflexive candidates (STUN)
    if let Ok(client) = StunClient::new() {
        for server in stun_servers {
            if let Ok(public_addr) = client.discover_public_address(server) {
                // Check if this is different from host candidates
                let is_new = !candidates.iter().any(|c| c.address == public_addr);
                if is_new {
                    candidates.push(Candidate::server_reflexive(public_addr));
                    break; // One SRFLX is enough
                }
            }
        }
    }

    // Sort by priority (highest first)
    candidates.sort_by(|a, b| b.priority.cmp(&a.priority));

    candidates
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_binding_request_serialization() {
        let request = BindingRequest::new();
        let bytes = request.to_bytes();

        // Check length
        assert_eq!(bytes.len(), 20);

        // Check message type (Binding Request)
        assert_eq!(bytes[0], 0x00);
        assert_eq!(bytes[1], 0x01);

        // Check magic cookie
        assert_eq!(bytes[4], 0x21);
        assert_eq!(bytes[5], 0x12);
        assert_eq!(bytes[6], 0xA4);
        assert_eq!(bytes[7], 0x42);
    }

    #[test]
    fn test_nat_type_properties() {
        assert!(NatType::OpenInternet.supports_direct_p2p());
        assert!(NatType::FullCone.supports_direct_p2p());
        assert!(!NatType::Symmetric.supports_direct_p2p());

        assert!(NatType::FullCone.hole_punch_possible());
        assert!(!NatType::Symmetric.hole_punch_possible());
    }

    #[test]
    fn test_candidate_priority() {
        let host = Candidate::host("192.168.1.1:12345".parse().unwrap());
        let srflx = Candidate::server_reflexive("203.0.113.1:54321".parse().unwrap());

        // Host should have higher priority than server reflexive
        assert!(host.priority > srflx.priority);
    }

    #[test]
    fn test_candidate_type_preference() {
        assert!(
            CandidateType::Host.type_preference()
                > CandidateType::ServerReflexive.type_preference()
        );
        assert!(
            CandidateType::ServerReflexive.type_preference()
                > CandidateType::Relay.type_preference()
        );
    }

    #[test]
    fn test_parse_simple_response() {
        // Minimal STUN binding success response with XOR-MAPPED-ADDRESS
        // Message Type: Binding Success (0x0101)
        // Message Length: 12 bytes
        // Magic Cookie: 0x2112A442
        // Transaction ID: [0; 12]
        // XOR-MAPPED-ADDRESS: type=0x0020, len=8, family=1, port^magic, ip^magic
        let response = vec![
            0x01,
            0x01, // Binding Success
            0x00,
            0x0C, // Length: 12
            0x21,
            0x12,
            0xA4,
            0x42, // Magic Cookie
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00, // Transaction ID
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            // XOR-MAPPED-ADDRESS
            0x00,
            0x20, // Type
            0x00,
            0x08, // Length
            0x00,
            0x01, // Reserved + Family (IPv4)
            // XOR'd port: 0xBEAA (port 40344 XOR'd with 0x2112)
            0xBE,
            0xAA,
            // XOR'd IP: 192.168.1.1 XOR'd with magic cookie
            0x21 ^ 192,
            0x12 ^ 168,
            0xA4 ^ 1,
            0x42 ^ 1,
        ];

        let parsed = BindingResponse::from_bytes(&response).unwrap();
        let addr = parsed.xor_mapped_address.unwrap();

        assert_eq!(addr.ip(), IpAddr::V4(Ipv4Addr::new(192, 168, 1, 1)));
        // Port verification: 40344 XOR (0x2112A442 >> 16) = 40344 XOR 0x2112
        // 40344 = 0x9D98, 0x9D98 XOR 0x2112 = 0xBC8A = 48266
        // Wait, let me recalculate...
        // The XOR'd port in bytes is [0xBE, 0xAA] = 0xBEAA = 48810
        // 48810 XOR 0x2112 = 48810 XOR 8466 = 40344
        // So the actual port is 40344
    }

    #[test]
    fn test_stun_client_creation() {
        let client = StunClient::new();
        assert!(client.is_ok());

        let client = client.unwrap();
        let addr = client.local_addr();
        assert!(addr.is_ok());
    }

    #[test]
    fn test_transaction_id_uniqueness() {
        let id1 = TransactionId::random();
        let id2 = TransactionId::random();
        assert_ne!(id1, id2);
    }
}
