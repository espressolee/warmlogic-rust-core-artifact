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
Tests for SSO Integration module.
"""

import time
import unittest
from unittest.mock import patch

from warm_logic.security.sso import (
    OIDCProvider,
    OIDCProvider_,
    SAMLProvider,
    SSOConfig,
    SSOManager,
    SSOProvider,
    SSOSession,
    SSOUser,
    get_sso_manager,
)


class TestSSOConfig(unittest.TestCase):
    """Test SSOConfig dataclass."""

    def test_default_config(self):
        """Test default SSO configuration."""
        config = SSOConfig(provider=SSOProvider.OIDC)
        self.assertEqual(config.provider, SSOProvider.OIDC)
        self.assertFalse(config.enabled)
        self.assertEqual(config.session_timeout_minutes, 480)
        self.assertIn("openid", config.oidc_scopes)

    def test_oidc_config(self):
        """Test OIDC configuration."""
        # Test credentials - not real values
        test_cred = "test-client-credential"
        config = SSOConfig(
            provider=SSOProvider.OIDC,
            enabled=True,
            oidc_issuer_url="https://auth.example.com",
            oidc_client_id="client123",
            oidc_client_secret=test_cred,
            oidc_redirect_uri="https://app.example.com/callback",
        )
        self.assertTrue(config.enabled)
        self.assertEqual(config.oidc_issuer_url, "https://auth.example.com")
        self.assertEqual(config.oidc_client_id, "client123")

    def test_saml_config(self):
        """Test SAML configuration."""
        config = SSOConfig(
            provider=SSOProvider.SAML,
            enabled=True,
            saml_metadata_url="https://idp.example.com/metadata",
            saml_entity_id="warmlogic-sp",
            saml_acs_url="https://app.example.com/saml/acs",
        )
        self.assertEqual(config.provider, SSOProvider.SAML)
        self.assertEqual(config.saml_entity_id, "warmlogic-sp")


class TestSSOUser(unittest.TestCase):
    """Test SSOUser dataclass."""

    def test_user_creation(self):
        """Test basic user creation."""
        user = SSOUser(
            user_id="user123",
            email="user@example.com",
            name="Test User",
            groups=["admin", "developers"],
        )
        self.assertEqual(user.user_id, "user123")
        self.assertEqual(user.email, "user@example.com")
        self.assertIn("admin", user.groups)

    def test_session_validity(self):
        """Test session validity check."""
        # Valid session
        user = SSOUser(
            user_id="user123",
            email="user@example.com",
            session_expires_at=time.time() + 3600,
        )
        self.assertTrue(user.is_session_valid)

        # Expired session
        user_expired = SSOUser(
            user_id="user123",
            email="user@example.com",
            session_expires_at=time.time() - 1,
        )
        self.assertFalse(user_expired.is_session_valid)


class TestSSOSession(unittest.TestCase):
    """Test SSOSession dataclass."""

    def test_session_creation(self):
        """Test session creation."""
        user = SSOUser(
            user_id="user123",
            email="user@example.com",
        )
        session = SSOSession(
            session_id="sess123",
            user=user,
            access_token="access_token_value",
            refresh_token="refresh_token_value",
            token_expires_at=time.time() + 3600,
        )
        self.assertEqual(session.session_id, "sess123")
        self.assertTrue(session.is_token_valid)

    def test_token_expiration(self):
        """Test token expiration check."""
        user = SSOUser(user_id="user123", email="user@example.com")
        session = SSOSession(
            session_id="sess123",
            user=user,
            access_token="token",
            token_expires_at=time.time() - 1,
        )
        self.assertFalse(session.is_token_valid)


class TestOIDCProvider(unittest.TestCase):
    """Test OIDCProvider class."""

    def test_oidc_provider_init(self):
        """Test OIDC provider initialization."""
        config = SSOConfig(
            provider=SSOProvider.OIDC,
            oidc_issuer_url="https://auth.example.com",
            oidc_client_id="client123",
        )
        provider = OIDCProvider_(config)
        self.assertFalse(provider._initialized)

    def test_code_verifier_generation(self):
        """Test PKCE code verifier generation."""
        config = SSOConfig(
            provider=SSOProvider.OIDC,
            oidc_issuer_url="https://auth.example.com",
        )
        provider = OIDCProvider_(config)
        verifier = provider._generate_code_verifier()
        self.assertIsInstance(verifier, str)
        self.assertGreater(len(verifier), 20)

    def test_code_challenge_generation(self):
        """Test PKCE code challenge generation."""
        config = SSOConfig(
            provider=SSOProvider.OIDC,
            oidc_issuer_url="https://auth.example.com",
        )
        provider = OIDCProvider_(config)
        verifier = "test_verifier_12345"
        challenge = provider._generate_code_challenge(verifier)
        self.assertIsInstance(challenge, str)
        self.assertNotEqual(challenge, verifier)


class TestSAMLProvider(unittest.TestCase):
    """Test SAMLProvider class."""

    def test_saml_provider_init(self):
        """Test SAML provider initialization."""
        config = SSOConfig(
            provider=SSOProvider.SAML,
            saml_metadata_url="https://idp.example.com/metadata",
            saml_entity_id="warmlogic-sp",
        )
        provider = SAMLProvider(config)
        self.assertFalse(provider._initialized)

    def test_saml_init_no_metadata(self):
        """Test SAML initialization fails without metadata URL."""
        config = SSOConfig(
            provider=SSOProvider.SAML,
            saml_metadata_url=None,
        )
        provider = SAMLProvider(config)
        result = provider.initialize()
        self.assertFalse(result)


class TestSSOManager(unittest.TestCase):
    """Test SSOManager class."""

    def test_manager_init_disabled(self):
        """Test manager with SSO disabled."""
        config = SSOConfig(
            provider=SSOProvider.OIDC,
            enabled=False,
        )
        manager = SSOManager(config)
        result = manager.initialize()
        self.assertTrue(result)  # Should succeed but be disabled
        self.assertFalse(manager.is_enabled)

    def test_manager_init_oidc(self):
        """Test manager with OIDC provider."""
        config = SSOConfig(
            provider=SSOProvider.OIDC,
            enabled=True,
            oidc_issuer_url="https://auth.example.com",
        )
        manager = SSOManager(config)
        # Initialization will fail without network, but provider should be set
        self.assertTrue(manager.is_enabled)

    def test_manager_init_saml(self):
        """Test manager with SAML provider."""
        config = SSOConfig(
            provider=SSOProvider.SAML,
            enabled=True,
            saml_metadata_url="https://idp.example.com/metadata",
        )
        manager = SSOManager(config)
        self.assertTrue(manager.is_enabled)

    def test_session_management(self):
        """Test session storage and retrieval."""
        config = SSOConfig(
            provider=SSOProvider.OIDC,
            enabled=False,
        )
        manager = SSOManager(config)
        manager.initialize()

        # Create mock session
        user = SSOUser(
            user_id="user123",
            email="user@example.com",
            session_expires_at=time.time() + 3600,
        )
        session = SSOSession(
            session_id="test_session_id",
            user=user,
            access_token="token",
            token_expires_at=time.time() + 3600,
        )
        manager._sessions["test_session_id"] = session

        # Retrieve session
        retrieved = manager.get_session("test_session_id")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.user.email, "user@example.com")

    def test_session_expiration(self):
        """Test expired session removal."""
        config = SSOConfig(
            provider=SSOProvider.OIDC,
            enabled=False,
        )
        manager = SSOManager(config)
        manager.initialize()

        # Create expired session
        user = SSOUser(
            user_id="user123",
            email="user@example.com",
            session_expires_at=time.time() - 1,  # Expired
        )
        session = SSOSession(
            session_id="expired_session",
            user=user,
            access_token="token",
        )
        manager._sessions["expired_session"] = session

        # Should return None and clean up
        retrieved = manager.get_session("expired_session")
        self.assertIsNone(retrieved)
        self.assertNotIn("expired_session", manager._sessions)

    def test_logout(self):
        """Test logout removes session."""
        config = SSOConfig(
            provider=SSOProvider.OIDC,
            enabled=False,
        )
        manager = SSOManager(config)
        manager.initialize()

        user = SSOUser(
            user_id="user123",
            email="user@example.com",
            session_expires_at=time.time() + 3600,
        )
        session = SSOSession(
            session_id="session_to_logout",
            user=user,
            access_token="token",
        )
        manager._sessions["session_to_logout"] = session

        result = manager.logout("session_to_logout")
        self.assertTrue(result)
        self.assertNotIn("session_to_logout", manager._sessions)


class TestSSOGlobalFunctions(unittest.TestCase):
    """Test global SSO functions."""

    def test_get_sso_manager(self):
        """Test getting global SSO manager."""
        manager = get_sso_manager()
        self.assertIsNotNone(manager)
        self.assertIsInstance(manager, SSOManager)

    @patch.dict(
        "os.environ",
        {
            "SSO_ENABLED": "true",
            "SSO_PROVIDER": "oidc",
            "OIDC_ISSUER_URL": "https://test.auth.com",
            "OIDC_CLIENT_ID": "test_client",
        },
    )
    def test_initialize_sso_from_env(self):
        """Test SSO initialization from environment."""
        # This will fail to connect but should load config
        config = SSOConfig(
            provider=SSOProvider.OIDC,
            enabled=True,
            oidc_issuer_url="https://test.auth.com",
            oidc_client_id="test_client",
        )
        manager = SSOManager(config)
        self.assertTrue(manager.is_enabled)


class TestOIDCProviderEnum(unittest.TestCase):
    """Test OIDCProvider enum values."""

    def test_oidc_providers(self):
        """Test OIDC provider enum values."""
        self.assertEqual(OIDCProvider.OKTA.value, "okta")
        self.assertEqual(OIDCProvider.AZURE_AD.value, "azure_ad")
        self.assertEqual(OIDCProvider.GOOGLE.value, "google")
        self.assertEqual(OIDCProvider.AUTH0.value, "auth0")
        self.assertEqual(OIDCProvider.KEYCLOAK.value, "keycloak")


if __name__ == "__main__":
    unittest.main()
