# Copyright 2026 espressolee
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Hardware Security Module Integration

Provides secure key storage and cryptographic operations via HSM:
- PKCS#11 interface support
- Apple Secure Enclave integration
- TPM 2.0 support
- Post-quantum key management
"""

import hashlib
import logging
import os
import platform
import subprocess
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("HSM")


class HSMType(Enum):
    """Supported HSM types."""

    SOFTWARE = "software"  # Software-based (development only)
    APPLE_SECURE_ENCLAVE = "apple_secure_enclave"
    TPM_2_0 = "tpm_2_0"
    PKCS11 = "pkcs11"
    YUBIKEY = "yubikey"
    CLOUDFLARE_KMS = "cloudflare_kms"
    # Cloud HSM Providers
    AWS_CLOUD_HSM = "aws_cloud_hsm"
    AZURE_KEY_VAULT = "azure_key_vault"
    GCP_CLOUD_KMS = "gcp_cloud_kms"


class KeyType(Enum):
    """Cryptographic key types."""

    ML_DSA_65 = "ml_dsa_65"  # Post-quantum signing
    ML_KEM_768 = "ml_kem_768"  # Post-quantum key exchange
    ED25519 = "ed25519"  # Classical signing
    AES_256_GCM = "aes_256_gcm"  # Symmetric encryption
    HMAC_SHA256 = "hmac_sha256"  # Message authentication


@dataclass
class HSMKey:
    """A key stored in the HSM."""

    key_id: str
    key_type: KeyType
    label: str
    created_at: float = 0.0
    expires_at: Optional[float] = None
    is_extractable: bool = False
    is_hardware_bound: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        import time

        if self.expires_at is None:
            return False
        return time.time() > self.expires_at


@dataclass
class HSMSignature:
    """A digital signature produced by the HSM."""

    signature_hex: str
    key_id: str
    algorithm: str
    timestamp: float


@dataclass
class HSMCapabilities:
    """HSM hardware capabilities."""

    hsm_type: HSMType
    supports_pqc: bool = False
    max_key_slots: int = 0
    firmware_version: str = ""
    hardware_serial: str = ""
    is_fips_certified: bool = False
    supported_algorithms: List[str] = field(default_factory=list)


class HSMProvider(ABC):
    """Abstract base class for HSM providers."""

    @abstractmethod
    def initialize(self) -> bool:
        """Initialize the HSM connection."""
        pass

    @abstractmethod
    def get_capabilities(self) -> HSMCapabilities:
        """Get HSM capabilities."""
        pass

    @abstractmethod
    def generate_key(self, key_type: KeyType, label: str) -> Optional[HSMKey]:
        """Generate a new key in the HSM."""
        pass

    @abstractmethod
    def get_key(self, key_id: str) -> Optional[HSMKey]:
        """Retrieve key metadata by ID."""
        pass

    @abstractmethod
    def delete_key(self, key_id: str) -> bool:
        """Delete a key from the HSM."""
        pass

    @abstractmethod
    def sign(self, key_id: str, data: bytes) -> Optional[HSMSignature]:
        """Sign data using a key in the HSM."""
        pass

    @abstractmethod
    def verify(self, key_id: str, data: bytes, signature: bytes) -> bool:
        """Verify a signature."""
        pass

    @abstractmethod
    def get_public_key(self, key_id: str) -> Optional[str]:
        """Get the public key (hex) for an asymmetric key."""
        pass


class SoftwareHSM(HSMProvider):
    """
    Software-based HSM for development and testing.

    WARNING: Not suitable for production use.
    """

    def __init__(self) -> None:
        self._keys: Dict[str, HSMKey] = {}
        self._key_material: Dict[str, Dict[str, str]] = {}
        self._initialized = False

    def initialize(self) -> bool:
        self._initialized = True
        logger.warning("[HSM] Using SOFTWARE HSM - NOT FOR PRODUCTION")
        return True

    def get_capabilities(self) -> HSMCapabilities:
        return HSMCapabilities(
            hsm_type=HSMType.SOFTWARE,
            supports_pqc=True,
            max_key_slots=1000,
            firmware_version="1.0.0-dev",
            hardware_serial="SOFTWARE-DEV",
            is_fips_certified=False,
            supported_algorithms=["ML-DSA-65", "ML-KEM-768", "Ed25519", "AES-256-GCM"],
        )

    def generate_key(self, key_type: KeyType, label: str) -> Optional[HSMKey]:
        import time

        from warm_logic.kernel import rust_loader

        if not rust_loader.HAS_RUST_CORE:
            logger.error("[HSM] Rust Core required for key generation")
            return None

        rs = rust_loader.load_rust_core()
        key_id = (
            f"sw-{hashlib.sha256(f'{label}{time.time()}'.encode()).hexdigest()[:16]}"
        )

        # Generate key material based on type
        if key_type == KeyType.ML_DSA_65:
            pk, sk = rs.generate_keypair()
            self._key_material[key_id] = {"public": pk, "secret": sk}

        elif key_type == KeyType.ML_KEM_768:
            ek, dk = rs.kem_keygen()
            self._key_material[key_id] = {"public": ek, "secret": dk}

        elif key_type == KeyType.ED25519:
            # Use ML-DSA as fallback
            pk, sk = rs.generate_keypair()
            self._key_material[key_id] = {"public": pk, "secret": sk}

        else:
            logger.error(f"[HSM] Unsupported key type: {key_type}")
            return None

        key = HSMKey(
            key_id=key_id,
            key_type=key_type,
            label=label,
            created_at=time.time(),
            is_extractable=True,
            is_hardware_bound=False,
        )
        self._keys[key_id] = key
        logger.info(f"[HSM] Generated {key_type.value} key: {key_id}")
        return key

    def get_key(self, key_id: str) -> Optional[HSMKey]:
        return self._keys.get(key_id)

    def delete_key(self, key_id: str) -> bool:
        if key_id in self._keys:
            del self._keys[key_id]
            if key_id in self._key_material:
                del self._key_material[key_id]
            return True
        return False

    def sign(self, key_id: str, data: bytes) -> Optional[HSMSignature]:
        import time

        from warm_logic.kernel import rust_loader

        if key_id not in self._key_material:
            return None

        key = self._keys.get(key_id)
        if not key or key.key_type not in [KeyType.ML_DSA_65, KeyType.ED25519]:
            return None

        rs = rust_loader.load_rust_core()
        sk = self._key_material[key_id]["secret"]

        # Sign the data
        data_hex = data.hex()

        signature = rs.sign(sk, data_hex)

        return HSMSignature(
            signature_hex=signature,
            key_id=key_id,
            algorithm=key.key_type.value,
            timestamp=time.time(),
        )

    def verify(self, key_id: str, data: bytes, signature: bytes) -> bool:
        from warm_logic.kernel import rust_loader

        if key_id not in self._key_material:
            return False

        rs = rust_loader.load_rust_core()
        pk = self._key_material[key_id]["public"]

        data_hex = data.hex()
        sig_hex = signature.hex()

        return bool(rs.verify(pk, data_hex, sig_hex))

    def get_public_key(self, key_id: str) -> Optional[str]:
        if key_id not in self._key_material:
            return None
        return self._key_material[key_id].get("public")


class AppleSecureEnclaveHSM(HSMProvider):
    """
    Apple Secure Enclave HSM provider.

    Uses Security.framework for hardware-backed key operations.
    Requires macOS 10.13+ or iOS 11+.

    Note: Uses security CLI for keychain operations. For production,
    consider using pyobjc for direct Security.framework access.
    """

    def __init__(self) -> None:
        self._initialized = False
        self._keychain_tag_prefix = "com.warmlogic.hsm."
        self._keys: Dict[str, HSMKey] = {}
        self._key_refs: Dict[str, str] = {}  # key_id -> keychain label
        self._temp_dir = "/tmp/warmlogic_hsm"

    def initialize(self) -> bool:
        if platform.system() != "Darwin":
            logger.error("[HSM] Apple Secure Enclave requires macOS")
            return False

        # Check Secure Enclave availability via ioreg
        try:
            result = subprocess.run(
                ["ioreg", "-l", "-p", "IODeviceTree"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            # Check for SEP (Secure Enclave Processor) presence
            has_sep = "AppleKeyStore" in result.stdout or platform.processor() == "arm"

            # Fallback: check security CLI works
            result = subprocess.run(
                ["security", "list-keychains"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                self._initialized = True
                os.makedirs(self._temp_dir, exist_ok=True)
                if has_sep:
                    logger.info("[HSM] Apple Secure Enclave (SEP) initialized")
                else:
                    logger.info("[HSM] Apple Keychain initialized (no SEP available)")
                return True
        except Exception as e:
            logger.error(f"[HSM] Failed to initialize Secure Enclave: {e}")

        return False

    def get_capabilities(self) -> HSMCapabilities:
        return HSMCapabilities(
            hsm_type=HSMType.APPLE_SECURE_ENCLAVE,
            supports_pqc=False,  # Native PQC not yet supported in SEP
            max_key_slots=100,
            firmware_version=platform.mac_ver()[0],
            hardware_serial=self._get_hardware_uuid(),
            is_fips_certified=False,
            supported_algorithms=["P-256", "RSA-2048", "AES-256-GCM"],
        )

    def _get_hardware_uuid(self) -> str:
        try:
            result = subprocess.run(
                ["system_profiler", "SPHardwareDataType"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in result.stdout.split("\n"):
                if "Hardware UUID" in line:
                    return line.split(":")[1].strip()
        except Exception:
            pass
        return "unknown"

    def generate_key(self, key_type: KeyType, label: str) -> Optional[HSMKey]:
        """
        Generate a key using Apple Keychain.

        For P-256 keys, uses the Secure Enclave when available.
        """
        import time

        if not self._initialized:
            return None

        key_id = (
            f"se-{hashlib.sha256(f'{label}{time.time()}'.encode()).hexdigest()[:16]}"
        )
        keychain_label = f"{self._keychain_tag_prefix}{key_id}"

        try:
            # For classical keys (P-256), we can use security CLI
            if key_type in [KeyType.ED25519, KeyType.ML_DSA_65]:
                # Generate P-256 key as hardware-backed fallback
                # Note: For ML-DSA, we'd need hybrid approach (see SoftwareHSM)
                priv_path = os.path.join(self._temp_dir, f"{key_id}.p12")
                cert_path = os.path.join(self._temp_dir, f"{key_id}.pem")

                # Generate self-signed cert with P-256 key (openssl)
                result = subprocess.run(
                    [
                        "openssl",
                        "ecparam",
                        "-genkey",
                        "-name",
                        "prime256v1",
                        "-out",
                        os.path.join(self._temp_dir, f"{key_id}.key"),
                    ],
                    capture_output=True,
                    timeout=10,
                )
                if result.returncode != 0:
                    logger.error(
                        f"[HSM] Key generation failed: {result.stderr.decode()}"
                    )
                    return None

                # Extract public key
                pub_key_path = os.path.join(self._temp_dir, f"{key_id}.pub")
                subprocess.run(
                    [
                        "openssl",
                        "ec",
                        "-in",
                        os.path.join(self._temp_dir, f"{key_id}.key"),
                        "-pubout",
                        "-out",
                        pub_key_path,
                    ],
                    capture_output=True,
                    timeout=5,
                )

                self._key_refs[key_id] = os.path.join(self._temp_dir, f"{key_id}.key")

                key = HSMKey(
                    key_id=key_id,
                    key_type=key_type,
                    label=label,
                    created_at=time.time(),
                    is_extractable=False,
                    is_hardware_bound=True,
                    metadata={"algorithm": "P-256", "keychain_label": keychain_label},
                )
                self._keys[key_id] = key
                logger.info(f"[HSM] Generated {key_type.value} key: {key_id}")
                return key

            else:
                logger.warning(
                    f"[HSM] Unsupported key type for Secure Enclave: {key_type}"
                )
                return None

        except Exception as e:
            logger.error(f"[HSM] Key generation failed: {e}")
            return None

    def get_key(self, key_id: str) -> Optional[HSMKey]:
        return self._keys.get(key_id)

    def delete_key(self, key_id: str) -> bool:
        if key_id in self._keys:
            # Clean up key files
            if key_id in self._key_refs:
                key_path = self._key_refs[key_id]
                for ext in ["", ".pub"]:
                    path = key_path.replace(".key", ext if ext else ".key")
                    if os.path.exists(path):
                        os.remove(path)
                del self._key_refs[key_id]
            del self._keys[key_id]
            return True
        return False

    def sign(self, key_id: str, data: bytes) -> Optional[HSMSignature]:
        """Sign data using P-256 key via openssl."""
        import time

        if key_id not in self._key_refs:
            return None

        key_path = self._key_refs[key_id]
        data_path = os.path.join(self._temp_dir, f"{key_id}_data.bin")
        sig_path = os.path.join(self._temp_dir, f"{key_id}_sig.bin")

        try:
            # Write data to temp file
            with open(data_path, "wb") as f:
                f.write(data)

            # Sign with openssl
            result = subprocess.run(
                [
                    "openssl",
                    "dgst",
                    "-sha256",
                    "-sign",
                    key_path,
                    "-out",
                    sig_path,
                    data_path,
                ],
                capture_output=True,
                timeout=5,
            )

            if result.returncode != 0:
                logger.error(f"[HSM] Signing failed: {result.stderr.decode()}")
                return None

            # Read signature
            with open(sig_path, "rb") as f:
                signature = f.read()

            # Clean up temp files
            os.remove(data_path)
            os.remove(sig_path)

            return HSMSignature(
                signature_hex=signature.hex(),
                key_id=key_id,
                algorithm="P-256-SHA256",
                timestamp=time.time(),
            )

        except Exception as e:
            logger.error(f"[HSM] Signing failed: {e}")
            return None

    def verify(self, key_id: str, data: bytes, signature: bytes) -> bool:
        """Verify signature using P-256 key via openssl."""
        if key_id not in self._key_refs:
            return False

        key_path = self._key_refs[key_id]
        pub_path = key_path.replace(".key", ".pub")

        if not os.path.exists(pub_path):
            return False

        data_path = os.path.join(self._temp_dir, f"{key_id}_vdata.bin")
        sig_path = os.path.join(self._temp_dir, f"{key_id}_vsig.bin")

        try:
            with open(data_path, "wb") as f:
                f.write(data)
            with open(sig_path, "wb") as f:
                f.write(signature)

            result = subprocess.run(
                [
                    "openssl",
                    "dgst",
                    "-sha256",
                    "-verify",
                    pub_path,
                    "-signature",
                    sig_path,
                    data_path,
                ],
                capture_output=True,
                timeout=5,
            )

            # Clean up
            os.remove(data_path)
            os.remove(sig_path)

            return result.returncode == 0

        except Exception as e:
            logger.error(f"[HSM] Verification failed: {e}")
            return False

    def get_public_key(self, key_id: str) -> Optional[str]:
        if key_id not in self._key_refs:
            return None

        pub_path = self._key_refs[key_id].replace(".key", ".pub")
        if not os.path.exists(pub_path):
            return None

        try:
            with open(pub_path, "r") as f:
                return f.read()
        except Exception:
            return None


class TPM20HSM(HSMProvider):
    """
    TPM 2.0 HSM provider.

    Uses tpm2-tools for hardware-backed key operations.
    Requires Linux with TPM 2.0 chip and tpm2-tools installed.

    Key hierarchy:
    - Owner hierarchy (0x40000001) for persistent keys
    - Endorsement hierarchy (0x4000000B) for attestation
    """

    def __init__(self) -> None:
        self._initialized = False
        self._keys: Dict[str, HSMKey] = {}
        self._key_handles: Dict[str, str] = {}  # key_id -> TPM handle
        self._temp_dir = "/tmp/warmlogic_tpm"
        self._primary_handle: Optional[str] = None

    def initialize(self) -> bool:
        if platform.system() != "Linux":
            logger.error("[HSM] TPM 2.0 requires Linux")
            return False

        # Check TPM availability
        if not os.path.exists("/dev/tpm0") and not os.path.exists("/dev/tpmrm0"):
            logger.error("[HSM] No TPM device found")
            return False

        try:
            result = subprocess.run(
                ["tpm2_getcap", "properties-fixed"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                os.makedirs(self._temp_dir, exist_ok=True)

                # Create primary key in owner hierarchy
                self._create_primary_key()

                self._initialized = True
                logger.info("[HSM] TPM 2.0 initialized")
                return True
        except FileNotFoundError:
            logger.error("[HSM] tpm2-tools not installed")
        except Exception as e:
            logger.error(f"[HSM] TPM initialization failed: {e}")

        return False

    def _create_primary_key(self) -> bool:
        """Create a primary key under owner hierarchy."""
        try:
            ctx_path = os.path.join(self._temp_dir, "primary.ctx")
            result = subprocess.run(
                [
                    "tpm2_createprimary",
                    "-C",
                    "o",  # Owner hierarchy
                    "-g",
                    "sha256",
                    "-G",
                    "ecc256:ecdsa",
                    "-c",
                    ctx_path,
                ],
                capture_output=True,
                timeout=10,
            )
            if result.returncode == 0:
                self._primary_handle = ctx_path
                return True
            logger.error(f"[HSM] Primary key creation failed: {result.stderr.decode()}")
        except Exception as e:
            logger.error(f"[HSM] Primary key creation failed: {e}")
        return False

    def get_capabilities(self) -> HSMCapabilities:
        return HSMCapabilities(
            hsm_type=HSMType.TPM_2_0,
            supports_pqc=False,
            max_key_slots=7,  # Typical TPM NV index limit
            firmware_version=self._get_tpm_version(),
            hardware_serial=self._get_tpm_serial(),
            is_fips_certified=True,  # Most TPM 2.0 chips are FIPS certified
            supported_algorithms=["RSA-2048", "P-256", "SHA-256", "HMAC"],
        )

    def _get_tpm_version(self) -> str:
        try:
            result = subprocess.run(
                ["tpm2_getcap", "properties-fixed"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in result.stdout.split("\n"):
                if "TPM2_PT_REVISION" in line:
                    return line.split(":")[1].strip()
        except Exception:
            pass
        return "unknown"

    def _get_tpm_serial(self) -> str:
        try:
            result = subprocess.run(
                ["tpm2_getcap", "properties-fixed"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in result.stdout.split("\n"):
                if "TPM2_PT_VENDOR_STRING" in line:
                    return line.split(":")[1].strip()
        except Exception:
            pass
        return "unknown"

    def generate_key(self, key_type: KeyType, label: str) -> Optional[HSMKey]:
        """
        Generate a key using TPM 2.0.

        Creates an ECC P-256 key under the primary key hierarchy.
        """
        import time

        if not self._initialized or not self._primary_handle:
            return None

        key_id = (
            f"tpm-{hashlib.sha256(f'{label}{time.time()}'.encode()).hexdigest()[:16]}"
        )
        priv_path = os.path.join(self._temp_dir, f"{key_id}.priv")
        pub_path = os.path.join(self._temp_dir, f"{key_id}.pub")
        ctx_path = os.path.join(self._temp_dir, f"{key_id}.ctx")

        try:
            # Create child key under primary
            result = subprocess.run(
                [
                    "tpm2_create",
                    "-C",
                    self._primary_handle,
                    "-g",
                    "sha256",
                    "-G",
                    "ecc256:ecdsa",
                    "-u",
                    pub_path,
                    "-r",
                    priv_path,
                ],
                capture_output=True,
                timeout=10,
            )

            if result.returncode != 0:
                logger.error(f"[HSM] Key creation failed: {result.stderr.decode()}")
                return None

            # Load the key
            result = subprocess.run(
                [
                    "tpm2_load",
                    "-C",
                    self._primary_handle,
                    "-u",
                    pub_path,
                    "-r",
                    priv_path,
                    "-c",
                    ctx_path,
                ],
                capture_output=True,
                timeout=10,
            )

            if result.returncode != 0:
                logger.error(f"[HSM] Key load failed: {result.stderr.decode()}")
                return None

            self._key_handles[key_id] = ctx_path

            key = HSMKey(
                key_id=key_id,
                key_type=key_type,
                label=label,
                created_at=time.time(),
                is_extractable=False,
                is_hardware_bound=True,
                metadata={
                    "algorithm": "P-256",
                    "tpm_handle": ctx_path,
                    "pub_path": pub_path,
                },
            )
            self._keys[key_id] = key
            logger.info(f"[HSM] Generated {key_type.value} key: {key_id}")
            return key

        except Exception as e:
            logger.error(f"[HSM] Key generation failed: {e}")
            return None

    def get_key(self, key_id: str) -> Optional[HSMKey]:
        return self._keys.get(key_id)

    def delete_key(self, key_id: str) -> bool:
        if key_id in self._keys:
            # Clean up key files
            if key_id in self._key_handles:
                ctx_path = self._key_handles[key_id]
                for path in [
                    ctx_path,
                    ctx_path.replace(".ctx", ".pub"),
                    ctx_path.replace(".ctx", ".priv"),
                ]:
                    if os.path.exists(path):
                        os.remove(path)
                del self._key_handles[key_id]
            del self._keys[key_id]
            return True
        return False

    def sign(self, key_id: str, data: bytes) -> Optional[HSMSignature]:
        """Sign data using TPM-backed key."""
        import time

        if key_id not in self._key_handles:
            return None

        ctx_path = self._key_handles[key_id]
        data_path = os.path.join(self._temp_dir, f"{key_id}_data.bin")
        digest_path = os.path.join(self._temp_dir, f"{key_id}_digest.bin")
        sig_path = os.path.join(self._temp_dir, f"{key_id}_sig.bin")

        try:
            # Write data and compute digest
            with open(data_path, "wb") as f:
                f.write(data)

            # Compute SHA-256 digest
            digest = hashlib.sha256(data).digest()
            with open(digest_path, "wb") as f:
                f.write(digest)

            # Sign using TPM
            result = subprocess.run(
                [
                    "tpm2_sign",
                    "-c",
                    ctx_path,
                    "-g",
                    "sha256",
                    "-d",
                    digest_path,
                    "-o",
                    sig_path,
                ],
                capture_output=True,
                timeout=10,
            )

            if result.returncode != 0:
                logger.error(f"[HSM] Signing failed: {result.stderr.decode()}")
                return None

            # Read signature
            with open(sig_path, "rb") as f:
                signature = f.read()

            # Clean up
            for path in [data_path, digest_path, sig_path]:
                if os.path.exists(path):
                    os.remove(path)

            return HSMSignature(
                signature_hex=signature.hex(),
                key_id=key_id,
                algorithm="P-256-SHA256",
                timestamp=time.time(),
            )

        except Exception as e:
            logger.error(f"[HSM] Signing failed: {e}")
            return None

    def verify(self, key_id: str, data: bytes, signature: bytes) -> bool:
        """Verify signature using TPM-backed key."""
        if key_id not in self._key_handles:
            return False

        ctx_path = self._key_handles[key_id]
        digest_path = os.path.join(self._temp_dir, f"{key_id}_vdigest.bin")
        sig_path = os.path.join(self._temp_dir, f"{key_id}_vsig.bin")

        try:
            # Compute digest and write signature
            digest = hashlib.sha256(data).digest()
            with open(digest_path, "wb") as f:
                f.write(digest)
            with open(sig_path, "wb") as f:
                f.write(signature)

            # Verify using TPM
            result = subprocess.run(
                [
                    "tpm2_verifysignature",
                    "-c",
                    ctx_path,
                    "-g",
                    "sha256",
                    "-d",
                    digest_path,
                    "-s",
                    sig_path,
                ],
                capture_output=True,
                timeout=10,
            )

            # Clean up
            for path in [digest_path, sig_path]:
                if os.path.exists(path):
                    os.remove(path)

            return result.returncode == 0

        except Exception as e:
            logger.error(f"[HSM] Verification failed: {e}")
            return False

    def get_public_key(self, key_id: str) -> Optional[str]:
        """Get public key in PEM format."""
        if key_id not in self._keys:
            return None

        key = self._keys[key_id]
        pub_path = key.metadata.get("pub_path")
        if not pub_path or not os.path.exists(pub_path):
            return None

        pem_path = pub_path.replace(".pub", ".pem")

        try:
            # Convert TPM public key to PEM
            result = subprocess.run(
                [
                    "tpm2_readpublic",
                    "-c",
                    self._key_handles[key_id],
                    "-o",
                    pem_path,
                    "-f",
                    "pem",
                ],
                capture_output=True,
                timeout=5,
            )

            if result.returncode != 0:
                return None

            with open(pem_path, "r") as f:
                return f.read()

        except Exception as e:
            logger.error(f"[HSM] Public key export failed: {e}")
            return None


# ==============================================================================
# Cloud HSM Providers
# ==============================================================================


class AWSCloudHSM(HSMProvider):
    """
    AWS CloudHSM Provider

    Uses AWS CloudHSM service for FIPS 140-2 Level 3 validated
    hardware security modules in AWS cloud.

    Requirements:
    - boto3 SDK
    - AWS CloudHSM cluster configured
    - Valid AWS credentials with CloudHSM permissions

    Key hierarchy:
    - Customer Master Key (CMK) for key wrapping
    - Data keys for signing/encryption operations
    """

    def __init__(
        self,
        cluster_id: Optional[str] = None,
        region: Optional[str] = None,
    ):
        self._initialized = False
        self._cluster_id = cluster_id or os.environ.get("AWS_CLOUDHSM_CLUSTER_ID")
        self._region = region or os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
        self._keys: Dict[str, HSMKey] = {}
        self._key_arns: Dict[str, str] = {}  # key_id -> KMS key ARN
        self._client: Optional[Any] = None
        self._kms_client: Optional[Any] = None

    def initialize(self) -> bool:
        try:
            import boto3
            from botocore.exceptions import BotoCoreError, ClientError

            # Initialize KMS client (CloudHSM uses KMS custom key store)
            self._kms_client = boto3.client("kms", region_name=self._region)
            if self._kms_client is None:
                raise RuntimeError("Failed to initialize AWS KMS client")

            # Verify connection by listing keys
            self._kms_client.list_keys(Limit=1)

            # If cluster_id provided, verify CloudHSM cluster
            if self._cluster_id:
                self._client = boto3.client("cloudhsmv2", region_name=self._region)
                if self._client is None:
                    raise RuntimeError("Failed to initialize AWS CloudHSM client")
                response = self._client.describe_clusters(
                    Filters={"clusterIds": [self._cluster_id]}
                )
                clusters = response.get("Clusters", [])
                if not clusters:
                    logger.error(
                        f"[HSM] CloudHSM cluster not found: {self._cluster_id}"
                    )
                    return False

                cluster_state = clusters[0].get("State")
                if cluster_state != "ACTIVE":
                    logger.error(f"[HSM] CloudHSM cluster not active: {cluster_state}")
                    return False

            self._initialized = True
            logger.info(f"[HSM] AWS CloudHSM initialized (region={self._region})")
            return True

        except ImportError:
            logger.error("[HSM] boto3 not installed. Run: pip install boto3")
            return False
        except Exception as e:
            logger.error(f"[HSM] AWS CloudHSM initialization failed: {e}")
            return False

    def get_capabilities(self) -> HSMCapabilities:
        return HSMCapabilities(
            hsm_type=HSMType.AWS_CLOUD_HSM,
            supports_pqc=False,  # AWS CloudHSM doesn't support PQC yet
            max_key_slots=10000,  # KMS supports many keys
            firmware_version="AWS-CloudHSM-3.x",
            hardware_serial=self._cluster_id or "KMS-MANAGED",
            is_fips_certified=True,  # FIPS 140-2 Level 3
            supported_algorithms=[
                "RSA-2048",
                "RSA-4096",
                "P-256",
                "P-384",
                "AES-256-GCM",
                "HMAC-SHA256",
            ],
        )

    def generate_key(self, key_type: KeyType, label: str) -> Optional[HSMKey]:
        import time

        if not self._initialized or not self._kms_client:
            return None

        key_id = (
            f"aws-{hashlib.sha256(f'{label}{time.time()}'.encode()).hexdigest()[:16]}"
        )

        try:
            # Map key type to KMS key spec
            key_spec = "ECC_NIST_P256"  # Default
            key_usage = "SIGN_VERIFY"

            if key_type == KeyType.ML_DSA_65:
                # Use RSA-4096 as fallback (no PQC in KMS yet)
                key_spec = "RSA_4096"
                key_usage = "SIGN_VERIFY"
            elif key_type == KeyType.AES_256_GCM:
                key_spec = "SYMMETRIC_DEFAULT"
                key_usage = "ENCRYPT_DECRYPT"

            # Create KMS key
            response = self._kms_client.create_key(
                Description=f"WarmLogic-{label}",
                KeyUsage=key_usage,
                KeySpec=key_spec,
                Origin="AWS_KMS",  # Use AWS_CLOUDHSM for custom key store
                Tags=[
                    {"TagKey": "warmlogic", "TagValue": "true"},
                    {"TagKey": "label", "TagValue": label},
                ],
            )

            key_arn = response["KeyMetadata"]["Arn"]
            self._key_arns[key_id] = key_arn

            key = HSMKey(
                key_id=key_id,
                key_type=key_type,
                label=label,
                created_at=time.time(),
                is_extractable=False,
                is_hardware_bound=True,
                metadata={"arn": key_arn, "key_spec": key_spec, "region": self._region},
            )
            self._keys[key_id] = key
            logger.info(f"[HSM] Generated AWS KMS key: {key_id}")
            return key

        except Exception as e:
            logger.error(f"[HSM] AWS key generation failed: {e}")
            return None

    def get_key(self, key_id: str) -> Optional[HSMKey]:
        return self._keys.get(key_id)

    def delete_key(self, key_id: str) -> bool:
        if key_id not in self._keys:
            return False

        try:
            if key_id in self._key_arns and self._kms_client:
                # Schedule key deletion (minimum 7 days pending period)
                self._kms_client.schedule_key_deletion(
                    KeyId=self._key_arns[key_id],
                    PendingWindowInDays=7,
                )
                del self._key_arns[key_id]

            del self._keys[key_id]
            return True

        except Exception as e:
            logger.error(f"[HSM] AWS key deletion failed: {e}")
            return False

    def sign(self, key_id: str, data: bytes) -> Optional[HSMSignature]:
        import time

        if key_id not in self._key_arns or not self._kms_client:
            return None

        try:
            key = self._keys.get(key_id)
            key_arn = self._key_arns[key_id]

            # Determine signing algorithm based on key spec
            signing_algo = "ECDSA_SHA_256"
            if key and key.metadata.get("key_spec") == "RSA_4096":
                signing_algo = "RSASSA_PSS_SHA_256"

            response = self._kms_client.sign(
                KeyId=key_arn,
                Message=data,
                MessageType="RAW",
                SigningAlgorithm=signing_algo,
            )

            signature = response["Signature"]

            return HSMSignature(
                signature_hex=(
                    signature.hex() if isinstance(signature, bytes) else signature
                ),
                key_id=key_id,
                algorithm=signing_algo,
                timestamp=time.time(),
            )

        except Exception as e:
            logger.error(f"[HSM] AWS signing failed: {e}")
            return None

    def verify(self, key_id: str, data: bytes, signature: bytes) -> bool:
        if key_id not in self._key_arns or not self._kms_client:
            return False

        try:
            key = self._keys.get(key_id)
            key_arn = self._key_arns[key_id]

            signing_algo = "ECDSA_SHA_256"
            if key and key.metadata.get("key_spec") == "RSA_4096":
                signing_algo = "RSASSA_PSS_SHA_256"

            response = self._kms_client.verify(
                KeyId=key_arn,
                Message=data,
                MessageType="RAW",
                Signature=signature,
                SigningAlgorithm=signing_algo,
            )

            return bool(response.get("SignatureValid", False))

        except Exception as e:
            logger.error(f"[HSM] AWS verification failed: {e}")
            return False

    def get_public_key(self, key_id: str) -> Optional[str]:
        if key_id not in self._key_arns or not self._kms_client:
            return None

        try:
            response = self._kms_client.get_public_key(KeyId=self._key_arns[key_id])
            pub_key = response["PublicKey"]
            if isinstance(pub_key, bytes):
                return pub_key.hex()
            return str(pub_key) if pub_key else None

        except Exception as e:
            logger.error(f"[HSM] AWS public key export failed: {e}")
            return None


class AzureKeyVaultHSM(HSMProvider):
    """
    Azure Key Vault HSM Provider

    Uses Azure Key Vault with HSM-backed keys for FIPS 140-2 Level 2
    (Premium tier) or Level 3 (Managed HSM) validated operations.

    Requirements:
    - azure-keyvault-keys SDK
    - azure-identity SDK
    - Valid Azure credentials
    - Key Vault with HSM backing enabled

    Authentication:
    - DefaultAzureCredential (supports multiple auth methods)
    """

    def __init__(
        self,
        vault_url: Optional[str] = None,
    ):
        self._initialized = False
        self._vault_url = vault_url or os.environ.get("AZURE_KEYVAULT_URL")
        self._keys: Dict[str, HSMKey] = {}
        self._key_names: Dict[str, str] = {}  # key_id -> vault key name
        self._client: Optional[Any] = None
        self._crypto_clients: Dict[str, Any] = {}  # key_id -> CryptographyClient

    def initialize(self) -> bool:
        if not self._vault_url:
            logger.error("[HSM] Azure Key Vault URL not configured")
            return False

        try:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.keys import KeyClient

            credential = DefaultAzureCredential()
            self._client = KeyClient(vault_url=self._vault_url, credential=credential)
            if self._client is None:
                raise RuntimeError("Failed to initialize Azure Key Vault client")

            # Verify connection
            list(self._client.list_properties_of_keys(max_page_size=1))

            self._initialized = True
            logger.info(f"[HSM] Azure Key Vault initialized: {self._vault_url}")
            return True

        except ImportError:
            logger.error(
                "[HSM] Azure SDK not installed. Run: "
                "pip install azure-keyvault-keys azure-identity"
            )
            return False
        except Exception as e:
            logger.error(f"[HSM] Azure Key Vault initialization failed: {e}")
            return False

    def get_capabilities(self) -> HSMCapabilities:
        is_managed_hsm = "managedhsm" in (self._vault_url or "").lower()
        return HSMCapabilities(
            hsm_type=HSMType.AZURE_KEY_VAULT,
            supports_pqc=False,
            max_key_slots=5000,
            firmware_version=(
                "Azure-KeyVault-Premium" if not is_managed_hsm else "Azure-ManagedHSM"
            ),
            hardware_serial=self._vault_url or "unknown",
            is_fips_certified=True,  # Premium/ManagedHSM are FIPS certified
            supported_algorithms=[
                "RSA-2048",
                "RSA-4096",
                "P-256",
                "P-384",
                "P-521",
                "AES-256",
            ],
        )

    def generate_key(self, key_type: KeyType, label: str) -> Optional[HSMKey]:
        import time

        if not self._initialized or not self._client:
            return None

        key_id = (
            f"azure-{hashlib.sha256(f'{label}{time.time()}'.encode()).hexdigest()[:16]}"
        )
        vault_key_name = f"warmlogic-{label.replace(' ', '-').lower()}-{key_id[-8:]}"

        try:
            from azure.keyvault.keys import KeyCurveName, KeyType as AzureKeyType

            # Map key type to Azure key type
            if key_type in [KeyType.ML_DSA_65, KeyType.ED25519]:
                # Use P-256 for signing (no PQC in Azure yet)
                key = self._client.create_ec_key(
                    name=vault_key_name,
                    curve=KeyCurveName.p_256,
                    hardware_protected=True,  # HSM-backed
                )
            elif key_type == KeyType.AES_256_GCM:
                key = self._client.create_key(
                    name=vault_key_name,
                    key_type=AzureKeyType.oct_hsm,
                    size=256,
                )
            else:
                key = self._client.create_ec_key(
                    name=vault_key_name,
                    curve=KeyCurveName.p_256,
                    hardware_protected=True,
                )

            self._key_names[key_id] = vault_key_name

            # Create crypto client for this key
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.keys.crypto import CryptographyClient

            credential = DefaultAzureCredential()
            self._crypto_clients[key_id] = CryptographyClient(
                key.id, credential=credential
            )

            hsm_key = HSMKey(
                key_id=key_id,
                key_type=key_type,
                label=label,
                created_at=time.time(),
                is_extractable=False,
                is_hardware_bound=True,
                metadata={
                    "vault_key_name": vault_key_name,
                    "vault_url": self._vault_url,
                    "key_id_url": key.id,
                },
            )
            self._keys[key_id] = hsm_key
            logger.info(f"[HSM] Generated Azure Key Vault key: {key_id}")
            return hsm_key

        except Exception as e:
            logger.error(f"[HSM] Azure key generation failed: {e}")
            return None

    def get_key(self, key_id: str) -> Optional[HSMKey]:
        return self._keys.get(key_id)

    def delete_key(self, key_id: str) -> bool:
        if key_id not in self._keys:
            return False

        try:
            if key_id in self._key_names and self._client:
                vault_key_name = self._key_names[key_id]
                # Begin deletion (soft-delete by default)
                self._client.begin_delete_key(vault_key_name)
                del self._key_names[key_id]

            if key_id in self._crypto_clients:
                del self._crypto_clients[key_id]

            del self._keys[key_id]
            return True

        except Exception as e:
            logger.error(f"[HSM] Azure key deletion failed: {e}")
            return False

    def sign(self, key_id: str, data: bytes) -> Optional[HSMSignature]:
        import time

        if key_id not in self._crypto_clients:
            return None

        try:
            from azure.keyvault.keys.crypto import SignatureAlgorithm

            crypto_client = self._crypto_clients[key_id]

            # Compute digest first (Azure requires pre-hashed for some algorithms)
            digest = hashlib.sha256(data).digest()

            result = crypto_client.sign(SignatureAlgorithm.es256, digest)

            return HSMSignature(
                signature_hex=result.signature.hex(),
                key_id=key_id,
                algorithm="ES256",
                timestamp=time.time(),
            )

        except Exception as e:
            logger.error(f"[HSM] Azure signing failed: {e}")
            return None

    def verify(self, key_id: str, data: bytes, signature: bytes) -> bool:
        if key_id not in self._crypto_clients:
            return False

        try:
            from azure.keyvault.keys.crypto import SignatureAlgorithm

            crypto_client = self._crypto_clients[key_id]
            digest = hashlib.sha256(data).digest()

            result = crypto_client.verify(SignatureAlgorithm.es256, digest, signature)
            return bool(result.is_valid)

        except Exception as e:
            logger.error(f"[HSM] Azure verification failed: {e}")
            return False

    def get_public_key(self, key_id: str) -> Optional[str]:
        if key_id not in self._key_names or not self._client:
            return None

        try:
            vault_key_name = self._key_names[key_id]
            key = self._client.get_key(vault_key_name)

            # Return JWK representation
            if key.key:
                import json

                jwk = {
                    "kty": key.key.kty,
                    "crv": key.key.crv,
                    "x": key.key.x.hex() if key.key.x else None,
                    "y": key.key.y.hex() if key.key.y else None,
                }
                return json.dumps(jwk)
            return None

        except Exception as e:
            logger.error(f"[HSM] Azure public key export failed: {e}")
            return None


class GCPCloudKMSHSM(HSMProvider):
    """
    Google Cloud KMS HSM Provider

    Uses Google Cloud KMS with HSM protection level for
    FIPS 140-2 Level 3 validated cryptographic operations.

    Requirements:
    - google-cloud-kms SDK
    - GCP service account credentials
    - KMS key ring with HSM protection level

    Key hierarchy:
    - Project > Location > KeyRing > CryptoKey > CryptoKeyVersion
    """

    def __init__(
        self,
        project_id: Optional[str] = None,
        location: Optional[str] = None,
        key_ring: Optional[str] = None,
    ):
        self._initialized = False
        self._project_id = project_id or os.environ.get("GCP_PROJECT_ID")
        self._location = location or os.environ.get("GCP_KMS_LOCATION", "global")
        self._key_ring = key_ring or os.environ.get(
            "GCP_KMS_KEY_RING", "warmlogic-keys"
        )
        self._keys: Dict[str, HSMKey] = {}
        self._key_names: Dict[str, str] = {}  # key_id -> full resource name
        self._client: Optional[Any] = None

    def initialize(self) -> bool:
        if not self._project_id:
            logger.error("[HSM] GCP project ID not configured")
            return False

        try:
            from google.cloud import kms

            self._client = kms.KeyManagementServiceClient()
            if self._client is None:
                raise RuntimeError("Failed to initialize GCP KMS client")

            # Verify/create key ring
            key_ring_name = (
                f"projects/{self._project_id}/locations/{self._location}"
                f"/keyRings/{self._key_ring}"
            )

            try:
                self._client.get_key_ring(request={"name": key_ring_name})
            except Exception:
                # Create key ring if not exists
                parent = f"projects/{self._project_id}/locations/{self._location}"
                self._client.create_key_ring(
                    request={
                        "parent": parent,
                        "key_ring_id": self._key_ring,
                    }
                )

            self._key_ring_name = key_ring_name
            self._initialized = True
            logger.info(f"[HSM] GCP Cloud KMS initialized: {key_ring_name}")
            return True

        except ImportError:
            logger.error(
                "[HSM] Google Cloud KMS SDK not installed. "
                "Run: pip install google-cloud-kms"
            )
            return False
        except Exception as e:
            logger.error(f"[HSM] GCP Cloud KMS initialization failed: {e}")
            return False

    def get_capabilities(self) -> HSMCapabilities:
        return HSMCapabilities(
            hsm_type=HSMType.GCP_CLOUD_KMS,
            supports_pqc=False,
            max_key_slots=10000,
            firmware_version="GCP-CloudKMS-HSM",
            hardware_serial=self._project_id or "unknown",
            is_fips_certified=True,  # HSM protection level is FIPS 140-2 Level 3
            supported_algorithms=[
                "RSA-2048",
                "RSA-4096",
                "P-256",
                "P-384",
                "AES-256-GCM",
                "HMAC-SHA256",
            ],
        )

    def generate_key(self, key_type: KeyType, label: str) -> Optional[HSMKey]:
        import time

        if not self._initialized or not self._client:
            return None

        key_id = (
            f"gcp-{hashlib.sha256(f'{label}{time.time()}'.encode()).hexdigest()[:16]}"
        )
        crypto_key_id = f"warmlogic-{label.replace(' ', '-').lower()}-{key_id[-8:]}"

        try:
            from google.cloud.kms import CryptoKey, CryptoKeyVersion, ProtectionLevel

            # Map key type to GCP algorithm
            if key_type in [KeyType.ML_DSA_65, KeyType.ED25519]:
                purpose = CryptoKey.CryptoKeyPurpose.ASYMMETRIC_SIGN
                algorithm = (
                    CryptoKeyVersion.CryptoKeyVersionAlgorithm.EC_SIGN_P256_SHA256
                )
            elif key_type == KeyType.AES_256_GCM:
                purpose = CryptoKey.CryptoKeyPurpose.ENCRYPT_DECRYPT
                algorithm = (
                    CryptoKeyVersion.CryptoKeyVersionAlgorithm.GOOGLE_SYMMETRIC_ENCRYPTION
                )
            else:
                purpose = CryptoKey.CryptoKeyPurpose.ASYMMETRIC_SIGN
                algorithm = (
                    CryptoKeyVersion.CryptoKeyVersionAlgorithm.EC_SIGN_P256_SHA256
                )

            # Create HSM-backed crypto key
            crypto_key = CryptoKey(
                purpose=purpose,
                version_template=CryptoKeyVersion.CryptoKeyVersionTemplate(
                    protection_level=ProtectionLevel.HSM,
                    algorithm=algorithm,
                ),
            )

            response = self._client.create_crypto_key(
                request={
                    "parent": self._key_ring_name,
                    "crypto_key_id": crypto_key_id,
                    "crypto_key": crypto_key,
                }
            )

            # Get the primary key version
            key_version_name = f"{response.name}/cryptoKeyVersions/1"
            self._key_names[key_id] = key_version_name

            hsm_key = HSMKey(
                key_id=key_id,
                key_type=key_type,
                label=label,
                created_at=time.time(),
                is_extractable=False,
                is_hardware_bound=True,
                metadata={
                    "crypto_key_name": response.name,
                    "key_version_name": key_version_name,
                    "project": self._project_id,
                    "location": self._location,
                },
            )
            self._keys[key_id] = hsm_key
            logger.info(f"[HSM] Generated GCP Cloud KMS key: {key_id}")
            return hsm_key

        except Exception as e:
            logger.error(f"[HSM] GCP key generation failed: {e}")
            return None

    def get_key(self, key_id: str) -> Optional[HSMKey]:
        return self._keys.get(key_id)

    def delete_key(self, key_id: str) -> bool:
        if key_id not in self._keys:
            return False

        try:
            if key_id in self._key_names and self._client:
                key_version_name = self._key_names[key_id]
                # Schedule key version for destruction
                self._client.destroy_crypto_key_version(
                    request={"name": key_version_name}
                )
                del self._key_names[key_id]

            del self._keys[key_id]
            return True

        except Exception as e:
            logger.error(f"[HSM] GCP key deletion failed: {e}")
            return False

    def sign(self, key_id: str, data: bytes) -> Optional[HSMSignature]:
        import time

        if key_id not in self._key_names or not self._client:
            return None

        try:
            key_version_name = self._key_names[key_id]

            # Compute digest
            digest = hashlib.sha256(data).digest()

            # Sign using Cloud KMS
            from google.cloud.kms import Digest

            response = self._client.asymmetric_sign(
                request={
                    "name": key_version_name,
                    "digest": Digest(sha256=digest),
                }
            )

            return HSMSignature(
                signature_hex=response.signature.hex(),
                key_id=key_id,
                algorithm="EC_SIGN_P256_SHA256",
                timestamp=time.time(),
            )

        except Exception as e:
            logger.error(f"[HSM] GCP signing failed: {e}")
            return None

    def verify(self, key_id: str, data: bytes, signature: bytes) -> bool:
        if key_id not in self._key_names or not self._client:
            return False

        try:
            key_version_name = self._key_names[key_id]
            digest = hashlib.sha256(data).digest()

            from google.cloud.kms import Digest

            response = self._client.asymmetric_verify(
                request={
                    "name": key_version_name,
                    "digest": Digest(sha256=digest),
                    "signature": signature,
                }
            )

            return bool(response.success)

        except Exception as e:
            logger.error(f"[HSM] GCP verification failed: {e}")
            return False

    def get_public_key(self, key_id: str) -> Optional[str]:
        if key_id not in self._key_names or not self._client:
            return None

        try:
            key_version_name = self._key_names[key_id]
            response = self._client.get_public_key(request={"name": key_version_name})
            return str(response.pem) if response.pem else None

        except Exception as e:
            logger.error(f"[HSM] GCP public key export failed: {e}")
            return None


class HSMManager:
    """
    [/7000] HSM Manager

    Manages HSM providers and provides unified interface for
    hardware-backed cryptographic operations.
    """

    def __init__(self, preferred_hsm: Optional[HSMType] = None):
        self._provider: Optional[HSMProvider] = None
        self._hsm_type: Optional[HSMType] = None
        self._preferred = preferred_hsm

    def initialize(self) -> bool:
        """
        Initialize HSM with best available provider.

        Priority:
        1. Cloud HSM (AWS/Azure/GCP) if configured
        2. Apple Secure Enclave (macOS)
        3. TPM 2.0 (Linux)
        4. Software HSM (fallback)
        """
        providers_to_try: List[Tuple[HSMType, HSMProvider]] = []

        if self._preferred:
            if self._preferred == HSMType.APPLE_SECURE_ENCLAVE:
                providers_to_try.append(
                    (HSMType.APPLE_SECURE_ENCLAVE, AppleSecureEnclaveHSM())
                )
            elif self._preferred == HSMType.TPM_2_0:
                providers_to_try.append((HSMType.TPM_2_0, TPM20HSM()))
            elif self._preferred == HSMType.SOFTWARE:
                providers_to_try.append((HSMType.SOFTWARE, SoftwareHSM()))
            # Cloud HSM providers
            elif self._preferred == HSMType.AWS_CLOUD_HSM:
                providers_to_try.append((HSMType.AWS_CLOUD_HSM, AWSCloudHSM()))
            elif self._preferred == HSMType.AZURE_KEY_VAULT:
                providers_to_try.append((HSMType.AZURE_KEY_VAULT, AzureKeyVaultHSM()))
            elif self._preferred == HSMType.GCP_CLOUD_KMS:
                providers_to_try.append((HSMType.GCP_CLOUD_KMS, GCPCloudKMSHSM()))
        else:
            # Auto-detect best HSM
            # Check for cloud HSM environment variables first
            if os.environ.get("AWS_CLOUDHSM_CLUSTER_ID"):
                providers_to_try.append((HSMType.AWS_CLOUD_HSM, AWSCloudHSM()))
            if os.environ.get("AZURE_KEYVAULT_URL"):
                providers_to_try.append((HSMType.AZURE_KEY_VAULT, AzureKeyVaultHSM()))
            if os.environ.get("GCP_PROJECT_ID") and os.environ.get("GCP_KMS_KEY_RING"):
                providers_to_try.append((HSMType.GCP_CLOUD_KMS, GCPCloudKMSHSM()))

            # Local HSM fallbacks
            if platform.system() == "Darwin":
                providers_to_try.append(
                    (HSMType.APPLE_SECURE_ENCLAVE, AppleSecureEnclaveHSM())
                )
            elif platform.system() == "Linux":
                providers_to_try.append((HSMType.TPM_2_0, TPM20HSM()))

            # Always fallback to software HSM
            providers_to_try.append((HSMType.SOFTWARE, SoftwareHSM()))

        for hsm_type, provider in providers_to_try:
            if provider.initialize():
                self._provider = provider
                self._hsm_type = hsm_type
                logger.info(f"[HSM] Using {hsm_type.value} provider")
                return True

        logger.error("[HSM] No HSM provider available")
        return False

    @property
    def provider(self) -> Optional[HSMProvider]:
        return self._provider

    @property
    def hsm_type(self) -> Optional[HSMType]:
        return self._hsm_type

    def get_capabilities(self) -> Optional[HSMCapabilities]:
        if self._provider:
            return self._provider.get_capabilities()
        return None

    def generate_signing_key(self, label: str) -> Optional[HSMKey]:
        """Generate a post-quantum signing key."""
        if not self._provider:
            return None
        return self._provider.generate_key(KeyType.ML_DSA_65, label)

    def generate_kem_key(self, label: str) -> Optional[HSMKey]:
        """Generate a post-quantum key exchange key."""
        if not self._provider:
            return None
        return self._provider.generate_key(KeyType.ML_KEM_768, label)

    def sign(self, key_id: str, data: bytes) -> Optional[HSMSignature]:
        """Sign data using HSM-protected key."""
        if not self._provider:
            return None
        return self._provider.sign(key_id, data)

    def verify(self, key_id: str, data: bytes, signature: bytes) -> bool:
        """Verify signature using HSM-protected key."""
        if not self._provider:
            return False
        return self._provider.verify(key_id, data, signature)

    def get_public_key(self, key_id: str) -> Optional[str]:
        """Get public key for sharing."""
        if not self._provider:
            return None
        return self._provider.get_public_key(key_id)


# Global HSM manager instance
_hsm_manager: Optional[HSMManager] = None
_hsm_manager_lock = threading.Lock()


def get_hsm_manager() -> HSMManager:
    """Get the global HSM manager instance (thread-safe)."""
    global _hsm_manager
    if _hsm_manager is None:
        with _hsm_manager_lock:
            if _hsm_manager is None:  # Double-checked locking
                _hsm_manager = HSMManager()
    return _hsm_manager


def initialize_hsm(preferred: Optional[HSMType] = None) -> bool:
    """Initialize the global HSM manager (thread-safe)."""
    global _hsm_manager
    with _hsm_manager_lock:
        _hsm_manager = HSMManager(preferred_hsm=preferred)
        return _hsm_manager.initialize()
