from types import SimpleNamespace

import pytest

from app.schemas.config import DirectoryConfig, QBittorrentConfig
from app.schemas.domain.download import TaskStatus
from app.services.application.workflows.directory_migration import DirectoryMigrationRequest, DirectoryMigrationService
from app.services.domain.directory.migration import directory_migration_domain_service


class FakeTaskRepo:
    async def find_by_directory_id(self, directory_id):
        return []


class FakeTaskListRepo:
    def __init__(self, tasks):
        self.tasks = tasks

    async def find_by_directory_id(self, directory_id):
        return self.tasks


class FakeLibraryRepo:
    def __init__(self, files=None):
        self.files = files or []

    async def find_by_directory_id(self, directory_id):
        return self.files


class FakeSubscriptionRepo:
    def __init__(self, count):
        self.count = count
        self.updated = None

    async def count_by_directory_id(self, directory_id):
        return self.count

    async def update_directory_id(self, source_directory_id, target_directory_id):
        self.updated = (source_directory_id, target_directory_id)
        return self.count


@pytest.mark.asyncio
async def test_directory_migration_allows_subscription_only_refs(monkeypatch):
    source = DirectoryConfig(
        id="dir-old",
        name="Old",
        media_type="movie",
        path="/data/library/movie",
        download_path="/data/download/movie",
        downloader_id="old",
    )
    target = DirectoryConfig(
        id="dir-new",
        name="New",
        media_type="movie",
        path="/data/library/movie",
        download_path="/data/download/movie",
        downloader_id="new",
    )
    subscription_repo = FakeSubscriptionRepo(count=5)
    service = DirectoryMigrationService()
    directory_migration_domain_service._task_repo = FakeTaskRepo()
    directory_migration_domain_service._library_repo = FakeLibraryRepo()
    directory_migration_domain_service._subscription_repo = subscription_repo

    monkeypatch.setattr(
        "app.services.domain.directory.migration.settings_service.get_directory_by_id",
        lambda directory_id: source if directory_id == "dir-old" else target,
    )
    monkeypatch.setattr(
        "app.services.domain.directory.migration.settings_service.list_downloaders",
        lambda: [QBittorrentConfig(id="new", name="New", type="qbittorrent", url="http://qb")],
    )

    request = DirectoryMigrationRequest(target_directory_id="dir-new")
    preview = await service.preview("dir-old", request)

    assert preview.ok is True
    assert preview.task_count == 0
    assert preview.subscription_count == 5
    assert preview.migratable_subscription_count == 5

    result = await service.submit("dir-old", request)

    assert result.ok is True
    assert result.commands == []
    assert result.migrated_subscription_count == 5
    assert subscription_repo.updated == ("dir-old", "dir-new")


@pytest.mark.asyncio
async def test_directory_migration_submit_skips_already_migrating_tasks(monkeypatch):
    source = DirectoryConfig(
        id="dir-old",
        name="Old",
        media_type="movie",
        path="/data/library/movie",
        download_path="/data/download/movie",
        downloader_id="old",
    )
    target = DirectoryConfig(
        id="dir-new",
        name="New",
        media_type="movie",
        path="/data/library-new/movie",
        download_path="/data/download-new/movie",
        downloader_id="new",
    )
    tasks = [
        SimpleNamespace(id="task-ok", status=TaskStatus.DOWNLOADING),
        SimpleNamespace(id="task-migrating", status=TaskStatus.MIGRATING),
    ]
    service = DirectoryMigrationService()
    directory_migration_domain_service._task_repo = FakeTaskListRepo(tasks)
    directory_migration_domain_service._library_repo = FakeLibraryRepo()
    directory_migration_domain_service._subscription_repo = FakeSubscriptionRepo(count=0)

    monkeypatch.setattr(
        "app.services.domain.directory.migration.settings_service.get_directory_by_id",
        lambda directory_id: source if directory_id == "dir-old" else target,
    )
    monkeypatch.setattr(
        "app.services.domain.directory.migration.settings_service.list_downloaders",
        lambda: [QBittorrentConfig(id="new", name="New", type="qbittorrent", url="http://qb")],
    )

    previewed_task_ids = []

    async def preview_task_downloader_change(task_id, request):
        previewed_task_ids.append(task_id)
        return SimpleNamespace(ok=True, blockers=[])

    created_task_ids = []

    async def create_command(request):
        created_task_ids.append(request.payload.task_id)
        return SimpleNamespace(id=f"cmd-{request.payload.task_id}")

    monkeypatch.setattr(
        "app.services.domain.directory.migration.download_service.preview_task_downloader_change",
        preview_task_downloader_change,
    )
    monkeypatch.setattr(
        "app.services.application.workflows.directory_migration.service.command_service.create_command",
        create_command,
    )

    request = DirectoryMigrationRequest(target_directory_id="dir-new")
    preview = await service.preview("dir-old", request)
    result = await service.submit("dir-old", request)

    assert preview.ok is True
    assert preview.migratable_task_count == 1
    assert preview.blocked_task_count == 1
    assert previewed_task_ids == ["task-ok", "task-ok", "task-ok"]
    assert created_task_ids == ["task-ok"]
    assert len(result.commands) == 1


