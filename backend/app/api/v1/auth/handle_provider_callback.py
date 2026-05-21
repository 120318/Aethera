import logging
from urllib.parse import urlencode

from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse

from app.services.config.settings_service import settings_service
from app.services.platform.auth_service import auth_service
from app.services.platform.auth_provider_service import AuthCallbackContext, auth_provider_service
from app.services.platform.external_auth_state_service import external_auth_state_service

router = APIRouter()
logger = logging.getLogger("app.auth.callback")


@router.get("/providers/{provider_id}/callback", name="handle_provider_callback")
async def handle_provider_callback(provider_id: str, request: Request, response: Response, code: str = "", state: str = "") -> RedirectResponse:
    cookie_value = request.cookies.get(external_auth_state_service.COOKIE_NAME)
    auth_state = external_auth_state_service.validate(cookie_value, provider_id, state)
    if auth_state is None or not code:
        return _build_error_redirect("/discover", "auth.externalStateInvalid")

    auth_addon = settings_service.get_addons_config().auth
    config = auth_provider_service.find_provider_config(auth_addon.providers, provider_id)
    provider = auth_provider_service.get_provider(config.type)
    redirect_uri = str(request.url_for("handle_provider_callback", provider_id=provider_id))

    try:
        identity = await provider.exchange_callback(
            config,
            AuthCallbackContext(
                code=code,
                redirect_uri=redirect_uri,
                code_verifier=auth_state.code_verifier,
                nonce=auth_state.nonce,
            ),
        )
        allowed = {email.strip().lower() for email in config.admin_emails if email.strip()}
        if identity.email.lower() not in allowed:
            return _build_error_redirect(auth_state.next_path, "auth.externalAdminUnauthorized")
        session = auth_service.issue_session()
        redirect = RedirectResponse(url=auth_state.next_path, status_code=302)
        redirect.set_cookie(
            key=auth_service.COOKIE_NAME,
            value=session.token,
            httponly=True,
            samesite="lax",
            secure=auth_service.is_https_request(request),
            max_age=auth_service.get_session_cookie_max_age_seconds(),
            path="/",
        )
        redirect.delete_cookie(key=external_auth_state_service.COOKIE_NAME, path="/")
        return redirect
    except Exception as exc:
        logger.exception("External authentication callback failed for provider=%s", provider_id)
        redirect = _build_error_redirect(auth_state.next_path, "auth.externalLoginFailed")
        redirect.delete_cookie(key=external_auth_state_service.COOKIE_NAME, path="/")
        return redirect


def _build_error_redirect(next_path: str, error_key: str) -> RedirectResponse:
    query = urlencode({"next": next_path, "error_key": error_key})
    return RedirectResponse(url=f"/login?{query}", status_code=302)
