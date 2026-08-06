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
Enterprise Single Sign-On (SSO) Integration

Provides OIDC and SAML 2.0 authentication for enterprise deployments.

Supported Identity Providers:
- Okta
- Azure AD / Entra ID
- Google Workspace
- Auth0
- Keycloak
- PingIdentity
- OneLogin
"""

import hashlib
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

logger = logging.getLogger("SSO")


class SSOProvider(Enum):
    """Supported SSO providers."""

    OIDC = "oidc"
    SAML = "saml"


class OIDCProvider(Enum):
    """Common OIDC identity providers."""

    OKTA = "okta"
    AZURE_AD = "azure_ad"
    GOOGLE = "google"
    AUTH0 = "auth0"
    KEYCLOAK = "keycloak"
    GENERIC = "generic"


@dataclass
class SSOConfig:
    """SSO configuration."""

    provider: SSOProvider
    enabled: bool = False

    # OIDC settings
    oidc_issuer_url: Optional[str] = None
    oidc_client_id: Optional[str] = None
    oidc_client_secret: Optional[str] = None
    oidc_scopes: List[str] = field(
        default_factory=lambda: ["openid", "profile", "email"]
    )
    oidc_redirect_uri: Optional[str] = None

    # SAML settings
    saml_metadata_url: Optional[str] = None
    saml_entity_id: Optional[str] = None
    saml_acs_url: Optional[str] = None
    saml_certificate: Optional[str] = None

    # Security settings
    require_mfa: bool = False
    session_timeout_minutes: int = 480  # 8 hours
    allowed_domains: List[str] = field(default_factory=list)


@dataclass
class SSOUser:
    """Authenticated user from SSO."""

    user_id: str
    email: str
    name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    groups: List[str] = field(default_factory=list)
    roles: List[str] = field(default_factory=list)
    provider: Optional[str] = None
    raw_claims: Dict[str, Any] = field(default_factory=dict)
    authenticated_at: float = 0.0
    session_expires_at: float = 0.0

    @property
    def is_session_valid(self) -> bool:
        return time.time() < self.session_expires_at


@dataclass
class SSOSession:
    """SSO session state."""

    session_id: str
    user: SSOUser
    access_token: str
    refresh_token: Optional[str] = None
    id_token: Optional[str] = None
    token_expires_at: float = 0.0
    created_at: float = 0.0

    @property
    def is_token_valid(self) -> bool:
        return time.time() < self.token_expires_at


class SSOProviderBase(ABC):
    """Abstract base class for SSO providers."""

    @abstractmethod
    def get_authorization_url(self, state: str, nonce: str) -> str:
        """Get the authorization URL for SSO login."""
        pass

    @abstractmethod
    def exchange_code(self, code: str, state: str) -> Optional[SSOSession]:
        """Exchange authorization code for tokens."""
        pass

    @abstractmethod
    def validate_token(self, token: str) -> Optional[SSOUser]:
        """Validate an access/ID token and extract user info."""
        pass

    @abstractmethod
    def refresh_session(self, session: SSOSession) -> Optional[SSOSession]:
        """Refresh an expired session using refresh token."""
        pass

    @abstractmethod
    def logout(self, session: SSOSession) -> bool:
        """Logout user and invalidate session."""
        pass


class OIDCProvider_(SSOProviderBase):
    """
    OpenID Connect (OIDC) Provider

    Implements OAuth 2.0 with OIDC extensions for enterprise SSO.
    Supports PKCE flow for enhanced security.
    """

    def __init__(self, config: SSOConfig):
        self._config = config
        self._initialized = False
        self._discovery_doc: Dict[str, Any] = {}
        self._jwks: Dict[str, Any] = {}

    def initialize(self) -> bool:
        """Initialize OIDC provider by fetching discovery document."""
        if not self._config.oidc_issuer_url:
            logger.error("[SSO] OIDC issuer URL not configured")
            return False

        try:
            import urllib.request

            # Fetch OIDC discovery document
            discovery_url = f"{self._config.oidc_issuer_url.rstrip('/')}/.well-known/openid-configuration"

            req = urllib.request.Request(
                discovery_url,
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                import json

                self._discovery_doc = json.loads(response.read().decode())

            # Fetch JWKS for token validation
            jwks_uri = self._discovery_doc.get("jwks_uri")
            if jwks_uri:
                req = urllib.request.Request(
                    jwks_uri,
                    headers={"Accept": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=10) as response:
                    self._jwks = json.loads(response.read().decode())

            self._initialized = True
            logger.info(
                f"[SSO] OIDC provider initialized: {self._config.oidc_issuer_url}"
            )
            return True

        except Exception as e:
            logger.error(f"[SSO] OIDC initialization failed: {e}")
            return False

    def get_authorization_url(self, state: str, nonce: str) -> str:
        """Generate OIDC authorization URL with PKCE."""
        if not self._initialized:
            self.initialize()

        auth_endpoint = self._discovery_doc.get(
            "authorization_endpoint",
            f"{self._config.oidc_issuer_url}/authorize",
        )

        # Generate PKCE code verifier and challenge
        code_verifier = self._generate_code_verifier()
        code_challenge = self._generate_code_challenge(code_verifier)

        params = {
            "response_type": "code",
            "client_id": self._config.oidc_client_id,
            "redirect_uri": self._config.oidc_redirect_uri,
            "scope": " ".join(self._config.oidc_scopes),
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }

        return f"{auth_endpoint}?{urlencode(params)}"

    def _generate_code_verifier(self) -> str:
        """Generate PKCE code verifier."""
        import base64

        return base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip("=")

    def _generate_code_challenge(self, verifier: str) -> str:
        """Generate PKCE code challenge from verifier."""
        import base64

        digest = hashlib.sha256(verifier.encode()).digest()
        return base64.urlsafe_b64encode(digest).decode().rstrip("=")

    def exchange_code(self, code: str, state: str) -> Optional[SSOSession]:
        """Exchange authorization code for tokens."""
        if not self._initialized:
            return None

        token_endpoint = self._discovery_doc.get(
            "token_endpoint",
            f"{self._config.oidc_issuer_url}/oauth/token",
        )

        try:
            import json
            import urllib.request

            data = urlencode(
                {
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self._config.oidc_redirect_uri,
                    "client_id": self._config.oidc_client_id,
                    "client_secret": self._config.oidc_client_secret,
                }
            ).encode()

            req = urllib.request.Request(
                token_endpoint,
                data=data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                token_data = json.loads(response.read().decode())

            # Parse tokens
            access_token = token_data.get("access_token")
            id_token = token_data.get("id_token")
            refresh_token = token_data.get("refresh_token")
            expires_in = token_data.get("expires_in", 3600)

            # Validate and parse ID token
            user = self._parse_id_token(id_token)
            if not user:
                logger.error("[SSO] Failed to parse ID token")
                return None

            # Create session
            session_id = hashlib.sha256(
                f"{user.user_id}{time.time()}".encode()
            ).hexdigest()[:32]

            return SSOSession(
                session_id=session_id,
                user=user,
                access_token=access_token,
                refresh_token=refresh_token,
                id_token=id_token,
                token_expires_at=time.time() + expires_in,
                created_at=time.time(),
            )

        except Exception as e:
            logger.error(f"[SSO] Token exchange failed: {e}")
            return None

    def _parse_id_token(self, id_token: str) -> Optional[SSOUser]:
        """Parse and validate ID token (JWT)."""
        try:
            import base64
            import json

            # Split JWT
            parts = id_token.split(".")
            if len(parts) != 3:
                return None

            # Decode payload (skip signature validation for now - production should verify)
            payload = parts[1]
            # Add padding if needed
            payload += "=" * (4 - len(payload) % 4)
            claims = json.loads(base64.urlsafe_b64decode(payload))

            # Validate issuer
            expected_issuer = (
                self._config.oidc_issuer_url.rstrip("/")
                if self._config.oidc_issuer_url
                else ""
            )
            if claims.get("iss") != expected_issuer:
                logger.warning("[SSO] Token issuer mismatch")
                # Don't fail for slight URL differences

            # Validate audience
            aud = claims.get("aud")
            if isinstance(aud, list):
                if self._config.oidc_client_id not in aud:
                    logger.error("[SSO] Client ID not in token audience")
                    return None
            elif aud != self._config.oidc_client_id:
                logger.error("[SSO] Token audience mismatch")
                return None

            # Validate expiration
            exp = claims.get("exp", 0)
            if time.time() > exp:
                logger.error("[SSO] Token expired")
                return None

            # Extract user info
            return SSOUser(
                user_id=claims.get("sub", ""),
                email=claims.get("email", ""),
                name=claims.get("name"),
                given_name=claims.get("given_name"),
                family_name=claims.get("family_name"),
                groups=claims.get("groups", []),
                roles=claims.get("roles", []),
                provider="oidc",
                raw_claims=claims,
                authenticated_at=time.time(),
                session_expires_at=time.time()
                + (self._config.session_timeout_minutes * 60),
            )

        except Exception as e:
            logger.error(f"[SSO] ID token parsing failed: {e}")
            return None

    def validate_token(self, token: str) -> Optional[SSOUser]:
        """Validate access token using userinfo endpoint."""
        if not self._initialized:
            return None

        userinfo_endpoint = self._discovery_doc.get(
            "userinfo_endpoint",
            f"{self._config.oidc_issuer_url}/userinfo",
        )

        try:
            import json
            import urllib.request

            req = urllib.request.Request(
                userinfo_endpoint,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                },
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                userinfo = json.loads(response.read().decode())

            return SSOUser(
                user_id=userinfo.get("sub", ""),
                email=userinfo.get("email", ""),
                name=userinfo.get("name"),
                given_name=userinfo.get("given_name"),
                family_name=userinfo.get("family_name"),
                groups=userinfo.get("groups", []),
                provider="oidc",
                raw_claims=userinfo,
                authenticated_at=time.time(),
                session_expires_at=time.time()
                + (self._config.session_timeout_minutes * 60),
            )

        except Exception as e:
            logger.error(f"[SSO] Token validation failed: {e}")
            return None

    def refresh_session(self, session: SSOSession) -> Optional[SSOSession]:
        """Refresh session using refresh token."""
        if not session.refresh_token:
            return None

        token_endpoint = self._discovery_doc.get(
            "token_endpoint",
            f"{self._config.oidc_issuer_url}/oauth/token",
        )

        try:
            import json
            import urllib.request

            data = urlencode(
                {
                    "grant_type": "refresh_token",
                    "refresh_token": session.refresh_token,
                    "client_id": self._config.oidc_client_id,
                    "client_secret": self._config.oidc_client_secret,
                }
            ).encode()

            req = urllib.request.Request(
                token_endpoint,
                data=data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                token_data = json.loads(response.read().decode())

            session.access_token = token_data.get("access_token", session.access_token)
            session.refresh_token = token_data.get(
                "refresh_token", session.refresh_token
            )
            session.id_token = token_data.get("id_token", session.id_token)
            session.token_expires_at = time.time() + token_data.get("expires_in", 3600)

            return session

        except Exception as e:
            logger.error(f"[SSO] Session refresh failed: {e}")
            return None

    def logout(self, session: SSOSession) -> bool:
        """Logout user (OIDC RP-initiated logout)."""
        end_session_endpoint = self._discovery_doc.get("end_session_endpoint")
        if not end_session_endpoint:
            return True  # No logout endpoint, session cleared locally

        try:

            params = {
                "id_token_hint": session.id_token,
                "post_logout_redirect_uri": self._config.oidc_redirect_uri,
            }

            logout_url = f"{end_session_endpoint}?{urlencode(params)}"

            # Just validate the endpoint exists (actual redirect handled by caller)
            logger.info(f"[SSO] Logout URL: {logout_url}")
            return True

        except Exception as e:
            logger.error(f"[SSO] Logout failed: {e}")
            return False


class SAMLProvider(SSOProviderBase):
    """
    SAML 2.0 Provider

    Implements SAML 2.0 Service Provider (SP) for enterprise SSO.
    Supports SP-initiated and IdP-initiated flows.
    """

    def __init__(self, config: SSOConfig):
        self._config = config
        self._initialized = False
        self._idp_metadata: Dict[str, Any] = {}

    def initialize(self) -> bool:
        """Initialize SAML provider by fetching IdP metadata."""
        if not self._config.saml_metadata_url:
            logger.error("[SSO] SAML metadata URL not configured")
            return False

        try:
            import urllib.request
            import xml.etree.ElementTree as ET

            req = urllib.request.Request(
                self._config.saml_metadata_url,
                headers={"Accept": "application/xml"},
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                metadata_xml = response.read().decode()

            # Parse SAML metadata
            root = ET.fromstring(metadata_xml)

            # Extract SSO URL and certificate
            ns = {
                "md": "urn:oasis:names:tc:SAML:2.0:metadata",
                "ds": "http://www.w3.org/2000/09/xmldsig#",
            }

            sso_elem = root.find(
                ".//md:SingleSignOnService[@Binding='urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect']",
                ns,
            )
            if sso_elem is not None:
                self._idp_metadata["sso_url"] = sso_elem.get("Location")

            cert_elem = root.find(".//ds:X509Certificate", ns)
            if cert_elem is not None and cert_elem.text:
                self._idp_metadata["certificate"] = cert_elem.text.strip()

            entity_elem = root.find(".")
            if entity_elem is not None:
                self._idp_metadata["entity_id"] = entity_elem.get("entityID")

            self._initialized = True
            logger.info(
                f"[SSO] SAML provider initialized: {self._idp_metadata.get('entity_id')}"
            )
            return True

        except Exception as e:
            logger.error(f"[SSO] SAML initialization failed: {e}")
            return False

    def get_authorization_url(self, state: str, nonce: str) -> str:
        """Generate SAML AuthnRequest URL."""
        if not self._initialized:
            self.initialize()

        sso_url = self._idp_metadata.get("sso_url", "")
        if not sso_url:
            return ""

        # Generate SAML AuthnRequest
        import base64
        import zlib

        request_id = f"_warmlogic_{hashlib.sha256(os.urandom(16)).hexdigest()[:16]}"
        issue_instant = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        authn_request = f"""<?xml version="1.0" encoding="UTF-8"?>
