"""
Tests for JWT authentication and context extraction.
"""

import pytest
import json
import base64
from datetime import datetime

from vizu_supabase_client.auth_context import (
    AuthContext,
    JWTContextExtractor,
    get_jwt_extractor,
)


class TestAuthContext:
    """Tests for AuthContext."""

    def test_auth_context_creation(self):
        """Test basic auth context creation."""
        ctx = AuthContext(
            user_id="user123",
            tenant_id="tenant456",
            role="analyst",
            email="user@example.com",
        )
        assert ctx.user_id == "user123"
        assert ctx.tenant_id == "tenant456"
        assert ctx.role == "analyst"

    def test_auth_context_to_dict(self):
        """Test conversion to dict."""
        ctx = AuthContext(
            user_id="user123",
            tenant_id="tenant456",
            role="analyst",
        )
        d = ctx.to_dict()
        assert d["user_id"] == "user123"
        assert d["tenant_id"] == "tenant456"
        assert d["role"] == "analyst"

    def test_auth_context_validate_valid(self):
        """Test validation of valid context."""
        ctx = AuthContext(
            user_id="user123",
            tenant_id="tenant456",
            role="analyst",
        )
        assert ctx.validate() is True

    def test_auth_context_validate_missing_user_id(self):
        """Test validation fails with missing user_id."""
        ctx = AuthContext(
            user_id="",
            tenant_id="tenant456",
            role="analyst",
        )
        assert ctx.validate() is False

    def test_auth_context_validate_missing_tenant_id(self):
        """Test validation fails with missing tenant_id."""
        ctx = AuthContext(
            user_id="user123",
            tenant_id="",
            role="analyst",
        )
        assert ctx.validate() is False

    def test_auth_context_validate_missing_role(self):
        """Test validation fails with missing role."""
        ctx = AuthContext(
            user_id="user123",
            tenant_id="tenant456",
            role="",
        )
        assert ctx.validate() is False

    def test_auth_context_is_expired_no_exp(self):
        """Test is_expired returns False when no exp claim."""
        ctx = AuthContext(
            user_id="user123",
            tenant_id="tenant456",
            role="analyst",
        )
        assert ctx.is_expired() is False

    def test_auth_context_is_expired_future(self):
        """Test is_expired returns False for future expiry."""
        future_timestamp = int((datetime.utcnow().timestamp())) + 3600  # 1 hour
        ctx = AuthContext(
            user_id="user123",
            tenant_id="tenant456",
            role="analyst",
            expires_at=future_timestamp,
        )
        assert ctx.is_expired() is False

    def test_auth_context_is_expired_past(self):
        """Test is_expired returns True for past expiry."""
        past_timestamp = int(datetime.utcnow().timestamp()) - 3600  # 1 hour ago
        ctx = AuthContext(
            user_id="user123",
            tenant_id="tenant456",
            role="analyst",
            expires_at=past_timestamp,
        )
        assert ctx.is_expired() is True


