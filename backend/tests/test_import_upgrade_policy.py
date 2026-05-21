from app.schemas.media_id import MediaID
from app.schemas.domain.download import TransferFileResult
from app.schemas.domain.import_upgrade import ImportUpgradeDecisionKind
from app.schemas.domain.library import LibraryFile
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.schemas.domain.torrent import TorrentFileItem
from app.services.domain.transfer.upgrade import import_upgrade_policy


def _library_file(*, resolution: str | None, source: str | None, size: int = 1000) -> LibraryFile:
    return LibraryFile(
        id="file-1",
        task_id="task-1",
        directory_id="dir-1",
        media_id=MediaID.parse("tmdb:movie:1"),
        path="Movies/Test Movie (2024)",
        file_name="Test.Movie.2024.mkv",
        file_size=size,
        file_index=0,
        created_at=0.0,
        resource_attributes=ResourceAttributes(
            resolution=resolution,
            sources=[source] if source else [],
        ),
    )


def _transfer_result(*, resolution: str | None, source: str | None, size: int = 1000) -> TransferFileResult:
    return TransferFileResult(
        source_path="/downloads/Test.Movie.2024.mkv",
        destination_path="/data/library/Movies/Test Movie (2024)/Test.Movie.2024.mkv",
        file_index=0,
        file_item=TorrentFileItem(
            index=0,
            filename="Test.Movie.2024.mkv",
            size=size,
            attrs=ResourceAttributes(
                resolution=resolution,
                sources=[source] if source else [],
            ),
        ),
    )


def test_import_upgrade_policy_accepts_higher_resolution():
    decision = import_upgrade_policy.decide(
        _library_file(resolution="1080p", source="WEB-DL"),
        _transfer_result(resolution="2160p", source="WEB-DL"),
    )

    assert decision.kind == ImportUpgradeDecisionKind.BETTER
    assert decision.dimension == "resolution"


def test_import_upgrade_policy_rejects_lower_resolution():
    decision = import_upgrade_policy.decide(
        _library_file(resolution="2160p", source="BluRay"),
        _transfer_result(resolution="1080p", source="WEB-DL"),
    )

    assert decision.kind == ImportUpgradeDecisionKind.NOT_BETTER
    assert decision.dimension == "resolution"


def test_import_upgrade_policy_returns_unknown_when_attributes_are_missing():
    decision = import_upgrade_policy.decide(
        _library_file(resolution=None, source=None, size=1000),
        _transfer_result(resolution=None, source=None, size=1000),
    )

    assert decision.kind == ImportUpgradeDecisionKind.UNKNOWN


def test_import_upgrade_policy_accepts_legacy_alias_values():
    decision = import_upgrade_policy.decide(
        _library_file(resolution="1080p", source="WEB-DL", size=1000),
        _transfer_result(resolution="1080p", source="BluRay", size=1000),
    )

    assert decision.kind == ImportUpgradeDecisionKind.BETTER
    assert decision.dimension == "source"