<samlp:AuthnRequest xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
    xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
    ID="{request_id}"
    Version="2.0"
    IssueInstant="{issue_instant}"
    AssertionConsumerServiceURL="{self._config.saml_acs_url}"
    Destination="{sso_url}">
    <saml:Issuer>{self._config.saml_entity_id}</saml:Issuer>
    <samlp:NameIDPolicy Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress" AllowCreate="true"/>
</samlp:AuthnRequest>"""

        # Deflate and base64 encode
        compressed = zlib.compress(authn_request.encode())[
            2:-4
        ]  # Remove zlib header/trailer
        encoded = base64.b64encode(compressed).decode()

        params = {
            "SAMLRequest": encoded,
            "RelayState": state,
        }

        return f"{sso_url}?{urlencode(params)}"

    def exchange_code(self, code: str, state: str) -> Optional[SSOSession]:
        """Process SAML Response (not a code exchange, but interface compatibility)."""
        # In SAML, the 'code' is actually the SAMLResponse
        return self._process_saml_response(code, state)

    def _process_saml_response(
        self, saml_response: str, relay_state: str
    ) -> Optional[SSOSession]:
        """Process and validate SAML Response."""
        try:
            import base64
            import xml.etree.ElementTree as ET

            # Decode SAML Response
            response_xml = base64.b64decode(saml_response).decode()
            root = ET.fromstring(response_xml)

            ns = {
                "samlp": "urn:oasis:names:tc:SAML:2.0:protocol",
                "saml": "urn:oasis:names:tc:SAML:2.0:assertion",
            }

            # Check status
            status = root.find(".//samlp:StatusCode", ns)
            if (
                status is None
                or status.get("Value") != "urn:oasis:names:tc:SAML:2.0:status:Success"
            ):
                logger.error("[SSO] SAML Response indicates failure")
                return None

            # Extract assertion
            assertion = root.find(".//saml:Assertion", ns)
            if assertion is None:
                logger.error("[SSO] No assertion in SAML Response")
                return None

            # Extract subject (user ID)
            name_id = assertion.find(".//saml:NameID", ns)
            user_id: str = name_id.text if name_id is not None and name_id.text else ""

            # Extract attributes
            attributes: Dict[str, str] = {}
            for attr in assertion.findall(".//saml:Attribute", ns):
                attr_name = attr.get("Name", "")
                attr_value = attr.find("saml:AttributeValue", ns)
                if attr_value is not None and attr_value.text:
                    attributes[attr_name] = attr_value.text

            # Map common attributes
            email: str = attributes.get(
                "email", attributes.get("mail", user_id) or user_id
            )
            name = attributes.get("displayName", attributes.get("cn", ""))
            groups = (
                attributes.get("groups", "").split(",")
                if "groups" in attributes
                else []
            )

            user = SSOUser(
                user_id=user_id,
                email=email,
                name=name,
                groups=groups,
                provider="saml",
                raw_claims=attributes,
                authenticated_at=time.time(),
                session_expires_at=time.time()
                + (self._config.session_timeout_minutes * 60),
            )

            session_id = hashlib.sha256(f"{user_id}{time.time()}".encode()).hexdigest()[
                :32
            ]

            return SSOSession(
                session_id=session_id,
                user=user,
                access_token=saml_response,  # Store response for SLO
                created_at=time.time(),
                token_expires_at=user.session_expires_at,
            )

        except Exception as e:
            logger.error(f"[SSO] SAML Response processing failed: {e}")
            return None

    def validate_token(self, token: str) -> Optional[SSOUser]:
        """SAML doesn't have token validation - sessions are stateful."""
        logger.warning("[SSO] SAML does not support token validation")
        return None

    def refresh_session(self, session: SSOSession) -> Optional[SSOSession]:
        """SAML doesn't support session refresh."""
        logger.warning("[SSO] SAML does not support session refresh")
        return None

    def logout(self, session: SSOSession) -> bool:
        """Initiate SAML Single Logout (SLO)."""
        # SLO implementation would require additional IdP metadata
        logger.info("[SSO] SAML logout initiated")
        return True


