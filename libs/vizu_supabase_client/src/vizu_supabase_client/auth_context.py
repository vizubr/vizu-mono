"""
JWT authentication and context extraction for Supabase.

This module handles JWT token parsing and claim extraction for
tenant isolation and role-based access control.
"""

import logging
import json
from dataclasses import dataclass
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class AuthContext:
    """Extracted authentication context from JWT claims."""
    user_id: str
    tenant_id: str
    role: str
    email: Optional[str] = None
    scopes: Optional[list] = None
    issued_at: Optional[int] = None
    expires_at: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "role": self.role,
            "email": self.email,
            "scopes": self.scopes,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
        }

    def is_expired(self) -> bool:
        """Check if token is expired (if exp claim available)."""
        if self.expires_at is None:
            return False
        return datetime.utcnow().timestamp() > self.expires_at

    def validate(self) -> bool:
        """Validate context has required fields."""
        return bool(self.user_id and self.tenant_id and self.role)


class JWTContextExtractor:
    """Extracts AuthContext from JWT claims."""

    # Default claim names (can be overridden)
    DEFAULT_CLAIMS = {
        "user_id_claim": "sub",  # Standard: "sub" = subject (user ID)
        "tenant_id_claim": "tenant_id",  # Custom claim for tenant
        "role_claim": "role",  # Custom claim for role
        "email_claim": "email",
        "scopes_claim": "scope",  # Space-separated scopes
        "iat_claim": "iat",  # Issued at
        "exp_claim": "exp",  # Expiration
    }

    def __init__(self, claim_mapping: Optional[Dict[str, str]] = None):
        """
        Initialize extractor with optional custom claim mapping.

        Args:
            claim_mapping: Dict mapping standard claim keys to actual JWT claim names.
                          E.g., {"tenant_id_claim": "org_id"} to use "org_id" instead of "tenant_id".
        """
        self.claims = {**self.DEFAULT_CLAIMS}
        if claim_mapping:
            self.claims.update(claim_mapping)
        logger.info(f"JWTContextExtractor initialized with claims: {self.claims}")

    def extract(self, jwt_payload: Dict[str, Any]) -> AuthContext:
        """
        Extract AuthContext from JWT payload (decoded).

        Args:
            jwt_payload: Decoded JWT claims dictionary.

        Returns:
            AuthContext instance.

        Raises:
            ValueError: If required claims are missing.
        """
        user_id = jwt_payload.get(self.claims["user_id_claim"])
        tenant_id = jwt_payload.get(self.claims["tenant_id_claim"])
        role = jwt_payload.get(self.claims["role_claim"])

        if not user_id:
            raise ValueError(
                f"Missing required claim: {self.claims['user_id_claim']}"
            )
        if not tenant_id:
            raise ValueError(
                f"Missing required claim: {self.claims['tenant_id_claim']}"
            )
        if not role:
            raise ValueError(
                f"Missing required claim: {self.claims['role_claim']}"
            )

        # Optional claims
        email = jwt_payload.get(self.claims["email_claim"])
        scopes_str = jwt_payload.get(self.claims["scopes_claim"])
        scopes = scopes_str.split() if isinstance(scopes_str, str) else scopes_str

        context = AuthContext(
            user_id=user_id,
            tenant_id=tenant_id,
            role=role,
            email=email,
            scopes=scopes,
            issued_at=jwt_payload.get(self.claims["iat_claim"]),
            expires_at=jwt_payload.get(self.claims["exp_claim"]),
        )

        if not context.validate():
            raise ValueError("Extracted context failed validation")

        logger.debug(
            f"Extracted AuthContext: user={user_id}, tenant={tenant_id}, role={role}"
        )
        return context

    def extract_from_header(self, auth_header: str) -> AuthContext:
        """
        Extract AuthContext from Authorization header.

        Supports "Bearer <token>" format.

        Args:
            auth_header: Authorization header value (e.g., "Bearer eyJhbG...")

        Returns:
            AuthContext instance.

        Raises:
            ValueError: If header format is invalid or token cannot be decoded.
        """
        if not auth_header:
            raise ValueError("Authorization header is empty")

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise ValueError("Invalid Authorization header format. Expected: Bearer <token>")

        token = parts[1]
        return self.extract_from_token(token)

    def extract_from_token(self, token: str) -> AuthContext:
        """
        Extract AuthContext from JWT token string (base64-encoded).

        This is a simplified decoder that doesn't verify the signature.
        For production, use PyJWT library with signature verification.

        Args:
            token: JWT token string.

        Returns:
            AuthContext instance.

        Raises:
            ValueError: If token is malformed.
        """
        try:
            # JWT format: header.payload.signature
            parts = token.split(".")
            if len(parts) != 3:
                raise ValueError("Invalid JWT format (expected 3 parts)")

            # Decode payload (base64)
            payload_part = parts[1]
            # Add padding if necessary
            padding = 4 - len(payload_part) % 4
            if padding != 4:
                payload_part += "=" * padding

            import base64
            payload_json = base64.urlsafe_b64decode(payload_part)
            payload = json.loads(payload_json)

            return self.extract(payload)

        except (ValueError, KeyError, json.JSONDecodeError) as e:
            logger.error(f"Failed to extract JWT: {e}")
            raise ValueError(f"Failed to extract context from token: {e}")


# Singleton instance
_jwt_extractor: Optional[JWTContextExtractor] = None


def get_jwt_extractor(
    claim_mapping: Optional[Dict[str, str]] = None,
) -> JWTContextExtractor:
    """
    Get or create the default JWT extractor.

    Args:
        claim_mapping: Custom claim mapping (only used on first call).

    Returns:
        JWTContextExtractor instance.
    """
    global _jwt_extractor
    if _jwt_extractor is None:
        _jwt_extractor = JWTContextExtractor(claim_mapping)
    return _jwt_extractor
