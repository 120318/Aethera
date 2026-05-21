from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.schemas.config import DownloadConfig, MovieNamingTemplateConfig, QBittorrentConfig, TVNamingTemplateConfig
from app.schemas.domain.filter_config import FilterConfig
from app.schemas.domain.quality_profile import QualityProfile
from app.schemas.domain.subscription_filters import SubscriptionFilters
from app.schemas.exception import ConfigurationException
from app.services.config.filter_preset_settings import (
    DEFAULT_FILTER_1080P_ID,
    DEFAULT_FILTER_4K_ID,
    DEFAULT_FILTER_DOLBY_VISION_ID,
    DEFAULT_FILTER_HDR_ID,
    FilterPresetSettings,
)
from app.services.config.naming_template_settings import (
    DEFAULT_MOVIE_TEMPLATE_ID,
    DEFAULT_TV_TEMPLATE_ID,
    NamingTemplateSettings,
)
from app.services.config.quality_profile_settings import DEFAULT_QUALITY_PROFILE_ID, QualityProfileSettings
from app.services.config.settings_service import SettingsService


class _FakeCollection:
    def __init__(self, items):
        self._items = list(items)

    def list(self):
        return list(self._items)

    def replace(self, items):
        self._items = list(items)


class _FakeSession:
    def __init__(self, count):
        self._count = count

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def scalar(self, _stmt):
        return self._count


class _FakeSectionRepository:
    def __init__(self, sections):
        self._sections = dict(sections)

    def get_section(self, section):
        return self._sections.get(section)

    def replace_sections(self, sections):
        self._sections.update(sections)


def _build_quality_service(*, profiles):
    sqlite_repo = SimpleNamespace(
        quality_profiles=_FakeCollection(profiles),
    )
    return QualityProfileSettings(sqlite_repo)


def _build_filter_service(*, profiles, filters):
    sqlite_repo = SimpleNamespace(
        quality_profiles=_FakeCollection(profiles),
        filter_presets=_FakeCollection(filters),
    )
    quality_profiles = QualityProfileSettings(sqlite_repo)
    return FilterPresetSettings(sqlite_repo, quality_profiles)


def _build_template_service(*, naming_templates=None):
    sqlite_repo = SimpleNamespace(
        naming_templates=_FakeCollection(naming_templates or []),
    )
    return NamingTemplateSettings(sqlite_repo)


def test_delete_quality_profile_rejects_filter_preset_references():
    profile = QualityProfile(id="qp-in-use", name="In Use")
    service = _build_quality_service(profiles=[profile])

    with pytest.raises(ConfigurationException, match="backendErrors.config.qualityProfileReferencedByFilters"):
        service.delete("qp-in-use", ["4K"])


def test_delete_quality_profile_rejects_media_download_config_references(monkeypatch):
    profile = QualityProfile(id="qp-in-use", name="In Use")
    service = _build_quality_service(profiles=[profile])

    monkeypatch.setattr(
        "app.services.config.quality_profile_settings.SessionLocal",
        lambda: _FakeSession(2),
    )

    with pytest.raises(ConfigurationException, match="backendErrors.config.qualityProfileReferencedByMediaConfigs"):
        service.delete("qp-in-use", [])


def test_update_quality_profile_preserves_a_default_when_unsetting_current_default():
    default_profile = QualityProfile(id="qp-default", name="Default", active_default=True)
    other_profile = QualityProfile(id="qp-other", name="Other", active_default=False)
    service = _build_quality_service(profiles=[default_profile, other_profile])

    updated = service.update("qp-default", active_default=False)

    assert updated is not None
    profiles = service.list()
    assert sum(1 for item in profiles if item.active_default) == 1
    assert next(item for item in profiles if item.id == "qp-default").active_default is True


def test_ensure_default_quality_profiles_matches_seed_profile_shape():
    service = _build_quality_service(profiles=[])

    service.ensure_defaults()

    profiles = service.list()
    assert len(profiles) == 1
    profile = profiles[0]
    assert profile.id == DEFAULT_QUALITY_PROFILE_ID
    assert profile.name == "Default quality profile"
    assert profile.active_default is True
    assert profile.ranking.dimension_order == [
        "resolution",
        "hdr_type",
        "source",
        "resource_form",
        "audio_codec",
        "video_codec",
        "audio_channels",
    ]
    assert [str(item) for item in profile.ranking.hdr_type] == [
        "Dolby Vision",
        "HDR10+",
        "HDR10",
    ]
    assert [str(item) for item in profile.ranking.video_codec] == [
        "HEVC",
        "AV1",
        "AVC",
    ]
    assert [str(item) for item in profile.ranking.audio_codec] == [
        "Dolby Atmos",
        "DTS-X",
        "TrueHD",
        "DTS-HD MA",
        "DTS-HD",
        "DTS",
        "DDP",
        "AC3",
        "FLAC",
        "AAC",
    ]


