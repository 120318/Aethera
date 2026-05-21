from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from pathlib import PurePosixPath

import bencodepy

from app.schemas.domain.resource_search import ResourceSearchResult
from app.schemas.domain.resource_attributes import PackageLayoutValue, ResourceAttributes, ResourceFormEvidence
from app.schemas.domain.torrent import TorrentCoverageKind, TorrentFileItem, TorrentMetadata, TorrentPayload
from app.services.domain.resource.parser import resource_parser
from app.services.domain.resource.quality import (
    RESOURCE_FORM_BLURAY_DISC,
    RESOURCE_FORM_DVD_DISC,
    SOURCE_BLURAY,
    SOURCE_DVD,
    SOURCE_UHD_BLURAY,
)


async def fetch_torrent_payload(result: ResourceSearchResult) -> TorrentPayload:
    from app.services.integration.torrent import torrent_service

    blob = await torrent_service.fetch_blob(result)
    return build_torrent_payload(blob, desc=result.description)


def build_torrent_payload(blob: bytes, desc: str = "") -> TorrentPayload:
    return TorrentPayload(metadata=parse_torrent_metadata(blob, desc=desc), blob=blob)


def parse_torrent_metadata(blob: bytes, desc: str = "") -> TorrentMetadata:
    decoded = bencodepy.decode(blob)
    if not isinstance(decoded, Mapping) or b"info" not in decoded:
        raise ValueError("No info dictionary in torrent file")
    info = decoded[b"info"]
    if not isinstance(info, Mapping):
        raise ValueError("Invalid info dictionary in torrent file")

    info_hash = hashlib.sha1(bencodepy.encode(info)).hexdigest()
    name_bytes = info[b"name"] if b"name" in info else b""
    name = name_bytes.decode("utf-8", errors="ignore") if type(name_bytes) is bytes else str(name_bytes)

    files: list[TorrentFileItem] = []
    total_size = 0
    if b"files" in info:
        for idx, file_info in enumerate(info[b"files"]):
            if not isinstance(file_info, Mapping):
                continue
            path_entries = file_info[b"path"] if b"path" in file_info else []
            path_parts = [part.decode("utf-8", errors="ignore") for part in path_entries]
            path = "/".join(path_parts)
            size = int(file_info[b"length"]) if b"length" in file_info else 0
            files.append(TorrentFileItem(
                index=idx,
                filename=path,
                size=size,
                attrs=resource_parser.parse(path),
            ))
            total_size += size
    else:
        size = int(info[b"length"]) if b"length" in info else 0
        files.append(TorrentFileItem(
            index=0,
            filename=name,
            size=size,
            attrs=resource_parser.parse(name),
        ))
        total_size = size

    return enrich_torrent_metadata(TorrentMetadata(
        hash=info_hash,
        name=name,
        size=total_size,
        files=files,
    ), desc=desc)


def enrich_torrent_metadata(metadata: TorrentMetadata, desc: str = "") -> TorrentMetadata:
    root_attrs = resource_parser.parse(metadata.name, desc=desc)
    form, source, layout = _detect_disc_structure(metadata.name, metadata.files)
    enriched_files = [
        file_item.model_copy(update={"attrs": _merge_file_attrs(file_item, form, source, layout)})
        for file_item in metadata.files
    ]
    package_attrs = _merge_package_attrs(root_attrs, enriched_files, form, source, layout)
    enriched_files = _apply_single_file_package_coverage(enriched_files, package_attrs)
    return metadata.model_copy(
        update={
            "files": enriched_files,
            "attrs": package_attrs,
            "coverage_kind": _resolve_coverage_kind(package_attrs, enriched_files),
        }
    )