class TestJWTContextExtractor:
    """Tests for JWTContextExtractor."""

    @pytest.fixture
    def extractor(self):
        """Create default extractor."""
        return JWTContextExtractor()

    @pytest.fixture
    def sample_payload(self):
        """Create sample JWT payload."""
        return {
            "sub": "user123",
            "tenant_id": "tenant456",
            "role": "analyst",
            "email": "user@example.com",
            "scope": "read write",
            "iat": 1609459200,
            "exp": 1609545600,
        }

    def test_extractor_initialization(self, extractor):
        """Test extractor initialization."""
        assert extractor.claims["user_id_claim"] == "sub"
        assert extractor.claims["tenant_id_claim"] == "tenant_id"
        assert extractor.claims["role_claim"] == "role"

    def test_extractor_custom_claims(self):
        """Test extractor with custom claim mapping."""
        custom_mapping = {
            "user_id_claim": "user_sub",
            "tenant_id_claim": "org_id",
        }
        extractor = JWTContextExtractor(claim_mapping=custom_mapping)
        assert extractor.claims["user_id_claim"] == "user_sub"
        assert extractor.claims["tenant_id_claim"] == "org_id"

    def test_extract_valid_payload(self, extractor, sample_payload):
        """Test extracting valid payload."""
        ctx = extractor.extract(sample_payload)
        assert ctx.user_id == "user123"
        assert ctx.tenant_id == "tenant456"
        assert ctx.role == "analyst"
        assert ctx.email == "user@example.com"
        assert ctx.scopes == ["read", "write"]

    def test_extract_missing_user_id(self, extractor, sample_payload):
        """Test extraction fails when user_id claim missing."""
        del sample_payload["sub"]
        with pytest.raises(ValueError, match="Missing required claim"):
            extractor.extract(sample_payload)

    def test_extract_missing_tenant_id(self, extractor, sample_payload):
        """Test extraction fails when tenant_id claim missing."""
        del sample_payload["tenant_id"]
        with pytest.raises(ValueError, match="Missing required claim"):
            extractor.extract(sample_payload)

    def test_extract_missing_role(self, extractor, sample_payload):
        """Test extraction fails when role claim missing."""
        del sample_payload["role"]
        with pytest.raises(ValueError, match="Missing required claim"):
            extractor.extract(sample_payload)

    def test_extract_from_header_valid(self, extractor, sample_payload):
        """Test extracting from Authorization header."""
        # Create a valid JWT (without signature verification)
        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "HS256"}).encode()
        ).rstrip(b"=").decode()
        payload = base64.urlsafe_b64encode(
            json.dumps(sample_payload).encode()
        ).rstrip(b"=").decode()
        signature = "dummy_signature"
        token = f"{header}.{payload}.{signature}"

        auth_header = f"Bearer {token}"
        ctx = extractor.extract_from_header(auth_header)
        assert ctx.user_id == "user123"
        assert ctx.tenant_id == "tenant456"

    def test_extract_from_header_invalid_format(self, extractor):
        """Test header extraction with invalid format."""
        with pytest.raises(ValueError, match="Invalid Authorization header format"):
            extractor.extract_from_header("InvalidHeader")

    def test_extract_from_header_empty(self, extractor):
        """Test header extraction with empty header."""
        with pytest.raises(ValueError, match="empty"):
            extractor.extract_from_header("")

    def test_extract_from_token_valid(self, extractor, sample_payload):
        """Test extracting from token string."""
        # Create a valid JWT
        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "HS256"}).encode()
        ).rstrip(b"=").decode()
        payload = base64.urlsafe_b64encode(
            json.dumps(sample_payload).encode()
        ).rstrip(b"=").decode()
        token = f"{header}.{payload}.signature"

        ctx = extractor.extract_from_token(token)
        assert ctx.user_id == "user123"

    def test_extract_from_token_invalid_format(self, extractor):
        """Test token extraction with invalid format."""
        with pytest.raises(ValueError, match="Invalid JWT format"):
            extractor.extract_from_token("invalid.token")

    def test_extract_from_token_invalid_payload(self, extractor):
        """Test token extraction with invalid payload."""
        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "HS256"}).encode()
        ).rstrip(b"=").decode()
        invalid_payload = "invalid_json"
        token = f"{header}.{invalid_payload}.signature"

        with pytest.raises(ValueError):
            extractor.extract_from_token(token)

    def test_get_jwt_extractor_singleton(self):
        """Test that get_jwt_extractor returns singleton."""
        ext1 = get_jwt_extractor()
        ext2 = get_jwt_extractor()
        assert ext1 is ext2


class TestJWTContextExtractorIntegration:
    """Integration tests for JWT extraction."""

    def test_full_flow_header_to_context(self):
        """Test full flow from Authorization header to AuthContext."""
        payload = {
            "sub": "alice123",
            "tenant_id": "acme_corp",
            "role": "analyst",
            "email": "alice@acme.com",
            "exp": int(datetime.utcnow().timestamp()) + 3600,
        }

        # Create JWT
        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
        ).rstrip(b"=").decode()
        payload_b64 = base64.urlsafe_b64encode(
            json.dumps(payload).encode()
        ).rstrip(b"=").decode()
        token = f"{header}.{payload_b64}.sig"
        auth_header = f"Bearer {token}"

        # Extract
        extractor = JWTContextExtractor()
        ctx = extractor.extract_from_header(auth_header)

        # Verify
        assert ctx.user_id == "alice123"
        assert ctx.tenant_id == "acme_corp"
        assert ctx.role == "analyst"
        assert ctx.validate() is True
        assert ctx.is_expired() is False
