from datetime import datetime

from app.schemas.domain.download import TaskContext, TaskData, TaskStatus, TransferFileResult
from app.schemas.domain.media import MediaIdentity
from app.schemas.domain.resource_search import ResourceSearchResult
from app.schemas.domain.torrent import TorrentFileItem, TorrentMetadata
from app.schemas.media_id import MediaID
from app.services.audit.event_message_builder import (
    build_download_completed_message,
    build_download_started_message,
    build_media_import_completed_message,
    build_pilot_episode_queued_message,
    build_subscription_run_completed_message,
)


def _task() -> TaskData:
    media = MediaIdentity(media_id=MediaID.parse("tmdb:tv:1"), title="Sample", year=2024)
    return TaskData(
        id="task-1",
        media_id=media.media_id,
        torrent_hash="1234567890abcdef",
        status=TaskStatus.DOWNLOADING,
        downloader_id="qb",
        context=TaskContext(
            indexer="mteam",
            download_url="https://example.com/download",
            resource_title="Example.Show.S01.1080p",
            media=media,
            directory_id="tv-default",
            selected_files=[0, 2],
            search_result=ResourceSearchResult(
                id="res-1",
                title="Example.Show.S01.1080p",
                site="mteam",
                category="tv",
                size="10 GB",
                seeders=10,
                leechers=1,
                publish_date=datetime(2026, 4, 1),
                download_url="https://example.com/file",
                result_id="res-1",
            ),
        ),
        metadata=TorrentMetadata(
            hash="1234567890abcdef",
            name="Example.Show.S01.1080p",
            size=1024,
            files=[
                TorrentFileItem(index=0, filename="S01E01.mkv", size=100),
                TorrentFileItem(index=1, filename="S01E02.mkv", size=100),
                TorrentFileItem(index=2, filename="S01E03.mkv", size=100),
            ],
        ),
    )


def test_build_download_started_message_includes_torrent_and_selection_context():
    message = build_download_started_message(_task(), "qBittorrent")

    assert "Example.Show.S01.1080p" in message
    assert "site mteam" in message
    assert "downloader qBittorrent" in message
    assert "2/3 files selected" in message
    assert "hash 12345678" in message


def test_build_download_completed_message_prefers_resource_title_over_metadata_name():
    task = _task()
    task.metadata.name = "S01E01.mkv"

    message = build_download_completed_message(task, "qBittorrent")

    assert "Example.Show.S01.1080p" in message
    assert "S01E01.mkv" not in message
    assert "downloader qBittorrent" in message
    assert "2/3 files selected" in message
    assert "hash 12345678" in message


def test_build_media_import_completed_message_includes_file_count_episode_and_target():
    task = _task()
    message = build_media_import_completed_message(
        task,
        [
            TransferFileResult(
                source_path="/downloads/S01E01.mkv",
                destination_path="/library/Show/Season 1/S01E01.mkv",
                file_item=TorrentFileItem(index=0, filename="S01E01.mkv", size=100),
                file_index=0,
                episode_number=1,
            ),
            TransferFileResult(
                source_path="/downloads/S01E02.mkv",
                destination_path="/library/Show/Season 1/S01E02.mkv",
                file_item=TorrentFileItem(index=1, filename="S01E02.mkv", size=100),
                file_index=1,
                episode_number=2,
            ),
        ],
    )

    assert "Sample" not in message
    assert "2 files imported" in message
    assert "episodes 1-2 covered" in message
    assert "S01E01.mkv" in message


def test_build_subscription_run_completed_message_is_explicit():
    message = build_subscription_run_completed_message(checked=5, added=2)

    assert message == "Subscription check completed (5 candidates matched, 2 download tasks created)"


def test_build_pilot_episode_queued_message_includes_directory_and_site_count():
    media = MediaIdentity(media_id=MediaID.parse("tmdb:tv:1"), title="Sample", year=2024)

    message = build_pilot_episode_queued_message(media, directory_id="tv-default", sites=["mteam", "pter"])

    assert "Sample" not in message
    assert "directory tv-default" in message
    assert "2 sites" in message


def test_build_pilot_episode_queued_message_uses_download_wording_for_movie():
    media = MediaIdentity(media_id=MediaID.parse("tmdb:movie:1"), title="Sample", year=2024)

    message = build_pilot_episode_queued_message(media, directory_id="movie-default", sites=None)

    assert "Download task submitted" in message
    assert "directory movie-default" in message
    assert "default sites" in message
