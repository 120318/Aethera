import os
import uuid

os.environ.setdefault("CONFIG_ROOT", f"/tmp/aethera-test-config-{uuid.uuid4()}")

from app.services.platform.auth_service import AuthService
from app.services.config.settings_service import settings_service


def test_session_persists_across_service_restart():
    svc1 = AuthService()
    svc1.set_password("pw")
    sess = svc1.issue_session()

    svc2 = AuthService()
    restored = svc2._get_session(sess.token)
    assert restored is not None
    assert restored.username == "admin"


def test_infinite_session_uses_persistent_cookie():
    svc = AuthService()
    svc.set_password("pw")
    settings_service.update_auth_config(enabled=True, session_ttl_seconds=0)

    assert svc.get_session_ttl_seconds() == 0
    assert svc.get_session_cookie_max_age_seconds() > 0
