import unittest

from app.schemas.constants.event_types import EventTypes
from app.addons.registry import AddonDescriptor, AddonJobSpec, addon_service
from app.schemas.exception.exceptions import ConfigurationException
from app.services.platform.auth_provider_service import auth_provider_service
from app.services.platform.notification_channel_service import notification_channel_service


def noop():
    return


def dummy_event_patterns():
    return [EventTypes.DOWNLOAD_STARTED]


def dummy_jobs():
    return [
        AddonJobSpec(
            id="dummy.job1",
            name="Job 1",
            trigger="interval",
            interval_seconds=60,
            handler=noop,
            max_instances=1,
        )
    ]


def build_dummy_addon() -> AddonDescriptor:
    return AddonDescriptor(
        name="dummy",
        subscribed_event_patterns=dummy_event_patterns,
        scheduled_jobs=dummy_jobs,
    )


class TestAddonServiceContracts(unittest.TestCase):
    def test_list_addon_jobs_aggregates(self):
        addon_service.register(build_dummy_addon())
        jobs = addon_service.list_addon_jobs()
        ids = {j.id for j in jobs}
        self.assertIn("dummy.job1", ids)

    def test_event_pattern_contracts(self):
        patterns = build_dummy_addon().subscribed_event_patterns()
        self.assertIn(EventTypes.DOWNLOAD_STARTED, patterns)

    def test_oidc_provider_discovery_is_disabled_by_default(self):
        auth_provider_service.discover_and_register()

        self.assertFalse(auth_provider_service.supports("oidc"))

    def test_telegram_channel_discovery_is_disabled_by_default(self):
        notification_channel_service.discover_and_register()

        self.assertFalse(notification_channel_service.supports("telegram"))

    def test_disabled_telegram_channel_is_not_resolvable(self):
        notification_channel_service.discover_and_register()

        with self.assertRaises(ConfigurationException):
            notification_channel_service.get_channel("telegram")