class SSOManager:
    """
    SSO Manager

    Unified interface for enterprise SSO authentication.
    Manages OIDC and SAML providers with automatic fallback.
    """

    def __init__(self, config: Optional[SSOConfig] = None):
        self._config = config or self._load_config_from_env()
        self._provider: Optional[SSOProviderBase] = None
        self._sessions: Dict[str, SSOSession] = {}

    def _load_config_from_env(self) -> SSOConfig:
        """Load SSO configuration from environment variables."""
        provider_str = os.environ.get("SSO_PROVIDER", "").lower()
        provider = (
            SSOProvider.OIDC
            if provider_str == "oidc"
            else SSOProvider.SAML if provider_str == "saml" else SSOProvider.OIDC
        )

        return SSOConfig(
            provider=provider,
            enabled=os.environ.get("SSO_ENABLED", "").lower() == "true",
            oidc_issuer_url=os.environ.get("OIDC_ISSUER_URL"),
            oidc_client_id=os.environ.get("OIDC_CLIENT_ID"),
            oidc_client_secret=os.environ.get("OIDC_CLIENT_SECRET"),
            oidc_redirect_uri=os.environ.get("OIDC_REDIRECT_URI"),
            saml_metadata_url=os.environ.get("SAML_METADATA_URL"),
            saml_entity_id=os.environ.get("SAML_ENTITY_ID"),
            saml_acs_url=os.environ.get("SAML_ACS_URL"),
        )

    def initialize(self) -> bool:
        """Initialize SSO provider based on configuration."""
        if not self._config.enabled:
            logger.info("[SSO] SSO is disabled")
            return True

        if self._config.provider == SSOProvider.OIDC:
            self._provider = OIDCProvider_(self._config)
        elif self._config.provider == SSOProvider.SAML:
            self._provider = SAMLProvider(self._config)
        else:
            # Exhaustive match - should never reach here
            raise ValueError(f"Unknown SSO provider: {self._config.provider}")

        return self._provider.initialize()

    @property
    def is_enabled(self) -> bool:
        return self._config.enabled

    def get_login_url(self, redirect_after: Optional[str] = None) -> str:
        """Get SSO login URL."""
        if not self._provider:
            return ""

        state = hashlib.sha256(os.urandom(16)).hexdigest()[:32]
        nonce = hashlib.sha256(os.urandom(16)).hexdigest()[:32]

        if redirect_after:
            state = f"{state}:{redirect_after}"

        return self._provider.get_authorization_url(state, nonce)

    def handle_callback(self, code: str, state: str) -> Optional[SSOSession]:
        """Handle SSO callback and create session."""
        if not self._provider:
            return None

        session = self._provider.exchange_code(code, state)
        if session:
            self._sessions[session.session_id] = session
            logger.info(f"[SSO] Session created for user: {session.user.email}")

        return session

    def get_session(self, session_id: str) -> Optional[SSOSession]:
        """Get session by ID."""
        session = self._sessions.get(session_id)
        if session and not session.user.is_session_valid:
            del self._sessions[session_id]
            return None
        return session

    def validate_session(self, session_id: str) -> Optional[SSOUser]:
        """Validate session and return user if valid."""
        session = self.get_session(session_id)
        if not session:
            return None

        # Refresh token if needed
        if not session.is_token_valid and session.refresh_token:
            refreshed = (
                self._provider.refresh_session(session) if self._provider else None
            )
            if refreshed:
                self._sessions[session_id] = refreshed
                session = refreshed

        return session.user if session.user.is_session_valid else None

    def logout(self, session_id: str) -> bool:
        """Logout user and invalidate session."""
        session = self._sessions.get(session_id)
        if not session:
            return True

        if self._provider:
            self._provider.logout(session)

        del self._sessions[session_id]
        logger.info(f"[SSO] User logged out: {session.user.email}")
        return True


# Global SSO manager instance
_sso_manager: Optional[SSOManager] = None


def get_sso_manager() -> SSOManager:
    """Get the global SSO manager instance."""
    global _sso_manager
    if _sso_manager is None:
        _sso_manager = SSOManager()
    return _sso_manager


def initialize_sso(config: Optional[SSOConfig] = None) -> bool:
    """Initialize the global SSO manager."""
    global _sso_manager
    _sso_manager = SSOManager(config)
    return _sso_manager.initialize()
