import unittest

from app.schemas.domain.event import Event
from app.addons.registry import addon_service


class TestAddonContextValidation(unittest.IsolatedAsyncioTestCase):
    async def test_reserved_addon_run_event_is_not_dispatched(self):
        event = Event(type="addon.run.started", message="skip")
        self.assertFalse(addon_service.should_dispatch_event(event.type))
