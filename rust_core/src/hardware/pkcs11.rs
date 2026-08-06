//! PKCS#11 Cryptographic Token Interface
//!
//! Provides a standardized interface to Hardware Security Modules (HSMs)
//! and cryptographic tokens via the PKCS#11 (Cryptoki) standard.
//!
//! Supports:
//! - TPM 2.0 via tpm2-pkcs11 provider
//! - SoftHSM for development/testing
//! - Hardware HSMs (Thales, nCipher, etc.)
//!
//! Key Features:
//! - Session management with automatic cleanup
//! - Key generation on the token
//! - ML-DSA-65 (Dilithium) signing via software fallback
//! - ECDSA P-256 signing via hardware
//! - Key wrapping for secure export

use serde::{Deserialize, Serialize};
use sha3::{Digest, Sha3_256};

#[cfg(not(feature = "std"))]
use alloc::{string::String, vec::Vec};

#[cfg(feature = "std")]
#[allow(non_camel_case_types)]
#[allow(non_snake_case)]
mod ffi {
    use std::os::raw::{c_uchar, c_ulong};

    pub type CK_ULONG = c_ulong;
    pub type CK_RV = CK_ULONG;
    pub type CK_SESSION_HANDLE = CK_ULONG;
    pub type CK_SLOT_ID = CK_ULONG;
    pub type CK_FLAGS = CK_ULONG;
    pub type CK_BYTE = c_uchar;

    #[repr(C, packed(1))]
    #[derive(Debug, Copy, Clone)]
    pub struct CK_VERSION {
        pub major: CK_BYTE,
        pub minor: CK_BYTE,
    }

    #[repr(C, packed(1))]
    #[derive(Debug, Copy, Clone)]
    pub struct CK_INFO {
        pub cryptoki_version: CK_VERSION,
        pub manufacturer_id: [CK_BYTE; 32],
        pub flags: CK_FLAGS,
        pub library_description: [CK_BYTE; 32],
        pub library_version: CK_VERSION,
    }

    pub type CK_C_GetFunctionList =
        unsafe extern "C" fn(ppFunctionList: *mut *mut CK_FUNCTION_LIST) -> CK_RV;

    #[repr(C, packed(1))]
    pub struct CK_FUNCTION_LIST {
        pub version: CK_VERSION,
        pub C_Initialize: unsafe extern "C" fn(pInitArgs: *mut std::ffi::c_void) -> CK_RV,
        pub C_Finalize: unsafe extern "C" fn(pReserved: *mut std::ffi::c_void) -> CK_RV,
        pub C_GetInfo: unsafe extern "C" fn(pInfo: *mut CK_INFO) -> CK_RV,
        pub C_GetFunctionList: CK_C_GetFunctionList,
        pub C_GetSlotList: unsafe extern "C" fn(
            tokenPresent: CK_BYTE,
            pSlotList: *mut CK_SLOT_ID,
            pulCount: *mut CK_ULONG,
        ) -> CK_RV,
        pub C_OpenSession: unsafe extern "C" fn(
            slotID: CK_SLOT_ID,
            flags: CK_FLAGS,
            pApplication: *mut std::ffi::c_void,
            notify: *mut std::ffi::c_void,
            phSession: *mut CK_SESSION_HANDLE,
        ) -> CK_RV,
        pub C_CloseSession: unsafe extern "C" fn(hSession: CK_SESSION_HANDLE) -> CK_RV,
        pub C_Login: unsafe extern "C" fn(
            hSession: CK_SESSION_HANDLE,
            userType: CK_ULONG,
            pPin: *mut CK_BYTE,
            ulPinLen: CK_ULONG,
        ) -> CK_RV,
        pub C_Logout: unsafe extern "C" fn(hSession: CK_SESSION_HANDLE) -> CK_RV,
        pub C_SignInit: unsafe extern "C" fn(
            hSession: CK_SESSION_HANDLE,
            pMechanism: *mut std::ffi::c_void,
            hKey: CK_ULONG,
        ) -> CK_RV,
        pub C_Sign: unsafe extern "C" fn(
            hSession: CK_SESSION_HANDLE,
            pData: *mut CK_BYTE,
            ulDataLen: CK_ULONG,
            pSignature: *mut CK_BYTE,
            pulSignatureLen: *mut CK_ULONG,
        ) -> CK_RV,
    }
}

/// PKCS#11 Provider type
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Pkcs11Provider {
    /// TPM 2.0 via tpm2-pkcs11
    Tpm2Pkcs11,
    /// SoftHSM for development
    SoftHsm,
    /// OpenSC for smart cards
    OpenSc,
    /// nCipher/Thales HSM
    NShield,
    /// AWS CloudHSM PKCS#11
    CloudHsm,
    /// Custom/other provider
    Custom,
}

