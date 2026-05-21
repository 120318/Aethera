import importlib
import os
import pkgutil
from abc import ABC, abstractmethod

from app.core.feature_flags import oidc_auth_enabled
from app.schemas.config import AuthProviderConfig
from app.schemas.exception.exceptions import AuthenticationException, ConfigurationException
from app.schemas.runtime.auth_provider import (
    AuthCallbackContext,
    AuthIdentity,
    AuthProviderSummary,
    AuthStartResult,
)


class BaseAuthProvider(ABC):
    @property
    @abstractmethod
    def provider_type(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def build_authorize_redirect(
        self,
        config: AuthProviderConfig,
        redirect_uri: str,
        state: str,
        nonce: str,
        code_verifier: str,
    ) -> AuthStartResult:
        raise NotImplementedError

    @abstractmethod
    async def exchange_callback(
        self,
        config: AuthProviderConfig,
        context: AuthCallbackContext,
    ) -> AuthIdentity:
        raise NotImplementedError


class AuthProviderService:
    def __init__(self) -> None:
        self._providers: dict[str, BaseAuthProvider] = {}

    def register(self, provider: BaseAuthProvider) -> None:
        self._providers[provider.provider_type] = provider

    def discover_and_register(self) -> None:
        from app.services.integration.auth import providers as auth_providers_pkg

        package_path = os.path.dirname(auth_providers_pkg.__file__)
        for _, module_name, is_pkg in pkgutil.iter_modules([package_path]):
            if not is_pkg:
                continue
            if module_name == "oidc" and not oidc_auth_enabled():
                continue
            importlib.import_module(f"app.services.integration.auth.providers.{module_name}")

    def supports(self, provider_type: str) -> bool:
        return provider_type in self._providers

    def get_provider(self, provider_type: str) -> BaseAuthProvider:
        if provider_type not in self._providers:
            raise ConfigurationException("backendErrors.config.authProviderTypeUnsupported", params={"type": provider_type})
        return self._providers[provider_type]

    def list_provider_summaries(self, configs: list[AuthProviderConfig]) -> list[AuthProviderSummary]:
        items: list[AuthProviderSummary] = []
        for config in configs:
            if not config.enabled:
                continue
            if not self.supports(config.type):
                continue
            items.append(AuthProviderSummary(id=config.id, type=config.type, name=config.name or config.id))
        return items

    def find_provider_config(self, configs: list[AuthProviderConfig], provider_id: str) -> AuthProviderConfig:
        for config in configs:
            if config.id == provider_id:
                return config
        raise AuthenticationException("backendErrors.authenticationProviderNotFound")


auth_provider_service = AuthProviderService()
