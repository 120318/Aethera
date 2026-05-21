import os
import stat
import shutil

import pytest

from app.schemas.config import TransferMode
from app.services.domain.transfer.materializers.copy import copy_materializer
from app.services.domain.transfer.materializers.hardlink import hardlink_materializer
from app.services.domain.transfer.materializers.registry import transfer_materializer_registry
from app.utils.fs_utils import ensure_directory, write_text_file

pytestmark = [pytest.mark.health]


def _mode(path) -> int:
    return stat.S_IMODE(os.stat(path).st_mode)


def test_ensure_directory_sets_group_writable_mode_for_created_directories(tmp_path):
    target = tmp_path / "library" / "Movie"

    ensure_directory(target)

    assert _mode(tmp_path / "library") == 0o775
    assert _mode(target) == 0o775


def test_ensure_directory_preserves_inherited_setgid_bit(tmp_path):
    root = tmp_path / "library"
    root.mkdir()
    os.chmod(root, 0o2775)
    target = root / "Show" / "Season 01"

    ensure_directory(target)

    assert _mode(root / "Show") == 0o2775
    assert _mode(target) == 0o2775


def test_write_text_file_sets_group_writable_mode_for_created_sidecar(tmp_path):
    target = tmp_path / "library" / "Movie" / "movie.nfo"

    write_text_file(target, "hello")

    assert target.read_text(encoding="utf-8") == "hello"
    assert _mode(target.parent) == 0o775
    assert _mode(target) == 0o664


def test_hardlink_materializer_keeps_source_file_mode(tmp_path):
    source = tmp_path / "download" / "movie.mkv"
    source.parent.mkdir()
    source.write_text("media", encoding="utf-8")
    os.chmod(source, 0o600)
    target = tmp_path / "library" / "Movie" / "movie.mkv"

    hardlink_materializer.materialize(source, target)

    assert os.stat(source).st_ino == os.stat(target).st_ino
    assert _mode(source) == 0o600
    assert _mode(target) == 0o600
    assert _mode(target.parent) == 0o775


def test_copy_materializer_copies_file_without_sharing_inode(tmp_path):
    source = tmp_path / "download" / "movie.mkv"
    source.parent.mkdir()
    source.write_text("media", encoding="utf-8")
    os.chmod(source, 0o600)
    target = tmp_path / "library" / "Movie" / "movie.mkv"

    copy_materializer.materialize(source, target)

    assert target.read_text(encoding="utf-8") == "media"
    assert os.stat(source).st_ino != os.stat(target).st_ino
    assert _mode(source) == 0o600
    assert _mode(target) == 0o600
    assert _mode(target.parent) == 0o775


def test_copy_materializer_replaces_existing_target(tmp_path):
    source = tmp_path / "download" / "movie.mkv"
    target = tmp_path / "library" / "Movie" / "movie.mkv"
    source.parent.mkdir()
    target.parent.mkdir(parents=True)
    source.write_text("new", encoding="utf-8")
    target.write_text("old", encoding="utf-8")

    copy_materializer.materialize(source, target)

    assert target.read_text(encoding="utf-8") == "new"
    assert os.stat(source).st_ino != os.stat(target).st_ino


def test_copy_materializer_keeps_existing_target_when_copy_fails(tmp_path, monkeypatch):
    source = tmp_path / "download" / "movie.mkv"
    target = tmp_path / "library" / "Movie" / "movie.mkv"
    source.parent.mkdir()
    target.parent.mkdir(parents=True)
    source.write_text("new", encoding="utf-8")
    target.write_text("old", encoding="utf-8")

    def fail_copy(source_path, target_path):
        target_path.write_text("partial", encoding="utf-8")
        raise OSError("disk full")

    monkeypatch.setattr(shutil, "copy2", fail_copy)

    with pytest.raises(Exception, match="backendErrors.transferCopyFailed"):
        copy_materializer.materialize(source, target)

    assert target.read_text(encoding="utf-8") == "old"
    assert list(target.parent.glob(".*.tmp")) == []


def test_transfer_materializer_registry_resolves_copy_mode():
    assert transfer_materializer_registry.resolve(TransferMode.COPY) is copy_materializer