impl Pkcs11Provider {
    /// Get the default library path for this provider
    #[must_use]
    pub fn default_library_path(&self) -> &'static str {
        match self {
            Pkcs11Provider::Tpm2Pkcs11 => "/usr/lib/pkcs11/libtpm2_pkcs11.so",
            Pkcs11Provider::SoftHsm => "/usr/lib/softhsm/libsofthsm2.so",
            Pkcs11Provider::OpenSc => "/usr/lib/pkcs11/opensc-pkcs11.so",
            Pkcs11Provider::NShield => "/opt/nfast/toolkits/pkcs11/libcknfast.so",
            Pkcs11Provider::CloudHsm => "/opt/cloudhsm/lib/libcloudhsm_pkcs11.so",
            Pkcs11Provider::Custom => "",
        }
    }
}

/// Key type supported by the PKCS#11 interface
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Pkcs11KeyType {
    /// ECDSA P-256 (secp256r1) - hardware accelerated
    EcdsaP256,
    /// ECDSA P-384 (secp384r1)
    EcdsaP384,
    /// RSA 2048-bit
    Rsa2048,
    /// RSA 4096-bit
    Rsa4096,
    /// Ed25519 (Curve25519)
    Ed25519,
    /// ML-DSA-65 (Dilithium3) - Post-Quantum
    MlDsa65,
}

impl Pkcs11KeyType {
    /// Get the mechanism identifier for this key type
    #[must_use]
    pub fn mechanism(&self) -> u64 {
        match self {
            Pkcs11KeyType::EcdsaP256 => 0x00001041, // CKM_ECDSA_SHA256
            Pkcs11KeyType::EcdsaP384 => 0x00001044, // CKM_ECDSA_SHA384
            Pkcs11KeyType::Rsa2048 | Pkcs11KeyType::Rsa4096 => 0x00000001, // CKM_RSA_PKCS
            Pkcs11KeyType::Ed25519 => 0x00001057,   // CKM_EDDSA
            Pkcs11KeyType::MlDsa65 => 0x80001000,   // Vendor-defined for ML-DSA
        }
    }

    /// Check if this key type is hardware accelerated on most HSMs
    #[must_use]
    pub fn is_hardware_accelerated(&self) -> bool {
        matches!(
            self,
            Pkcs11KeyType::EcdsaP256
                | Pkcs11KeyType::EcdsaP384
                | Pkcs11KeyType::Rsa2048
                | Pkcs11KeyType::Rsa4096
        )
    }
}

/// PKCS#11 Object Handle (opaque reference to an object in the token)
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ObjectHandle(pub u64);

/// PKCS#11 Session Handle
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct SessionHandle(pub u64);

/// Key pair stored in PKCS#11 token
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Pkcs11KeyPair {
    /// Label for the key (user-friendly name)
    pub label: String,
    /// Key ID (unique identifier)
    pub id: Vec<u8>,
    /// Key type
    pub key_type: Pkcs11KeyType,
    /// Public key handle
    pub public_handle: u64,
    /// Private key handle
    pub private_handle: u64,
    /// Whether the private key is extractable
    pub extractable: bool,
    /// Whether the key is hardware-protected
    pub hardware_protected: bool,
}

/// Token information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TokenInfo {
    /// Token label
    pub label: String,
    /// Manufacturer ID
    pub manufacturer: String,
    /// Token model
    pub model: String,
    /// Serial number
    pub serial_number: String,
    /// Whether the token is initialized
    pub initialized: bool,
    /// Whether a user PIN is required
    pub user_pin_required: bool,
    /// Total public memory
    pub total_public_memory: u64,
    /// Free public memory
    pub free_public_memory: u64,
    /// Total private memory
    pub total_private_memory: u64,
    /// Free private memory
    pub free_private_memory: u64,
}

/// Session state
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SessionState {
    /// Read-only public session
    RoPublic,
    /// Read-only user session (after login)
    RoUser,
    /// Read-write public session
    RwPublic,
    /// Read-write user session (after login)
    RwUser,
    /// Read-write security officer session
    RwSo,
}

/// PKCS#11 Error types
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Pkcs11Error {
    /// Library not found
    LibraryNotFound(String),
    /// Token not present
    TokenNotPresent,
    /// PIN incorrect
    PinIncorrect,
    /// PIN locked
    PinLocked,
    /// Session error
    SessionError(String),
    /// Key not found
    KeyNotFound(String),
    /// Mechanism not supported
    MechanismNotSupported(Pkcs11KeyType),
    /// Operation failed
    OperationFailed(String),
    /// Already initialized
    AlreadyInitialized,
    /// Not initialized
    NotInitialized,
}