def test_ensure_default_filter_presets_uses_stable_builtin_ids():
    quality_profile = QualityProfile(id=DEFAULT_QUALITY_PROFILE_ID, name="Default", active_default=True)
    service = _build_filter_service(profiles=[quality_profile], filters=[])

    service.ensure_defaults()

    filters = service.list()
    assert [item.id for item in filters] == [
        DEFAULT_FILTER_DOLBY_VISION_ID,
        DEFAULT_FILTER_HDR_ID,
        DEFAULT_FILTER_4K_ID,
        DEFAULT_FILTER_1080P_ID,
    ]
    assert all(item.quality_profile_id == DEFAULT_QUALITY_PROFILE_ID for item in filters)
    assert [item.name for item in filters] == ["Dolby Vision", "HDR", "4K", "1080p"]


def test_ensure_default_naming_templates_uses_stable_builtin_ids_when_missing():
    service = _build_template_service(naming_templates=[])

    service.ensure_defaults()

    templates = service.list()
    assert len(templates) == 2
    movie_default = next(item for item in templates if item.id == DEFAULT_MOVIE_TEMPLATE_ID)
    tv_default = next(item for item in templates if item.id == DEFAULT_TV_TEMPLATE_ID)
    assert movie_default.name == "Default movie template"
    assert movie_default.is_default is True
    assert tv_default.name == "Default TV template"
    assert tv_default.is_default is True


def test_ensure_default_naming_templates_preserves_existing_default_template_content():
    movie_template = MovieNamingTemplateConfig(
        id="movie-custom",
        name="Sample",
        dir_template="Movies/{title}",
        file_template="{title}.custom",
        enabled=True,
        is_default=True,
    )
    tv_template = TVNamingTemplateConfig(
        id="tv-custom",
        name="Sample",
        dir_template="Shows/{title}/S{season:00}",
        file_template="{title}.S{season:00}E{episode:00}.custom",
        enabled=True,
        is_default=True,
    )
    service = _build_template_service(naming_templates=[movie_template, tv_template])

    service.ensure_defaults()

    templates = service.list()
    assert len(templates) == 2
    assert next(item for item in templates if item.id == "movie-custom").name == "Sample"
    assert next(item for item in templates if item.id == "movie-custom").dir_template == "Movies/{title}"
    assert next(item for item in templates if item.id == "movie-custom").file_template == "{title}.custom"
    assert next(item for item in templates if item.id == "tv-custom").name == "Sample"
    assert next(item for item in templates if item.id == "tv-custom").dir_template == "Shows/{title}/S{season:00}"
    assert next(item for item in templates if item.id == "tv-custom").file_template == "{title}.S{season:00}E{episode:00}.custom"


def test_update_download_config_preserves_existing_default_downloader():
    service = SettingsService()
    downloader_id = f"downloader-{uuid4()}"
    service.create_downloader(
        QBittorrentConfig(
            id=downloader_id,
            name="Downloader",
            url=f"http://qb-{downloader_id}.local",
        )
    )
    service.set_default_downloader(downloader_id)

    service.update_download_config(DownloadConfig(default_tag="NewTag"))

    assert service.get_default_downloader_id() == downloader_id
    assert service.get_system_tab_config()["download"].default_downloader_id == downloader_id


def test_base_config_uses_db_sections_without_yaml_fallback():
    service = SettingsService()
    service._sqlite_repo = _FakeSectionRepository(
        {
            "services": {
                "browse_source": "tmdb",
                "themoviedb": {"api_key": "db-tmdb-key", "proxy_images": True},
                "douban": {"discover_lists": ["movie_hot_gaia"], "proxy_images": False},
            },
            "system": {
                "download": {"default_downloader_id": "downloader-db", "default_tag": "DB"},
                "logging": {"level": "WARNING", "dir": "/config/logs", "file": "backend.log"},
            },
            "addons": {"danmu": {"enabled": True, "directory_ids": ["dir-db"]}},
            "auth": {"enabled": True, "session_ttl_seconds": 123},
        }
    )

    config = service._load_base_config()

    assert config.browse_source.value == "tmdb"
    assert config.themoviedb.api_key == "db-tmdb-key"
    assert config.download.default_tag == "DB"
    assert config.download.default_downloader_id == "downloader-db"
    assert config.logging.level == "WARNING"
    assert config.addons.danmu.directory_ids == ["dir-db"]
    assert config.auth.session_ttl_seconds == 123
