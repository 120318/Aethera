from __future__ import annotations

import hashlib
from urllib.parse import urlencode

import httpx
import jwt
from jwt import PyJWKClient

from app.schemas.config import AuthProviderConfig, OIDCAuthProviderConfig
from app.schemas.exception.exceptions import AuthenticationException, ConfigurationException
from app.schemas.runtime.auth_provider import (
    AuthCallbackContext,
    AuthIdentity,
    AuthStartResult,
    OIDCClaimsEnvelope,
    OIDCDiscoveryDocument,
    OIDCTokenResponse,
)
from app.services.platform.auth_provider_service import BaseAuthProvider


class OIDCAuthProvider(BaseAuthProvider):
    @property
    def provider_type(self) -> str:
        return "oidc"

    def build_authorize_redirect(
        self,
        config: AuthProviderConfig,
        redirect_uri: str,
        state: str,
        nonce: str,
        code_verifier: str,
    ) -> AuthStartResult:
        oidc_config = OIDCAuthProviderConfig.model_validate(config)
        discovery = self._resolve_discovery(oidc_config)
        params = urlencode(
            {
                "response_type": "code",
                "client_id": oidc_config.client_id,
                "redirect_uri": redirect_uri,
                "scope": " ".join(oidc_config.scopes or ["openid", "profile", "email"]),
                "state": state,
                "nonce": nonce,
                "code_challenge": self._code_challenge(code_verifier),
                "code_challenge_method": "S256",
            }
        )
        return AuthStartResult(redirect_url=f"{discovery.authorization_endpoint}?{params}")

    async def exchange_callback(
        self,
        config: AuthProviderConfig,
        context: AuthCallbackContext,
    ) -> AuthIdentity:
        oidc_config = OIDCAuthProviderConfig.model_validate(config)
        discovery = self._resolve_discovery(oidc_config)
        token_response = await self._exchange_code(oidc_config, discovery, context)
        claims = self._decode_id_token(oidc_config, discovery, token_response.id_token, context.nonce)
        userinfo = await self._load_userinfo(discovery, token_response.access_token)
        email = self._read_string_claim(userinfo, claims, oidc_config.claim_mappings.email)
        username = self._read_string_claim(userinfo, claims, oidc_config.claim_mappings.username) or email
        subject = self._read_string_claim(claims, userinfo, "sub")
        groups = self._read_groups_claim(userinfo, claims, oidc_config.claim_mappings.groups)

        if not subject:
            raise AuthenticationException("backendErrors.externalIdentitySubjectMissing")
        if not email:
            raise AuthenticationException("backendErrors.externalIdentityEmailMissing")

        return AuthIdentity(
            provider_id=oidc_config.id,
            subject=subject,
            email=str(email).lower(),
            username=str(username or email),
            groups=groups,
        )

    def _resolve_discovery(self, config: OIDCAuthProviderConfig) -> OIDCDiscoveryDocument:
        if config.discovery_enabled:
            return self._load_discovery_document(config)
        return OIDCDiscoveryDocument(
            issuer=config.issuer_url,
            authorization_endpoint=config.authorization_endpoint,
            token_endpoint=config.token_endpoint,
            userinfo_endpoint=config.userinfo_endpoint,
            jwks_uri=config.jwks_uri,
        )

    def _load_discovery_document(self, config: OIDCAuthProviderConfig) -> OIDCDiscoveryDocument:
        issuer = config.issuer_url.rstrip("/")
        if not issuer:
            raise ConfigurationException("backendErrors.config.oidcIssuerUrlRequired")
        url = f"{issuer}/.well-known/openid-configuration"
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url)
            response.raise_for_status()
            payload = OIDCDiscoveryDocument.model_validate(response.json())
        return payload.model_copy(update={"issuer": payload.issuer or issuer})

    async def _exchange_code(
        self,
        config: OIDCAuthProviderConfig,
        discovery: OIDCDiscoveryDocument,
        context: AuthCallbackContext,
    ) -> OIDCTokenResponse:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                discovery.token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "code": context.code,
                    "redirect_uri": context.redirect_uri,
                    "client_id": config.client_id,
                    "client_secret": config.client_secret,
                    "code_verifier": context.code_verifier,
                },
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            return OIDCTokenResponse.model_validate(response.json())

    async def _load_userinfo(self, discovery: OIDCDiscoveryDocument, access_token: str) -> OIDCClaimsEnvelope:
        if not discovery.userinfo_endpoint:
            return OIDCClaimsEnvelope()
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                discovery.userinfo_endpoint,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
            )
            response.raise_for_status()
            return OIDCClaimsEnvelope.model_validate(response.json())

    def _decode_id_token(
        self,
        config: OIDCAuthProviderConfig,
        discovery: OIDCDiscoveryDocument,
        id_token: str,
        expected_nonce: str,
    ) -> OIDCClaimsEnvelope:
        if not id_token:
            raise AuthenticationException("backendErrors.externalIdentityTokenMissing")
        jwk_client = PyJWKClient(discovery.jwks_uri)
        signing_key = jwk_client.get_signing_key_from_jwt(id_token)
        decoded = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"],
            audience=config.client_id,
            issuer=discovery.issuer,
        )
        claims = OIDCClaimsEnvelope.model_validate(decoded)
        if claims.nonce != expected_nonce:
            raise AuthenticationException("backendErrors.externalIdentityNonceMismatch")
        return claims

    def _read_string_claim(self, primary: OIDCClaimsEnvelope, fallback: OIDCClaimsEnvelope, key: str) -> str:
        primary_value = primary.read_string(key)
        if primary_value:
            return primary_value
        return fallback.read_string(key)

    def _read_groups_claim(self, primary: OIDCClaimsEnvelope, fallback: OIDCClaimsEnvelope, key: str) -> list[str]:
        primary_value = primary.read_groups(key)
        if primary_value:
            return primary_value
        return fallback.read_groups(key)

    def _code_challenge(self, code_verifier: str) -> str:
        digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        return jwt.utils.base64url_encode(digest).decode("utf-8")