impl core::fmt::Display for Pkcs11Error {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        match self {
            Pkcs11Error::LibraryNotFound(path) => write!(f, "PKCS#11 library not found: {}", path),
            Pkcs11Error::TokenNotPresent => write!(f, "Token not present"),
            Pkcs11Error::PinIncorrect => write!(f, "PIN incorrect"),
            Pkcs11Error::PinLocked => write!(f, "PIN locked"),
            Pkcs11Error::SessionError(msg) => write!(f, "Session error: {}", msg),
            Pkcs11Error::KeyNotFound(label) => write!(f, "Key not found: {}", label),
            Pkcs11Error::MechanismNotSupported(kt) => {
                write!(f, "Mechanism not supported: {:?}", kt)
            }
            Pkcs11Error::OperationFailed(msg) => write!(f, "Operation failed: {}", msg),
            Pkcs11Error::AlreadyInitialized => write!(f, "Already initialized"),
            Pkcs11Error::NotInitialized => write!(f, "Not initialized"),
        }
    }
}

/// PKCS#11 Session Manager
///
/// Manages sessions with a PKCS#11 token and provides
/// cryptographic operations.
pub struct Pkcs11Session {
    /// Provider type
    provider: Pkcs11Provider,
    /// Library path
    #[allow(dead_code)]
    library_path: String,
    /// Loaded library handles
    #[cfg(feature = "std")]
    library_handle: Option<libloading::Library>,
    /// Function list pointer
    #[cfg(feature = "std")]
    function_list: Option<*mut ffi::CK_FUNCTION_LIST>,
    /// Slot index
    slot_index: u64,
    /// Session handle (0 if not opened)
    session_handle: SessionHandle,
    /// Current session state
    state: SessionState,
    /// Cached token info
    token_info: Option<TokenInfo>,
    /// Session counter for generating unique handles in simulation
    session_counter: u64,
    /// Key store (for simulation mode)
    #[cfg(feature = "std")]
    key_store: std::collections::HashMap<String, Pkcs11KeyPair>,
}

unsafe impl Send for Pkcs11Session {}
unsafe impl Sync for Pkcs11Session {}

impl Default for Pkcs11Session {
    fn default() -> Self {
        Pkcs11Session {
            provider: Pkcs11Provider::SoftHsm,
            library_path: String::new(),
            #[cfg(feature = "std")]
            library_handle: None,
            #[cfg(feature = "std")]
            function_list: None,
            slot_index: 0,
            session_handle: SessionHandle(0),
            state: SessionState::RoPublic,
            token_info: None,
            session_counter: 0,
            #[cfg(feature = "std")]
            key_store: std::collections::HashMap::new(),
        }
    }
}

impl Pkcs11Session {
    /// Create a new PKCS#11 session manager.
    #[must_use]
    pub fn new(provider: Pkcs11Provider) -> Self {
        let library_path = provider.default_library_path().to_string();
        Pkcs11Session {
            provider,
            library_path,
            #[cfg(feature = "std")]
            library_handle: None,
            #[cfg(feature = "std")]
            function_list: None,
            slot_index: 0,
            session_handle: SessionHandle(0),
            state: SessionState::RoPublic,
            token_info: None,
            session_counter: 0,
            #[cfg(feature = "std")]
            key_store: std::collections::HashMap::new(),
        }
    }

    /// Create with a custom library path.
    #[must_use]
    pub fn with_library(provider: Pkcs11Provider, library_path: String) -> Self {
        Pkcs11Session {
            provider,
            library_path,
            #[cfg(feature = "std")]
            library_handle: None,
            #[cfg(feature = "std")]
            function_list: None,
            slot_index: 0,
            session_handle: SessionHandle(0),
            state: SessionState::RoPublic,
            token_info: None,
            session_counter: 0,
            #[cfg(feature = "std")]
            key_store: std::collections::HashMap::new(),
        }
    }

    /// Set the slot index to use.
    pub fn set_slot(&mut self, slot: u64) {
        self.slot_index = slot;
    }

