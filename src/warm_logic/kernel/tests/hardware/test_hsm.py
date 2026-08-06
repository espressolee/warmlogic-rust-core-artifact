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
Tests for HSM Integration module.
"""

import sys
import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import warm_logic.kernel


@contextmanager
def mock_rust_loader(has_rust_core: bool = True, mock_rs: MagicMock = None):
    """Context manager to mock rust_loader for HSM tests."""
    if mock_rs is None:
        mock_rs = MagicMock()
        mock_rs.generate_keypair.return_value = ("pk", "sk")
        mock_rs.kem_keygen.return_value = ("ek", "dk")
        mock_rs.sign.return_value = "signature_hex"
        mock_rs.verify.return_value = True

    mock_loader = MagicMock()
    mock_loader.HAS_RUST_CORE = has_rust_core
    mock_loader.load_rust_core.return_value = mock_rs

    # Save original
    original_rust_loader = getattr(warm_logic.kernel, "rust_loader", None)
    original_in_modules = sys.modules.get("warm_logic.kernel.rust_loader")

    # Patch both the module cache and the package attribute
    sys.modules["warm_logic.kernel.rust_loader"] = mock_loader
    warm_logic.kernel.rust_loader = mock_loader

    try:
        yield mock_loader, mock_rs
    finally:
        # Restore
        if original_rust_loader is not None:
            warm_logic.kernel.rust_loader = original_rust_loader
        if original_in_modules is not None:
            sys.modules["warm_logic.kernel.rust_loader"] = original_in_modules
        elif "warm_logic.kernel.rust_loader" in sys.modules:
            # Don't remove if it existed before
            pass


class TestHSMKey(unittest.TestCase):
    """Test HSMKey dataclass."""

    def test_key_creation(self):
        """Test basic key creation."""
        from warm_logic.kernel.hardware.hsm import HSMKey, KeyType

        key = HSMKey(
            key_id="test-key-1",
            key_type=KeyType.ML_DSA_65,
            label="test-signing-key",
            created_at=1000.0,
        )
        self.assertEqual(key.key_id, "test-key-1")
        self.assertEqual(key.key_type, KeyType.ML_DSA_65)
        self.assertEqual(key.label, "test-signing-key")
        self.assertFalse(key.is_extractable)
        self.assertTrue(key.is_hardware_bound)

    def test_key_not_expired(self):
        """Test key expiration check - not expired."""
        from warm_logic.kernel.hardware.hsm import HSMKey, KeyType

        key = HSMKey(
            key_id="test",
            key_type=KeyType.ML_DSA_65,
            label="test",
            expires_at=None,
        )
        self.assertFalse(key.is_expired)

    def test_key_expired(self):
        """Test key expiration check - expired."""
        from warm_logic.kernel.hardware.hsm import HSMKey, KeyType

        key = HSMKey(
            key_id="test",
            key_type=KeyType.ML_DSA_65,
            label="test",
            expires_at=1.0,  # Long past
        )
        self.assertTrue(key.is_expired)


class TestHSMCapabilities(unittest.TestCase):
    """Test HSMCapabilities dataclass."""

    def test_capabilities_creation(self):
        """Test capabilities creation."""
        from warm_logic.kernel.hardware.hsm import HSMCapabilities, HSMType

        caps = HSMCapabilities(
            hsm_type=HSMType.SOFTWARE,
            supports_pqc=True,
            max_key_slots=1000,
        )
        self.assertEqual(caps.hsm_type, HSMType.SOFTWARE)
        self.assertTrue(caps.supports_pqc)
        self.assertEqual(caps.max_key_slots, 1000)


class TestSoftwareHSM(unittest.TestCase):
    """Test SoftwareHSM provider."""

    def test_initialize(self):
        """Test software HSM initialization."""
        from warm_logic.kernel.hardware.hsm import SoftwareHSM

        hsm = SoftwareHSM()
        result = hsm.initialize()
        self.assertTrue(result)

    def test_get_capabilities(self):
        """Test getting capabilities."""
        from warm_logic.kernel.hardware.hsm import HSMType, SoftwareHSM

        hsm = SoftwareHSM()
        hsm.initialize()
        caps = hsm.get_capabilities()

        self.assertEqual(caps.hsm_type, HSMType.SOFTWARE)
        self.assertTrue(caps.supports_pqc)
        self.assertFalse(caps.is_fips_certified)
        self.assertIn("ML-DSA-65", caps.supported_algorithms)

    def test_generate_ml_dsa_key(self):
        """Test ML-DSA key generation."""
        from warm_logic.kernel.hardware.hsm import KeyType, SoftwareHSM

        mock_rs = MagicMock()
        mock_rs.generate_keypair.return_value = ("public_key_hex", "secret_key_hex")

        with mock_rust_loader(has_rust_core=True, mock_rs=mock_rs) as (_, _):
            hsm = SoftwareHSM()
            hsm.initialize()

            key = hsm.generate_key(KeyType.ML_DSA_65, "test-signing")

            self.assertIsNotNone(key)
            self.assertEqual(key.key_type, KeyType.ML_DSA_65)
            self.assertEqual(key.label, "test-signing")
            mock_rs.generate_keypair.assert_called_once()

    def test_generate_ml_kem_key(self):
        """Test ML-KEM key generation."""
        from warm_logic.kernel.hardware.hsm import KeyType, SoftwareHSM

        mock_rs = MagicMock()
        mock_rs.kem_keygen.return_value = ("encap_key_hex", "decap_key_hex")

        with mock_rust_loader(has_rust_core=True, mock_rs=mock_rs) as (_, _):
            hsm = SoftwareHSM()
            hsm.initialize()

            key = hsm.generate_key(KeyType.ML_KEM_768, "test-kem")

            self.assertIsNotNone(key)
            self.assertEqual(key.key_type, KeyType.ML_KEM_768)
            mock_rs.kem_keygen.assert_called_once()

    def test_generate_key_no_rust_core(self):
        """Test key generation fails without Rust core."""
        from warm_logic.kernel.hardware.hsm import KeyType, SoftwareHSM

        with mock_rust_loader(has_rust_core=False) as (_, _):
            hsm = SoftwareHSM()
            hsm.initialize()

            key = hsm.generate_key(KeyType.ML_DSA_65, "test")

            self.assertIsNone(key)

    def test_get_key(self):
        """Test retrieving key metadata."""
        from warm_logic.kernel.hardware.hsm import KeyType, SoftwareHSM

        mock_rs = MagicMock()
        mock_rs.generate_keypair.return_value = ("pk", "sk")

        with mock_rust_loader(has_rust_core=True, mock_rs=mock_rs) as (_, _):
            hsm = SoftwareHSM()
            hsm.initialize()

            key = hsm.generate_key(KeyType.ML_DSA_65, "test")
            retrieved = hsm.get_key(key.key_id)

            self.assertEqual(retrieved.key_id, key.key_id)

    def test_get_key_not_found(self):
        """Test retrieving non-existent key."""
        from warm_logic.kernel.hardware.hsm import SoftwareHSM

        hsm = SoftwareHSM()
        hsm.initialize()

        key = hsm.get_key("non-existent-key")
        self.assertIsNone(key)

    def test_delete_key(self):
        """Test key deletion."""
        from warm_logic.kernel.hardware.hsm import KeyType, SoftwareHSM

        mock_rs = MagicMock()
        mock_rs.generate_keypair.return_value = ("pk", "sk")

        with mock_rust_loader(has_rust_core=True, mock_rs=mock_rs) as (_, _):
            hsm = SoftwareHSM()
            hsm.initialize()

            key = hsm.generate_key(KeyType.ML_DSA_65, "test")
            result = hsm.delete_key(key.key_id)

            self.assertTrue(result)
            self.assertIsNone(hsm.get_key(key.key_id))

    def test_delete_key_not_found(self):
        """Test deleting non-existent key."""
        from warm_logic.kernel.hardware.hsm import SoftwareHSM

        hsm = SoftwareHSM()
        hsm.initialize()

        result = hsm.delete_key("non-existent")
        self.assertFalse(result)

    def test_sign(self):
        """Test signing data."""
        from warm_logic.kernel.hardware.hsm import KeyType, SoftwareHSM

        mock_rs = MagicMock()
        mock_rs.generate_keypair.return_value = ("pk", "sk")
        mock_rs.sign.return_value = "signature_hex"

        with mock_rust_loader(has_rust_core=True, mock_rs=mock_rs) as (_, _):
            hsm = SoftwareHSM()
            hsm.initialize()

            key = hsm.generate_key(KeyType.ML_DSA_65, "test")
            sig = hsm.sign(key.key_id, b"test data")

            self.assertIsNotNone(sig)
            self.assertEqual(sig.signature_hex, "signature_hex")
            self.assertEqual(sig.key_id, key.key_id)

    def test_sign_key_not_found(self):
        """Test signing with non-existent key."""
        from warm_logic.kernel.hardware.hsm import SoftwareHSM

        hsm = SoftwareHSM()
        hsm.initialize()

        sig = hsm.sign("non-existent", b"data")
        self.assertIsNone(sig)

    def test_verify(self):
        """Test signature verification."""
        from warm_logic.kernel.hardware.hsm import KeyType, SoftwareHSM

        mock_rs = MagicMock()
        mock_rs.generate_keypair.return_value = ("pk", "sk")
        mock_rs.verify.return_value = True

        with mock_rust_loader(has_rust_core=True, mock_rs=mock_rs) as (_, _):
            hsm = SoftwareHSM()
            hsm.initialize()

            key = hsm.generate_key(KeyType.ML_DSA_65, "test")
            result = hsm.verify(key.key_id, b"data", b"signature")

            self.assertTrue(result)

    def test_verify_key_not_found(self):
        """Test verification with non-existent key."""
        from warm_logic.kernel.hardware.hsm import SoftwareHSM

        hsm = SoftwareHSM()
        hsm.initialize()

        result = hsm.verify("non-existent", b"data", b"sig")
        self.assertFalse(result)

    def test_get_public_key(self):
        """Test getting public key."""
        from warm_logic.kernel.hardware.hsm import KeyType, SoftwareHSM

        mock_rs = MagicMock()
        mock_rs.generate_keypair.return_value = ("public_key_hex", "sk")

        with mock_rust_loader(has_rust_core=True, mock_rs=mock_rs) as (_, _):
            hsm = SoftwareHSM()
            hsm.initialize()

            key = hsm.generate_key(KeyType.ML_DSA_65, "test")
            pk = hsm.get_public_key(key.key_id)

            self.assertEqual(pk, "public_key_hex")


class TestHSMManager(unittest.TestCase):
    """Test HSMManager."""

    def test_initialize_software(self):
        """Test initializing with software HSM."""
        from warm_logic.kernel.hardware.hsm import HSMManager, HSMType

        manager = HSMManager(preferred_hsm=HSMType.SOFTWARE)
        result = manager.initialize()

        self.assertTrue(result)
        self.assertEqual(manager.hsm_type, HSMType.SOFTWARE)

    def test_get_capabilities(self):
        """Test getting capabilities from manager."""
        from warm_logic.kernel.hardware.hsm import HSMManager, HSMType

        manager = HSMManager(preferred_hsm=HSMType.SOFTWARE)
        manager.initialize()

        caps = manager.get_capabilities()
        self.assertIsNotNone(caps)
        self.assertEqual(caps.hsm_type, HSMType.SOFTWARE)

    def test_get_capabilities_not_initialized(self):
        """Test getting capabilities when not initialized."""
        from warm_logic.kernel.hardware.hsm import HSMManager

        manager = HSMManager()
        caps = manager.get_capabilities()
        self.assertIsNone(caps)

    def test_generate_signing_key(self):
        """Test generating signing key via manager."""
        from warm_logic.kernel.hardware.hsm import HSMManager, HSMType, KeyType

        mock_rs = MagicMock()
        mock_rs.generate_keypair.return_value = ("pk", "sk")

        with mock_rust_loader(has_rust_core=True, mock_rs=mock_rs) as (_, _):
            manager = HSMManager(preferred_hsm=HSMType.SOFTWARE)
            manager.initialize()

            key = manager.generate_signing_key("test-key")
            self.assertIsNotNone(key)
            self.assertEqual(key.key_type, KeyType.ML_DSA_65)

    def test_generate_kem_key(self):
        """Test generating KEM key via manager."""
        from warm_logic.kernel.hardware.hsm import HSMManager, HSMType, KeyType

        mock_rs = MagicMock()
        mock_rs.kem_keygen.return_value = ("ek", "dk")

        with mock_rust_loader(has_rust_core=True, mock_rs=mock_rs) as (_, _):
            manager = HSMManager(preferred_hsm=HSMType.SOFTWARE)
            manager.initialize()

            key = manager.generate_kem_key("test-key")
            self.assertIsNotNone(key)
            self.assertEqual(key.key_type, KeyType.ML_KEM_768)


class TestGlobalHSMManager(unittest.TestCase):
    """Test global HSM manager functions."""

    def test_get_hsm_manager(self):
        """Test getting global HSM manager."""
        from warm_logic.kernel.hardware.hsm import HSMManager, get_hsm_manager

        manager = get_hsm_manager()
        self.assertIsNotNone(manager)
        self.assertIsInstance(manager, HSMManager)

    def test_initialize_hsm(self):
        """Test initializing global HSM."""
        from warm_logic.kernel.hardware.hsm import HSMType, initialize_hsm

        result = initialize_hsm(HSMType.SOFTWARE)
        self.assertTrue(result)


# ==============================================================================
# Cloud HSM Provider Tests
# ==============================================================================


class TestAWSCloudHSM(unittest.TestCase):
    """Test AWS CloudHSM provider."""

    def test_hsm_type_enum(self):
        """Test AWS_CLOUD_HSM enum exists."""
        from warm_logic.kernel.hardware.hsm import HSMType

        self.assertIsNotNone(HSMType.AWS_CLOUD_HSM)
        self.assertEqual(HSMType.AWS_CLOUD_HSM.value, "aws_cloud_hsm")

    def test_aws_cloudhsm_init(self):
        """Test AWSCloudHSM initialization."""
        from warm_logic.kernel.hardware.hsm import AWSCloudHSM

        hsm = AWSCloudHSM(cluster_id="hsm-test123", region="us-west-2")
        self.assertFalse(hsm._initialized)
        self.assertEqual(hsm._cluster_id, "hsm-test123")
        self.assertEqual(hsm._region, "us-west-2")

    def test_aws_cloudhsm_capabilities(self):
        """Test AWSCloudHSM capabilities."""
        from warm_logic.kernel.hardware.hsm import AWSCloudHSM, HSMType

        hsm = AWSCloudHSM(cluster_id="hsm-test")
        caps = hsm.get_capabilities()

        self.assertEqual(caps.hsm_type, HSMType.AWS_CLOUD_HSM)
        self.assertTrue(caps.is_fips_certified)
        self.assertIn("RSA-4096", caps.supported_algorithms)
        self.assertIn("P-256", caps.supported_algorithms)

    @patch.dict("os.environ", {}, clear=True)
    def test_aws_cloudhsm_init_from_env(self):
        """Test AWSCloudHSM initialization from environment."""
        import os

        from warm_logic.kernel.hardware.hsm import AWSCloudHSM

        os.environ["AWS_CLOUDHSM_CLUSTER_ID"] = "env-cluster-123"
        os.environ["AWS_DEFAULT_REGION"] = "eu-west-1"

        hsm = AWSCloudHSM()
        self.assertEqual(hsm._cluster_id, "env-cluster-123")
        self.assertEqual(hsm._region, "eu-west-1")

        # Clean up
        del os.environ["AWS_CLOUDHSM_CLUSTER_ID"]
        del os.environ["AWS_DEFAULT_REGION"]

    def test_aws_cloudhsm_initialize_no_boto3(self):
        """Test initialization fails gracefully without boto3."""
        from warm_logic.kernel.hardware.hsm import AWSCloudHSM

        with patch.dict("sys.modules", {"boto3": None}):
            hsm = AWSCloudHSM(cluster_id="test")
            # This should return False due to ImportError
            result = hsm.initialize()
            self.assertFalse(result)

    def test_aws_cloudhsm_initialize_success(self):
        """Test successful AWS CloudHSM initialization."""
        from warm_logic.kernel.hardware.hsm import AWSCloudHSM

        # Mock KMS client
        mock_kms = MagicMock()
        mock_kms.list_keys.return_value = {"Keys": []}

        mock_boto3 = MagicMock()
        mock_boto3.client.return_value = mock_kms
        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            hsm = AWSCloudHSM(region="us-east-1")
            result = hsm.initialize()

        self.assertTrue(result)
        self.assertTrue(hsm._initialized)

    def test_aws_cloudhsm_generate_key(self):
        """Test AWS key generation."""
        from warm_logic.kernel.hardware.hsm import AWSCloudHSM, KeyType

        mock_kms = MagicMock()
        mock_kms.list_keys.return_value = {"Keys": []}
        mock_kms.create_key.return_value = {
            "KeyMetadata": {"Arn": "arn:aws:kms:us-east-1:123456:key/test-key"}
        }

        mock_boto3 = MagicMock()
        mock_boto3.client.return_value = mock_kms
        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            hsm = AWSCloudHSM(region="us-east-1")
            hsm.initialize()
            key = hsm.generate_key(KeyType.ED25519, "test-signing")

        self.assertIsNotNone(key)
        self.assertEqual(key.label, "test-signing")
        self.assertTrue(key.is_hardware_bound)


class TestAzureKeyVaultHSM(unittest.TestCase):
    """Test Azure Key Vault HSM provider."""

    def test_hsm_type_enum(self):
        """Test AZURE_KEY_VAULT enum exists."""
        from warm_logic.kernel.hardware.hsm import HSMType

        self.assertIsNotNone(HSMType.AZURE_KEY_VAULT)
        self.assertEqual(HSMType.AZURE_KEY_VAULT.value, "azure_key_vault")

    def test_azure_keyvault_init(self):
        """Test AzureKeyVaultHSM initialization."""
        from warm_logic.kernel.hardware.hsm import AzureKeyVaultHSM

        hsm = AzureKeyVaultHSM(vault_url="https://warmlogic-vault.vault.azure.net")
        self.assertFalse(hsm._initialized)
        self.assertEqual(hsm._vault_url, "https://warmlogic-vault.vault.azure.net")

    def test_azure_keyvault_capabilities(self):
        """Test AzureKeyVaultHSM capabilities."""
        from warm_logic.kernel.hardware.hsm import AzureKeyVaultHSM, HSMType

        hsm = AzureKeyVaultHSM(vault_url="https://test.vault.azure.net")
        caps = hsm.get_capabilities()

        self.assertEqual(caps.hsm_type, HSMType.AZURE_KEY_VAULT)
        self.assertTrue(caps.is_fips_certified)
        self.assertIn("P-521", caps.supported_algorithms)

    def test_azure_keyvault_capabilities_managed_hsm(self):
        """Test capabilities detection for Managed HSM."""
        from warm_logic.kernel.hardware.hsm import AzureKeyVaultHSM

        hsm = AzureKeyVaultHSM(vault_url="https://warmlogic.managedhsm.azure.net")
        caps = hsm.get_capabilities()

        self.assertEqual(caps.firmware_version, "Azure-ManagedHSM")

    def test_azure_keyvault_init_no_url(self):
        """Test initialization fails without vault URL."""
        from warm_logic.kernel.hardware.hsm import AzureKeyVaultHSM

        hsm = AzureKeyVaultHSM(vault_url=None)
        result = hsm.initialize()
        self.assertFalse(result)


class TestGCPCloudKMSHSM(unittest.TestCase):
    """Test GCP Cloud KMS HSM provider."""

    def test_hsm_type_enum(self):
        """Test GCP_CLOUD_KMS enum exists."""
        from warm_logic.kernel.hardware.hsm import HSMType

        self.assertIsNotNone(HSMType.GCP_CLOUD_KMS)
        self.assertEqual(HSMType.GCP_CLOUD_KMS.value, "gcp_cloud_kms")

    def test_gcp_cloudkms_init(self):
        """Test GCPCloudKMSHSM initialization."""
        from warm_logic.kernel.hardware.hsm import GCPCloudKMSHSM

        hsm = GCPCloudKMSHSM(
            project_id="warmlogic-prod",
            location="us-central1",
            key_ring="signing-keys",
        )
        self.assertFalse(hsm._initialized)
        self.assertEqual(hsm._project_id, "warmlogic-prod")
        self.assertEqual(hsm._location, "us-central1")
        self.assertEqual(hsm._key_ring, "signing-keys")

    def test_gcp_cloudkms_capabilities(self):
        """Test GCPCloudKMSHSM capabilities."""
        from warm_logic.kernel.hardware.hsm import GCPCloudKMSHSM, HSMType

        hsm = GCPCloudKMSHSM(project_id="test-project")
        caps = hsm.get_capabilities()

        self.assertEqual(caps.hsm_type, HSMType.GCP_CLOUD_KMS)
        self.assertTrue(caps.is_fips_certified)
        self.assertIn("P-384", caps.supported_algorithms)

    def test_gcp_cloudkms_init_no_project(self):
        """Test initialization fails without project ID."""
        import os

        from warm_logic.kernel.hardware.hsm import GCPCloudKMSHSM

        # Temporarily remove GCP env var if present
        old_val = os.environ.pop("GCP_PROJECT_ID", None)

        hsm = GCPCloudKMSHSM(project_id=None)
        result = hsm.initialize()
        self.assertFalse(result)

        # Restore env var
        if old_val:
            os.environ["GCP_PROJECT_ID"] = old_val


class TestHSMManagerCloudProviders(unittest.TestCase):
    """Test HSMManager with cloud HSM providers."""

    def test_manager_prefers_aws(self):
        """Test manager can be configured for AWS."""
        from warm_logic.kernel.hardware.hsm import HSMManager, HSMType

        manager = HSMManager(preferred_hsm=HSMType.AWS_CLOUD_HSM)
        self.assertEqual(manager._preferred, HSMType.AWS_CLOUD_HSM)

    def test_manager_prefers_azure(self):
        """Test manager can be configured for Azure."""
        from warm_logic.kernel.hardware.hsm import HSMManager, HSMType

        manager = HSMManager(preferred_hsm=HSMType.AZURE_KEY_VAULT)
        self.assertEqual(manager._preferred, HSMType.AZURE_KEY_VAULT)

    def test_manager_prefers_gcp(self):
        """Test manager can be configured for GCP."""
        from warm_logic.kernel.hardware.hsm import HSMManager, HSMType

        manager = HSMManager(preferred_hsm=HSMType.GCP_CLOUD_KMS)
        self.assertEqual(manager._preferred, HSMType.GCP_CLOUD_KMS)


if __name__ == "__main__":
    unittest.main()