def _detect_disc_structure(name: str, files: list[TorrentFileItem]) -> tuple[str | None, str | None, str | None]:
    bluray = False
    uhd = False
    dvd = False
    iso = _looks_like_iso(name)
    for file_item in files:
        parts = [part.upper() for part in PurePosixPath(file_item.filename).parts]
        filename = parts[-1] if parts else ""
        iso = iso or _looks_like_iso(file_item.filename)
        if "BDMV" in parts and filename in {"INDEX.BDMV", "MOVIEOBJECT.BDMV"}:
            bluray = True
        if "CERTIFICATE" in parts:
            bluray = True
        if any(part in {"BD66", "BD100"} for part in parts):
            uhd = True
        if "VIDEO_TS" in parts and (filename == "VIDEO_TS.IFO" or re.match(r"VTS_\d{2}_\d\.IFO", filename)):
            dvd = True
        if "VIDEO_TS" in parts and filename.endswith(".VOB"):
            dvd = True
    if bluray:
        return RESOURCE_FORM_BLURAY_DISC, SOURCE_UHD_BLURAY if uhd else SOURCE_BLURAY, PackageLayoutValue.BDMV
    if dvd:
        return RESOURCE_FORM_DVD_DISC, SOURCE_DVD, PackageLayoutValue.VIDEO_TS
    if iso:
        root_attrs = resource_parser.parse(name)
        if root_attrs.resource_form == RESOURCE_FORM_DVD_DISC:
            return RESOURCE_FORM_DVD_DISC, SOURCE_DVD, PackageLayoutValue.ISO
        if root_attrs.resource_form == RESOURCE_FORM_BLURAY_DISC:
            return RESOURCE_FORM_BLURAY_DISC, SOURCE_UHD_BLURAY if SOURCE_UHD_BLURAY in root_attrs.sources else SOURCE_BLURAY, PackageLayoutValue.ISO
    return None, None, PackageLayoutValue.ISO if iso else None


def _merge_file_attrs(file_item: TorrentFileItem, form: str | None, source: str | None, layout: str | None) -> ResourceAttributes:
    attrs = file_item.attrs or resource_parser.parse(file_item.filename)
    if not form and not layout:
        return attrs
    sources = list(attrs.sources or [])
    if source and source not in sources:
        sources.append(source)
    updates = {"sources": sources, "package_layout": layout or attrs.package_layout}
    if form:
        updates.update({"resource_form": form, "resource_form_evidence": ResourceFormEvidence.TORRENT_STRUCTURE})
    return attrs.model_copy(update=updates)


def _merge_package_attrs(
    root_attrs: ResourceAttributes,
    files: list[TorrentFileItem],
    form: str | None,
    source: str | None,
    layout: str | None,
) -> ResourceAttributes:
    file_seasons = [s for file in files for s in (file.attrs.seasons if file.attrs else [])]
    file_episodes = sorted({ep for file in files for ep in (file.attrs.episodes if file.attrs else [])})
    seasons = _first_non_empty(root_attrs.seasons, file_seasons)
    episodes = file_episodes or list(root_attrs.episodes or [])
    disc_number = root_attrs.disc_number or next((file.attrs.disc_number for file in files if file.attrs and file.attrs.disc_number), None)
    disc_total = root_attrs.disc_total or next((file.attrs.disc_total for file in files if file.attrs and file.attrs.disc_total), None)
    sources = list(root_attrs.sources or [])
    if source and source not in sources:
        sources.append(source)
    updates = {
        "sources": sources, "seasons": seasons, "episodes": episodes,
        "disc_number": disc_number, "disc_total": disc_total,
        "package_layout": layout or root_attrs.package_layout,
    }
    if form:
        updates.update({"resource_form": form, "resource_form_evidence": ResourceFormEvidence.TORRENT_STRUCTURE})
    return root_attrs.model_copy(update=updates)


def _apply_single_file_package_coverage(
    files: list[TorrentFileItem],
    package_attrs: ResourceAttributes,
) -> list[TorrentFileItem]:
    if len(files) != 1 or not package_attrs.episodes:
        return files
    file_item = files[0]
    attrs = file_item.attrs or ResourceAttributes()
    if attrs.episodes:
        return files
    updates = {"episodes": list(package_attrs.episodes)}
    if package_attrs.seasons and not attrs.seasons:
        updates["seasons"] = list(package_attrs.seasons)
    if package_attrs.desc and not attrs.desc:
        updates["desc"] = package_attrs.desc
    return [file_item.model_copy(update={"attrs": attrs.model_copy(update=updates)})]


def _resolve_coverage_kind(attrs: ResourceAttributes, files: list[TorrentFileItem]) -> TorrentCoverageKind:
    if any(file.get_episodes() for file in files):
        return TorrentCoverageKind.EXACT_EPISODES
    if attrs.resource_form in {RESOURCE_FORM_BLURAY_DISC, RESOURCE_FORM_DVD_DISC}:
        return TorrentCoverageKind.SEASON_PACKAGE if attrs.seasons and not attrs.disc_number else TorrentCoverageKind.DISC_PACKAGE
    return TorrentCoverageKind.UNKNOWN


def _first_non_empty(primary: list[int], fallback: list[int]) -> list[int]:
    if primary:
        return primary
    return sorted(set(fallback))


def _looks_like_iso(value: str) -> bool:
    return bool(re.search(r"(?i)(?:^|[ ._\-/\[\]()])(?:BDISO|DVDISO|ISO)(?:$|[ ._\-/\[\]()])|\.iso$", value))