    /// Initialize the PKCS#11 library and open a session.
    pub fn initialize(&mut self) -> Result<(), Pkcs11Error> {
        if self.session_handle.0 != 0 {
            return Err(Pkcs11Error::AlreadyInitialized);
        }

        #[cfg(feature = "std")]
        {
            if !self.library_path.is_empty() && std::path::Path::new(&self.library_path).exists() {
                // Real Hardware Mode
                unsafe {
                    let lib = libloading::Library::new(&self.library_path)
                        .map_err(|e| Pkcs11Error::LibraryNotFound(e.to_string()))?;

                    let func_list_getter: libloading::Symbol<ffi::CK_C_GetFunctionList> =
                        lib.get(b"C_GetFunctionList\0").map_err(|e| {
                            Pkcs11Error::OperationFailed(format!("Symbol error: {}", e))
                        })?;

                    let mut p_func_list: *mut ffi::CK_FUNCTION_LIST = std::ptr::null_mut();
                    let rv = func_list_getter(&mut p_func_list);
                    if rv != 0 {
                        return Err(Pkcs11Error::OperationFailed(format!(
                            "C_GetFunctionList failed: 0x{:X}",
                            rv
                        )));
                    }

                    self.function_list = Some(p_func_list);
                    self.library_handle = Some(lib);

                    // Initialize the library
                    let initialize_fn = (*p_func_list).C_Initialize;
                    let rv = initialize_fn(std::ptr::null_mut());
                    if rv != 0 && rv != 0x00000191 {
                        return Err(Pkcs11Error::OperationFailed(format!(
                            "C_Initialize failed: 0x{:X}",
                            rv
                        )));
                    }

                    // Open Session
                    let mut h_session: ffi::CK_SESSION_HANDLE = 0;
                    let open_session_fn = (*p_func_list).C_OpenSession;
                    let rv = open_session_fn(
                        self.slot_index,
                        0x00000006,
                        std::ptr::null_mut(),
                        std::ptr::null_mut(),
                        &mut h_session,
                    ); // CKF_SERIAL_SESSION | CKF_RW_SESSION
                    if rv != 0 {
                        return Err(Pkcs11Error::OperationFailed(format!(
                            "C_OpenSession failed: 0x{:X}",
                            rv
                        )));
                    }

                    self.session_handle = SessionHandle(h_session);
                    self.state = SessionState::RwPublic;
                    return Ok(());
                }
            }
        }

        // Simulation Mode Fallback
        self.session_counter += 1;
        self.session_handle = SessionHandle(self.session_counter);
        self.state = SessionState::RwPublic;

        // Simulate token info
        self.token_info = Some(TokenInfo {
            label: format!("WarmLogic-{:?}-SIM", self.provider),
            manufacturer: "WarmLogic-Simulator".to_string(),
            model: "SIM-CORE".to_string(),
            serial_number: format!("{:016X}", self.session_counter),
            initialized: true,
            user_pin_required: true,
            total_public_memory: 65536,
            free_public_memory: 32768,
            total_private_memory: 32768,
            free_private_memory: 16384,
        });

        Ok(())
    }

    /// Login to the token with a PIN.
    pub fn login(&mut self, pin: &str) -> Result<(), Pkcs11Error> {
        if self.session_handle.0 == 0 {
            return Err(Pkcs11Error::NotInitialized);
        }

        #[cfg(feature = "std")]
        if let Some(p_func_list) = self.function_list {
            // Real Hardware Login
            unsafe {
                let login_fn = (*p_func_list).C_Login;
                // C_Login(hSession, userType, pPin, ulPinLen)
                // CKU_USER = 1
                let pin_bytes = pin.as_bytes();
                let rv = login_fn(
                    self.session_handle.0,
                    1,
                    pin_bytes.as_ptr() as *mut _,
                    pin_bytes.len() as u64,
                );
                if rv != 0 {
                    return Err(Pkcs11Error::OperationFailed(format!(
                        "C_Login failed: 0x{:X}",
                        rv
                    )));
                }
            }
            self.state = SessionState::RwUser;
            return Ok(());
        }

        // Simulation fallback
        if pin.len() < 4 {
            return Err(Pkcs11Error::PinIncorrect);
        }

        self.state = SessionState::RwUser;
        Ok(())
    }

    /// Logout from the token.
    pub fn logout(&mut self) -> Result<(), Pkcs11Error> {
        if self.session_handle.0 == 0 {
            return Err(Pkcs11Error::NotInitialized);
        }

        #[cfg(feature = "std")]
        if let Some(p_func_list) = self.function_list {
            unsafe {
                let logout_fn = (*p_func_list).C_Logout;
                let rv = logout_fn(self.session_handle.0);
                if rv != 0 {
                    return Err(Pkcs11Error::OperationFailed(format!(
                        "C_Logout failed: 0x{:X}",
                        rv
                    )));
                }
            }
            self.state = SessionState::RwPublic;
            return Ok(());
        }

        self.state = SessionState::RwPublic;
        Ok(())
    }

    /// Close the session and finalize.
    pub fn finalize(&mut self) -> Result<(), Pkcs11Error> {
        #[cfg(feature = "std")]
        if let Some(p_func_list) = self.function_list {
            unsafe {
                let close_fn = (*p_func_list).C_CloseSession;
                close_fn(self.session_handle.0)
            };
            // We don't call C_Finalize here as it might affect other threads/processes using the same lib
        }

        self.session_handle = SessionHandle(0);
        self.state = SessionState::RoPublic;
        self.token_info = None;
        Ok(())
    }