@pytest.mark.asyncio
async def test_directory_migration_blocks_orphan_library_files_in_mixed_directory(monkeypatch):
    source = DirectoryConfig(
        id="dir-old",
        name="Old",
        media_type="movie",
        path="/data/library/movie",
        download_path="/data/download/movie",
        downloader_id="old",
    )
    target = DirectoryConfig(
        id="dir-new",
        name="New",
        media_type="movie",
        path="/data/library-new/movie",
        download_path="/data/download-new/movie",
        downloader_id="new",
    )
    tasks = [SimpleNamespace(id="task-ok", status=TaskStatus.DOWNLOADING)]
    library_files = [
        SimpleNamespace(id="file-task", task_id="task-ok"),
        SimpleNamespace(id="file-orphan", task_id="missing-task"),
    ]
    service = DirectoryMigrationService()
    directory_migration_domain_service._task_repo = FakeTaskListRepo(tasks)
    directory_migration_domain_service._library_repo = FakeLibraryRepo(library_files)
    directory_migration_domain_service._subscription_repo = FakeSubscriptionRepo(count=0)

    monkeypatch.setattr(
        "app.services.domain.directory.migration.settings_service.get_directory_by_id",
        lambda directory_id: source if directory_id == "dir-old" else target,
    )
    monkeypatch.setattr(
        "app.services.domain.directory.migration.settings_service.list_downloaders",
        lambda: [QBittorrentConfig(id="new", name="New", type="qbittorrent", url="http://qb")],
    )

    async def preview_task_downloader_change(task_id, request):
        return SimpleNamespace(ok=True, blockers=[])

    monkeypatch.setattr(
        "app.services.domain.directory.migration.download_service.preview_task_downloader_change",
        preview_task_downloader_change,
    )

    request = DirectoryMigrationRequest(target_directory_id="dir-new")
    preview = await service.preview("dir-old", request)

    assert preview.ok is False
    assert preview.task_count == 1
    assert preview.library_file_count == 2
    assert preview.migratable_task_count == 1
    assert "library_only_files_not_migrated_by_task" in preview.blockers


@pytest.mark.asyncio
async def test_directory_migration_preview_skips_task_preview_when_target_downloader_invalid(monkeypatch):
    source = DirectoryConfig(
        id="dir-old",
        name="Old",
        media_type="movie",
        path="/data/library/movie",
        download_path="/data/download/movie",
        downloader_id="old",
    )
    target = DirectoryConfig(
        id="dir-new",
        name="New",
        media_type="movie",
        path="/data/library-new/movie",
        download_path="/data/download-new/movie",
        downloader_id="missing",
    )
    tasks = [SimpleNamespace(id="task-ok", status=TaskStatus.DOWNLOADING)]
    service = DirectoryMigrationService()
    directory_migration_domain_service._task_repo = FakeTaskListRepo(tasks)
    directory_migration_domain_service._library_repo = FakeLibraryRepo()
    directory_migration_domain_service._subscription_repo = FakeSubscriptionRepo(count=0)

    monkeypatch.setattr(
        "app.services.domain.directory.migration.settings_service.get_directory_by_id",
        lambda directory_id: source if directory_id == "dir-old" else target,
    )
    monkeypatch.setattr(
        "app.services.domain.directory.migration.settings_service.list_downloaders",
        lambda: [],
    )

    async def preview_task_downloader_change(task_id, request):
        raise AssertionError("task preview should be skipped when target downloader is invalid")

    monkeypatch.setattr(
        "app.services.domain.directory.migration.download_service.preview_task_downloader_change",
        preview_task_downloader_change,
    )

    preview = await service.preview("dir-old", DirectoryMigrationRequest(target_directory_id="dir-new"))

    assert preview.ok is False
    assert preview.task_count == 1
    assert preview.blocked_task_count == 1
    assert preview.migratable_task_count == 0
    assert "target_downloader_not_found" in preview.blockers
