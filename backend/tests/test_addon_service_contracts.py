import unittest
from unittest.mock import patch

from app.schemas.constants.event_types import EventTypes
from app.addons.registry import (
    AddonArtifactTypeSpec,
    AddonCommandSpec,
    AddonDescriptor,
    AddonJobSpec,
    AddonProviderSpec,
    AddonRegistry,
    AddonResourceActionSpec,
    AddonSettingsSectionSpec,
    addon_service,
)
from app.addons.descriptors import _danmu_enabled, _notifications_enabled
from app.schemas.config import AddonsConfig, TelegramNotificationChannelConfig
from app.services.platform.auth_provider_service import auth_provider_service
from app.services.platform.notification_channel_service import notification_channel_service


def noop():
    return


def dummy_event_patterns():
    return [EventTypes.DOWNLOAD_COMPLETED]


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
    def test_danmu_addon_requires_an_output_directory(self):
        self.assertFalse(_danmu_enabled(AddonsConfig(danmu={"enabled": True})))
        self.assertTrue(
            _danmu_enabled(AddonsConfig(danmu={"enabled": True, "directory_ids": ["dir-1"]}))
        )

    def test_descriptor_declares_extension_contributions(self):
        addon = AddonDescriptor(
            name="sample",
            commands=[AddonCommandSpec(id="sample.generate")],
            resource_actions=[
                AddonResourceActionSpec(
                    id="sample.generate",
                    command_id="sample.generate",
                    target_type="library_file",
                )
            ],
            artifact_types=[AddonArtifactTypeSpec(id="sample_sidecar")],
            providers=[AddonProviderSpec(capability="sample", id="provider")],
            settings_sections=[AddonSettingsSectionSpec(id="sample")],
        )

        self.assertEqual("sample.generate", addon.commands[0].id)
        self.assertEqual("library_file", addon.resource_actions[0].target_type)
        self.assertEqual("sample_sidecar", addon.artifact_types[0].id)
        self.assertEqual("provider", addon.providers[0].id)
        self.assertEqual("sample", addon.settings_sections[0].id)

    def test_registry_rejects_duplicate_contribution_within_addon(self):
        registry = AddonRegistry()

        with self.assertRaisesRegex(ValueError, "Duplicate command id in addon sample"):
            registry.register(
                AddonDescriptor(
                    name="sample",
                    commands=[
                        AddonCommandSpec(id="sample.generate"),
                        AddonCommandSpec(id="sample.generate"),
                    ],
                )
            )

    def test_discovery_does_not_hide_invalid_descriptor_contracts(self):
        registry = AddonRegistry()

        with (
            patch("app.addons.descriptors.register_addons", side_effect=ValueError("invalid descriptor")),
            self.assertRaisesRegex(ValueError, "invalid descriptor"),
        ):
            registry.discover_and_register()

    def test_registry_rejects_resource_action_with_undeclared_command(self):
        registry = AddonRegistry()

        with self.assertRaisesRegex(ValueError, "references undeclared command sample.generate"):
            registry.register(
                AddonDescriptor(
                    name="sample",
                    resource_actions=[
                        AddonResourceActionSpec(
                            id="sample.generate",
                            command_id="sample.generate",
                            target_type="library_file",
                        )
                    ],
                )
            )

    def test_registry_rejects_duplicate_contribution_across_addons(self):
        registry = AddonRegistry()
        registry.register(
            AddonDescriptor(
                name="first",
                commands=[AddonCommandSpec(id="first.generate")],
                resource_actions=[
                    AddonResourceActionSpec(
                        id="sample.generate",
                        command_id="first.generate",
                        target_type="library_file",
                    )
                ],
            )
        )

        with self.assertRaisesRegex(ValueError, "owned by first and second"):
            registry.register(
                AddonDescriptor(
                    name="second",
                    commands=[AddonCommandSpec(id="second.generate")],
                    resource_actions=[
                        AddonResourceActionSpec(
                            id="sample.generate",
                            command_id="second.generate",
                            target_type="library_file",
                        )
                    ],
                )
            )

    def test_provider_ids_are_unique_within_capability(self):
        registry = AddonRegistry()
        registry.register(
            AddonDescriptor(
                name="danmu",
                providers=[AddonProviderSpec(capability="danmu", id="qq")],
            )
        )
        registry.register(
            AddonDescriptor(
                name="subtitles",
                providers=[AddonProviderSpec(capability="subtitles", id="qq")],
            )
        )

        self.assertEqual(["danmu", "subtitles"], [addon.name for addon in registry.list_addons()])

    def test_list_addon_jobs_aggregates(self):
        addon_service.register(build_dummy_addon())
        jobs = addon_service.list_addon_jobs()
        ids = {j.id for j in jobs}
        self.assertIn("dummy.job1", ids)

    def test_event_pattern_contracts(self):
        patterns = build_dummy_addon().subscribed_event_patterns()
        self.assertIn(EventTypes.DOWNLOAD_COMPLETED, patterns)

    def test_oidc_provider_discovery_is_disabled_by_default(self):
        auth_provider_service.discover_and_register()

        self.assertFalse(auth_provider_service.supports("oidc"))

    def test_telegram_channel_discovery_registers_channel_by_default(self):
        notification_channel_service.discover_and_register()

        self.assertTrue(notification_channel_service.supports("telegram"))

    def test_telegram_channel_is_resolvable_by_default(self):
        notification_channel_service.discover_and_register()

        self.assertEqual(notification_channel_service.get_channel("telegram").channel_type, "telegram")

    def test_notifications_addon_requires_configured_enabled_channel(self):
        notification_channel_service.discover_and_register()

        self.assertFalse(
            _notifications_enabled(
                AddonsConfig(
                    notifications={
                        "enabled": True,
                        "channels": [TelegramNotificationChannelConfig(name="Telegram", bot_token="", chat_id="chat")],
                    }
                )
            )
        )
        self.assertFalse(
            _notifications_enabled(
                AddonsConfig(
                    notifications={
                        "enabled": True,
                        "channels": [
                            TelegramNotificationChannelConfig(
                                name="Telegram",
                                enabled=False,
                                bot_token="token",
                                chat_id="chat",
                            )
                        ],
                    }
                )
            )
        )
        self.assertTrue(
            _notifications_enabled(
                AddonsConfig(
                    notifications={
                        "enabled": True,
                        "channels": [
                            TelegramNotificationChannelConfig(
                                name="Telegram",
                                bot_token="token",
                                chat_id="chat",
                            )
                        ],
                    }
                )
            )
        )