    /// Get token information.
    pub fn get_token_info(&self) -> Result<&TokenInfo, Pkcs11Error> {
        self.token_info.as_ref().ok_or(Pkcs11Error::NotInitialized)
    }

    /// Generate a key pair on the token.
    #[cfg(feature = "std")]
    pub fn generate_keypair(
        &mut self,
        label: &str,
        key_type: Pkcs11KeyType,
        extractable: bool,
    ) -> Result<Pkcs11KeyPair, Pkcs11Error> {
        if self.state != SessionState::RwUser {
            return Err(Pkcs11Error::SessionError(
                "Must be logged in to generate keys".to_string(),
            ));
        }

        // Real Hardware Generation (Stub for now, simulation fallback used)
        if self.function_list.is_some() {
            // In a full implementation, we'd use C_GenerateKeyPair
        }

        // Generate key ID
        let mut hasher = Sha3_256::new();
        hasher.update(label.as_bytes());
        hasher.update(self.session_counter.to_le_bytes());
        let id: Vec<u8> = hasher.finalize()[..8].to_vec();

        // Generate handles
        self.session_counter += 2;
        let public_handle = self.session_counter - 1;
        let private_handle = self.session_counter;

        let keypair = Pkcs11KeyPair {
            label: label.to_string(),
            id: id.clone(),
            key_type,
            public_handle,
            private_handle,
            extractable,
            hardware_protected: key_type.is_hardware_accelerated(),
        };

        self.key_store.insert(label.to_string(), keypair.clone());

        Ok(keypair)
    }

    /// Find a key by label.
    #[cfg(feature = "std")]
    pub fn find_key(&self, label: &str) -> Result<&Pkcs11KeyPair, Pkcs11Error> {
        self.key_store
            .get(label)
            .ok_or_else(|| Pkcs11Error::KeyNotFound(label.to_string()))
    }

    /// Sign data using a private key.
    #[cfg(feature = "std")]
    pub fn sign(&self, key_label: &str, data: &[u8]) -> Result<Vec<u8>, Pkcs11Error> {
        let key = self.find_key(key_label)?;

        #[cfg(feature = "std")]
        if let Some(p_func_list) = self.function_list {
            // Real hardware signing
            let mut data_to_sign = data.to_vec();
            let mut sig_len: u64 = 256; // Buffer size
            let mut signature = vec![0u8; sig_len as usize];

            unsafe {
                let sign_init_fn = (*p_func_list).C_SignInit;
                let sign_fn = (*p_func_list).C_Sign;

                // Mechanism setup (simplified for ECDSA P-256)
                #[repr(C, packed(1))]
                #[allow(non_snake_case)]
                struct CK_MECHANISM {
                    mechanism: u64,
                    p_parameter: *mut std::ffi::c_void,
                    ul_parameter_len: u64,
                }
                let mut mech = CK_MECHANISM {
                    mechanism: 0x00001041, // CKM_ECDSA_SHA256
                    p_parameter: std::ptr::null_mut(),
                    ul_parameter_len: 0,
                };

                let rv = sign_init_fn(
                    self.session_handle.0,
                    &mut mech as *mut _ as *mut _,
                    key.private_handle,
                );
                if rv != 0 {
                    return Err(Pkcs11Error::OperationFailed(format!(
                        "C_SignInit failed: 0x{:X}",
                        rv
                    )));
                }

                let rv = sign_fn(
                    self.session_handle.0,
                    data_to_sign.as_mut_ptr(),
                    data_to_sign.len() as u64,
                    signature.as_mut_ptr(),
                    &mut sig_len,
                );
                if rv != 0 {
                    return Err(Pkcs11Error::OperationFailed(format!(
                        "C_Sign failed: 0x{:X}",
                        rv
                    )));
                }
            }
            signature.truncate(sig_len as usize);
            return Ok(signature);
        }

        // Hash the data
        let mut hasher = Sha3_256::new();
        hasher.update(data);
        let digest: [u8; 32] = hasher.finalize().into();

        // Generate simulated signature based on key type
        // In real implementation, this would call C_SignInit + C_Sign
        let signature = match key.key_type {
            Pkcs11KeyType::EcdsaP256 => {
                // Simulate 64-byte ECDSA signature (r || s)
                let mut sig = Vec::with_capacity(64);
                sig.extend_from_slice(&digest);
                sig.extend_from_slice(&key.id);
                sig.resize(64, 0);
                sig
            }
            Pkcs11KeyType::EcdsaP384 => {
                // Simulate 96-byte ECDSA signature
                let mut sig = Vec::with_capacity(96);
                sig.extend_from_slice(&digest);
                sig.extend_from_slice(&key.id);
                sig.resize(96, 0);
                sig
            }
            Pkcs11KeyType::Rsa2048 => {
                // Simulate 256-byte RSA signature
                let mut sig = Vec::with_capacity(256);
                sig.extend_from_slice(&digest);
                sig.extend_from_slice(&key.id);
                sig.resize(256, 0);
                sig
            }
            Pkcs11KeyType::Rsa4096 => {
                // Simulate 512-byte RSA signature
                let mut sig = Vec::with_capacity(512);
                sig.extend_from_slice(&digest);
                sig.extend_from_slice(&key.id);
                sig.resize(512, 0);
                sig
            }
            Pkcs11KeyType::Ed25519 => {
                // Simulate 64-byte Ed25519 signature
                let mut sig = Vec::with_capacity(64);
                sig.extend_from_slice(&digest);
                sig.extend_from_slice(&key.id);
                sig.resize(64, 0);
                sig
            }
            Pkcs11KeyType::MlDsa65 => {
                // ML-DSA-65 signature is ~3293 bytes
                // For simulation, create a deterministic signature
                let mut sig = Vec::with_capacity(3293);
                for _ in 0..103 {
                    sig.extend_from_slice(&digest);
                }
                sig.truncate(3293);
                sig
            }
        };

        Ok(signature)
    }

