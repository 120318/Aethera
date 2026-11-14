from __future__ import annotations

from pathlib import PurePosixPath
import re

from app.schemas.domain.torrent import TorrentFileItem, TorrentMetadata
from app.services.domain.resource.filtering import is_original_disc_attrs


NON_LIBRARY_EXTENSIONS = {
    ".txt", ".md", ".pdf", ".url", ".lnk", ".htm", ".html",
    ".exe", ".bat", ".cmd", ".sh", ".msi", ".scr",
    ".torrent", ".nzb", ".sfv", ".md5", ".sha1", ".sha256",
    ".zip", ".rar", ".7z", ".tar", ".gz",
}


def is_library_download_file(metadata: TorrentMetadata, file_item: TorrentFileItem) -> bool:
    # Disc structures contain required non-video support files; keep them intact.
    if metadata.attrs and (metadata.attrs.package_layout or is_original_disc_attrs(metadata.attrs)):
        return True
    path = PurePosixPath(file_item.filename.replace("\\", "/"))
    if path.suffix.lower() in NON_LIBRARY_EXTENSIONS:
        return False
    if any(part.casefold() in {"sample", "samples"} for part in path.parts[:-1]):
        return False
    return not re.search(r"(?:^|[. _-])sample(?:$|[. _-])", path.stem, re.IGNORECASE)


def library_download_file_indices(metadata: TorrentMetadata, selected_files: list[int] | None) -> list[int]:
    requested = set(selected_files) if selected_files else None
    return sorted(
        file_item.index
        for file_item in metadata.files
        if (requested is None or file_item.index in requested)
        and is_library_download_file(metadata, file_item)
    )
