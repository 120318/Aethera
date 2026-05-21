from pathlib import Path

from app.services.audit.backend_log_reader_service import BackendLogReaderService


def _write_lines(path: Path, *lines: str) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_read_backend_logs_returns_latest_snapshot_with_rotated_files(tmp_path: Path):
    base_path = tmp_path / "backend.log"
    _write_lines(tmp_path / "backend.log.2", "old-1")
    _write_lines(tmp_path / "backend.log.1", "mid-1", "mid-2")
    _write_lines(base_path, "new-1", "new-2")

    service = BackendLogReaderService()
    service._get_base_path = lambda: base_path

    result = service.read_backend_logs(limit=4)

    assert result.reset is False
    assert result.lines == ["mid-1", "mid-2", "new-1", "new-2"]
    assert result.cursor is not None
    assert result.source_file == str(base_path)


def test_read_backend_logs_returns_only_incremental_lines(tmp_path: Path):
    base_path = tmp_path / "backend.log"
    _write_lines(base_path, "line-1")

    service = BackendLogReaderService()
    service._get_base_path = lambda: base_path

    first = service.read_backend_logs(limit=10)
    with base_path.open("a", encoding="utf-8") as handle:
        handle.write("line-2\nline-3\n")

    second = service.read_backend_logs(limit=10, cursor=first.cursor)

    assert second.reset is False
    assert second.lines == ["line-2", "line-3"]
    assert second.cursor is not None


def test_read_backend_logs_resets_when_file_rotates(tmp_path: Path):
    base_path = tmp_path / "backend.log"
    _write_lines(base_path, "line-1", "line-2")

    service = BackendLogReaderService()
    service._get_base_path = lambda: base_path

    first = service.read_backend_logs(limit=10)

    rotated_path = tmp_path / "backend.log.1"
    base_path.replace(rotated_path)
    _write_lines(base_path, "line-3")

    second = service.read_backend_logs(limit=10, cursor=first.cursor)

    assert second.reset is True
    assert second.lines == ["line-1", "line-2", "line-3"]
    assert second.cursor is not None


def test_read_backend_logs_treats_invalid_cursor_as_snapshot(tmp_path: Path):
    base_path = tmp_path / "backend.log"
    _write_lines(base_path, "line-1", "line-2")

    service = BackendLogReaderService()
    service._get_base_path = lambda: base_path

    result = service.read_backend_logs(limit=10, cursor="not-a-valid-cursor")

    assert result.reset is True
    assert result.lines == ["line-1", "line-2"]


def test_read_backend_logs_incremental_respects_limit_without_losing_cursor(tmp_path: Path):
    base_path = tmp_path / "backend.log"
    _write_lines(base_path, "line-1")

    service = BackendLogReaderService()
    service._get_base_path = lambda: base_path

    first = service.read_backend_logs(limit=10)
    with base_path.open("a", encoding="utf-8") as handle:
        for idx in range(2, 7):
            handle.write(f"line-{idx}\n")

    second = service.read_backend_logs(limit=2, cursor=first.cursor)
    third = service.read_backend_logs(limit=2, cursor=second.cursor)
    fourth = service.read_backend_logs(limit=2, cursor=third.cursor)

    assert second.reset is False
    assert second.lines == ["line-2", "line-3"]
    assert third.reset is False
    assert third.lines == ["line-4", "line-5"]
    assert fourth.reset is False
    assert fourth.lines == ["line-6"]