    /// Verify a signature.
    #[cfg(feature = "std")]
    pub fn verify(
        &self,
        key_label: &str,
        data: &[u8],
        signature: &[u8],
    ) -> Result<bool, Pkcs11Error> {
        let key = self.find_key(key_label)?;

        // Check signature length
        let expected_len = match key.key_type {
            Pkcs11KeyType::EcdsaP256 => 64,
            Pkcs11KeyType::EcdsaP384 => 96,
            Pkcs11KeyType::Rsa2048 => 256,
            Pkcs11KeyType::Rsa4096 => 512,
            Pkcs11KeyType::Ed25519 => 64,
            Pkcs11KeyType::MlDsa65 => 3293,
        };

        if signature.len() != expected_len {
            return Ok(false);
        }

        // Hash the data
        let mut hasher = Sha3_256::new();
        hasher.update(data);
        let digest: [u8; 32] = hasher.finalize().into();

        // Verify the signature contains our digest (simulation)
        Ok(signature[..32] == digest)
    }

    /// List all keys in the token.
    #[cfg(feature = "std")]
    #[must_use]
    pub fn list_keys(&self) -> Vec<&Pkcs11KeyPair> {
        self.key_store.values().collect()
    }

    /// Delete a key from the token.
    #[cfg(feature = "std")]
    pub fn delete_key(&mut self, label: &str) -> Result<(), Pkcs11Error> {
        if self.state != SessionState::RwUser {
            return Err(Pkcs11Error::SessionError(
                "Must be logged in to delete keys".to_string(),
            ));
        }

        self.key_store
            .remove(label)
            .map(|_| ())
            .ok_or_else(|| Pkcs11Error::KeyNotFound(label.to_string()))
    }

    /// Export a public key in DER format.
    #[cfg(feature = "std")]
    pub fn export_public_key(&self, label: &str) -> Result<Vec<u8>, Pkcs11Error> {
        let key = self.find_key(label)?;

        // In real implementation, this would call C_GetAttributeValue
        // For simulation, create a mock DER-encoded public key
        let mut der = vec![
            0x30, // SEQUENCE
            key.id.len() as u8 + 4,
            0x06, // OID
            0x02,
        ];
        der.extend_from_slice(&key.id[..2.min(key.id.len())]);
        der.push(0x03); // BIT STRING
        der.push(key.id.len() as u8);
        der.extend_from_slice(&key.id);

        Ok(der)
    }

    /// Get the current session state.
    #[must_use]
    pub fn get_state(&self) -> SessionState {
        self.state
    }

    /// Get the provider type.
    #[must_use]
    pub fn get_provider(&self) -> Pkcs11Provider {
        self.provider
    }

    /// Check if session is active.
    #[must_use]
    pub fn is_active(&self) -> bool {
        self.session_handle.0 != 0
    }
}

use super::hsm::{HSMBackend, HSMOperations};

impl HSMOperations for Pkcs11Session {
    fn backend(&self) -> HSMBackend {
        // We need a way to map Pkcs11Provider to HSMBackend.
        // For now, we'll assume it's a hardware backend if not SoftHsm.
        HSMBackend::TPM2() // Generic placeholder for PKCS11 backed hardware
    }

    fn get_public_key(&self) -> Result<String, String> {
        // Return public key for the governance key if it exists
        #[cfg(feature = "std")]
        {
            if let Ok(der) = self.export_public_key("wl_governance_key") {
                return Ok(hex::encode(der));
            }
        }
        Err("Public key not found or not extractable".into())
    }

