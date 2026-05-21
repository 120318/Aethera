from app.core.feature_flags import oidc_auth_enabled

if oidc_auth_enabled():
    from app.services.integration.auth.providers.oidc.provider import OIDCAuthProvider
    from app.services.platform.auth_provider_service import auth_provider_service

    auth_provider_service.register(OIDCAuthProvider())