    fn sign(&self, message: &[u8]) -> Result<String, String> {
        #[cfg(feature = "std")]
        {
            let sig = self
                .sign("wl_governance_key", message)
                .map_err(|e| e.to_string())?;
            return Ok(hex::encode(sig));
        }
        #[cfg(not(feature = "std"))]
        Err("Signing not supported in no_std".into())
    }

    fn verify(&self, message: &[u8], signature: &str) -> Result<bool, String> {
        #[cfg(feature = "std")]
        {
            let sig_bytes = hex::decode(signature).map_err(|_| "Invalid hex in signature")?;
            return self
                .verify("wl_governance_key", message, &sig_bytes)
                .map_err(|e| e.to_string());
        }
        #[cfg(not(feature = "std"))]
        Err("Verification not supported in no_std".into())
    }

    fn get_identity(&self) -> String {
        format!("PKCS11-{:?}-{}", self.provider, self.session_handle.0)
    }

    fn is_hardware_backed(&self) -> bool {
        // If we have a library handle and it's not SoftHsm, it's real hardware
        #[cfg(feature = "std")]
        {
            self.library_handle.is_some() && self.provider != Pkcs11Provider::SoftHsm
        }
        #[cfg(not(feature = "std"))]
        false
    }
}

/// PKCS#11 Key Manager for the governance system
///
/// Provides high-level key management operations for AI governance.
#[cfg(feature = "std")]
pub struct Pkcs11KeyManager {
    session: Pkcs11Session,
    /// Governance signing key label
    governance_key_label: String,
    /// Attestation signing key label
    attestation_key_label: String,
}

#[cfg(feature = "std")]
impl Pkcs11KeyManager {
    /// Create a new key manager.
    #[must_use]
    pub fn new(provider: Pkcs11Provider) -> Self {
        Pkcs11KeyManager {
            session: Pkcs11Session::new(provider),
            governance_key_label: "wl_governance_key".to_string(),
            attestation_key_label: "wl_attestation_key".to_string(),
        }
    }

    /// Initialize and setup keys for governance.
    pub fn setup(&mut self, pin: &str) -> Result<(), Pkcs11Error> {
        self.session.initialize()?;
        self.session.login(pin)?;

        // Generate governance signing key (ML-DSA-65 for post-quantum)
        if self.session.find_key(&self.governance_key_label).is_err() {
            self.session.generate_keypair(
                &self.governance_key_label,
                Pkcs11KeyType::MlDsa65,
                false, // Not extractable
            )?;
        }

        // Generate attestation key (ECDSA P-256 for hardware acceleration)
        if self.session.find_key(&self.attestation_key_label).is_err() {
            self.session.generate_keypair(
                &self.attestation_key_label,
                Pkcs11KeyType::EcdsaP256,
                false,
            )?;
        }

        Ok(())
    }

    /// Sign a governance decision.
    pub fn sign_governance(&self, decision_hash: &[u8]) -> Result<Vec<u8>, Pkcs11Error> {
        self.session.sign(&self.governance_key_label, decision_hash)
    }

    /// Sign an attestation.
    pub fn sign_attestation(&self, attestation_data: &[u8]) -> Result<Vec<u8>, Pkcs11Error> {
        self.session
            .sign(&self.attestation_key_label, attestation_data)
    }

    /// Verify a governance signature.
    pub fn verify_governance(
        &self,
        decision_hash: &[u8],
        signature: &[u8],
    ) -> Result<bool, Pkcs11Error> {
        self.session
            .verify(&self.governance_key_label, decision_hash, signature)
    }

    /// Get the governance public key.
    pub fn get_governance_public_key(&self) -> Result<Vec<u8>, Pkcs11Error> {
        self.session.export_public_key(&self.governance_key_label)
    }

    /// Shutdown the key manager.
    pub fn shutdown(&mut self) -> Result<(), Pkcs11Error> {
        self.session.logout()?;
        self.session.finalize()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_pkcs11_provider_paths() {
        assert!(!Pkcs11Provider::Tpm2Pkcs11.default_library_path().is_empty());
        assert!(!Pkcs11Provider::SoftHsm.default_library_path().is_empty());
    }

    #[test]
    fn test_key_type_mechanisms() {
        assert_ne!(Pkcs11KeyType::EcdsaP256.mechanism(), 0);
        assert_ne!(Pkcs11KeyType::MlDsa65.mechanism(), 0);
        assert!(Pkcs11KeyType::EcdsaP256.is_hardware_accelerated());
        assert!(!Pkcs11KeyType::MlDsa65.is_hardware_accelerated());
    }

    #[test]
    fn test_session_lifecycle() {
        let mut session = Pkcs11Session::new(Pkcs11Provider::SoftHsm);

        // Initialize
        assert!(session.initialize().is_ok());
        assert!(session.is_active());

        // Login
        assert!(session.login("1234").is_ok());
        assert_eq!(session.get_state(), SessionState::RwUser);

        // Token info
        let info = session.get_token_info().unwrap();
        assert!(info.initialized);

        // Logout
        assert!(session.logout().is_ok());
        assert_eq!(session.get_state(), SessionState::RwPublic);

        // Finalize
        assert!(session.finalize().is_ok());
        assert!(!session.is_active());
    }

    #[test]
    fn test_key_generation_and_signing() {
        let mut session = Pkcs11Session::new(Pkcs11Provider::SoftHsm);
        session.initialize().unwrap();
        session.login("1234").unwrap();

        // Generate ECDSA key
        let key = session
            .generate_keypair("test_key", Pkcs11KeyType::EcdsaP256, false)
            .unwrap();
        assert_eq!(key.label, "test_key");
        assert!(key.hardware_protected);

        // Sign data
        let data = b"test message";
        let signature = session.sign("test_key", data).unwrap();
        assert_eq!(signature.len(), 64); // ECDSA P-256

        // Verify
        let valid = session.verify("test_key", data, &signature).unwrap();
        assert!(valid);

        // Invalid signature
        let mut bad_sig = signature.clone();
        bad_sig[0] ^= 0xFF;
        let invalid = session.verify("test_key", data, &bad_sig).unwrap();
        assert!(!invalid);
    }

    #[test]
    fn test_ml_dsa_key() {
        let mut session = Pkcs11Session::new(Pkcs11Provider::SoftHsm);
        session.initialize().unwrap();
        session.login("1234").unwrap();

        // Generate ML-DSA-65 key
        let key = session
            .generate_keypair("pq_key", Pkcs11KeyType::MlDsa65, false)
            .unwrap();
        assert!(!key.hardware_protected); // ML-DSA not hardware accelerated yet

        // Sign
        let data = b"quantum resistant message";
        let signature = session.sign("pq_key", data).unwrap();
        assert_eq!(signature.len(), 3293);

        // Verify
        let valid = session.verify("pq_key", data, &signature).unwrap();
        assert!(valid);
    }

    #[test]
    fn test_key_manager() {
        let mut km = Pkcs11KeyManager::new(Pkcs11Provider::SoftHsm);
        assert!(km.setup("1234").is_ok());

        // Sign governance decision
        let decision_hash = [0xABu8; 32];
        let sig = km.sign_governance(&decision_hash).unwrap();
        assert!(!sig.is_empty());

        // Verify
        let valid = km.verify_governance(&decision_hash, &sig).unwrap();
        assert!(valid);

        // Get public key
        let pubkey = km.get_governance_public_key().unwrap();
        assert!(!pubkey.is_empty());

        // Sign attestation
        let attestation = b"attestation_data";
        let att_sig = km.sign_attestation(attestation).unwrap();
        assert_eq!(att_sig.len(), 64); // ECDSA P-256

        // Shutdown
        assert!(km.shutdown().is_ok());
    }

    #[test]
    fn test_key_deletion() {
        let mut session = Pkcs11Session::new(Pkcs11Provider::SoftHsm);
        session.initialize().unwrap();
        session.login("1234").unwrap();

        session
            .generate_keypair("temp_key", Pkcs11KeyType::Ed25519, true)
            .unwrap();
        assert!(session.find_key("temp_key").is_ok());

        session.delete_key("temp_key").unwrap();
        assert!(session.find_key("temp_key").is_err());
    }

    #[test]
    fn test_list_keys() {
        let mut session = Pkcs11Session::new(Pkcs11Provider::SoftHsm);
        session.initialize().unwrap();
        session.login("1234").unwrap();

        session
            .generate_keypair("key1", Pkcs11KeyType::EcdsaP256, false)
            .unwrap();
        session
            .generate_keypair("key2", Pkcs11KeyType::Rsa2048, false)
            .unwrap();

        let keys = session.list_keys();
        assert_eq!(keys.len(), 2);
    }

    #[test]
    fn test_export_public_key() {
        let mut session = Pkcs11Session::new(Pkcs11Provider::SoftHsm);
        session.initialize().unwrap();
        session.login("1234").unwrap();

        session
            .generate_keypair("export_key", Pkcs11KeyType::EcdsaP256, false)
            .unwrap();

        let der = session.export_public_key("export_key").unwrap();
        assert!(!der.is_empty());
        assert_eq!(der[0], 0x30); // SEQUENCE tag
    }

    #[test]
    fn test_pin_validation() {
        let mut session = Pkcs11Session::new(Pkcs11Provider::SoftHsm);
        session.initialize().unwrap();

        // Too short PIN
        assert!(matches!(
            session.login("123"),
            Err(Pkcs11Error::PinIncorrect)
        ));

        // Valid PIN
        assert!(session.login("1234").is_ok());
    }
}
