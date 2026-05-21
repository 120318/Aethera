from __future__ import annotations

from app.schemas.domain.library import LibraryFile, LibraryPackageFileItem, LibraryPackageSummary
from app.schemas.domain.resource_attributes import PackageLayoutValue, ResourceAttributes
from app.utils.library_paths import file_name_looks_like_media_file, normalize_path_separators


def build_library_file_storage_path(file: LibraryFile) -> str:
    return normalize_path_separators(f"{file.path}/{file.file_name or ''}".strip("/"))


def resolve_package_root(file: LibraryFile) -> str | None:
    attrs = file.resource_attributes or ResourceAttributes()
    if attrs.package_layout == PackageLayoutValue.ISO:
        return normalize_path_separators(file.path or "").strip("/") or build_library_file_storage_path(file)
    if attrs.package_layout not in {PackageLayoutValue.BDMV, PackageLayoutValue.VIDEO_TS}:
        return None

    parts = [part for part in build_library_file_storage_path(file).split("/") if part]
    upper_parts = [part.upper() for part in parts]
    for marker in ("BDMV", "CERTIFICATE", "VIDEO_TS"):
        if marker in upper_parts:
            return "/".join(parts[:upper_parts.index(marker)])
    return None


def matches_package_root(library_file: LibraryFile, package_root: str) -> bool:
    if not package_root:
        return False
    full_path = build_library_file_storage_path(library_file)
    normalized_root = normalize_path_separators(package_root).rstrip("/")
    return full_path == normalized_root or full_path.startswith(f"{normalized_root}/")


def is_displayable_library_file(file: LibraryFile) -> bool:
    return resolve_package_root(file) is not None or file_name_looks_like_media_file(file.file_name)


def format_package_file_name(attrs: ResourceAttributes) -> str:
    layout = str(attrs.package_layout) if attrs.package_layout else "Disc"
    if attrs.disc_number:
        total = f"/{int(attrs.disc_total):02d}" if attrs.disc_total else ""
        return f"Disc {int(attrs.disc_number):02d}{total} · {layout}"
    return f"{attrs.resource_form or 'Disc'} · {layout}"


def package_representative_sort_key(file: LibraryFile) -> tuple[int, str]:
    text = build_library_file_storage_path(file).upper()
    if "BDMV/INDEX.BDMV" in text or "VIDEO_TS/VIDEO_TS.IFO" in text:
        return (0, text)
    if "/BDMV/" in text or "/VIDEO_TS/" in text:
        return (1, text)
    return (2, text)


def build_package_summary(root: str, files: list[LibraryFile]) -> LibraryPackageSummary:
    representative = min(files, key=package_representative_sort_key)
    attrs = representative.resource_attributes or ResourceAttributes()
    disc_total = _count_package_discs(files)
    attrs = attrs.model_copy(update={"disc_number": None, "disc_total": disc_total})
    package_name = root.rstrip("/").rsplit("/", 1)[-1] if root else format_package_file_name(attrs)
    directory_root = root.rstrip("/").rsplit("/", 1)[0] if "/" in root.rstrip("/") else ""
    file_items = [_build_package_file_item(root, item, item.id == representative.id) for item in sorted(files, key=_package_file_sort_key)]
    return LibraryPackageSummary(
        id=representative.id,
        task_id=representative.task_id,
        directory_id=representative.directory_id,
        media_id=representative.media_id,
        file_name=package_name,
        resource_title=attrs.title or package_name,
        directory=f"/{directory_root.lstrip('/')}" if directory_root else "/",
        package_root=root,
        file_count=len(files),
        total_size=sum(item.file_size or 0 for item in files),
        created_at=max(item.created_at for item in files),
        resource_attributes=attrs,
        files=file_items,
    )


def _count_package_discs(files: list[LibraryFile]) -> int:
    roots = {root for item in files if (root := resolve_package_root(item))}
    return max(1, len(roots))


def build_library_package_summaries(files: list[LibraryFile]) -> list[LibraryPackageSummary]:
    task_grouped: dict[str, list[LibraryFile]] = {}
    for file in files:
        root = resolve_package_root(file)
        if root:
            task_grouped.setdefault(file.task_id, []).append(file)

    packages: list[LibraryPackageSummary] = []
    for task_files in task_grouped.values():
        roots = sorted({root for item in task_files if (root := resolve_package_root(item))})
        if len(roots) > 1:
            packages.append(build_package_summary(_common_package_root(roots), task_files))
            continue

        grouped: dict[str, list[LibraryFile]] = {}
        for item in task_files:
            root = resolve_package_root(item)
            if root:
                grouped.setdefault(root, []).append(item)
        packages.extend(build_package_summary(root, items) for root, items in grouped.items())
    return packages


def find_package_for_file(file: LibraryFile, files: list[LibraryFile]) -> LibraryPackageSummary | None:
    for package in build_library_package_summaries(files):
        if any(item.id == file.id for item in package.files):
            return package
    return None


def _common_package_root(roots: list[str]) -> str:
    if not roots:
        return ""
    split_roots = [[part for part in normalize_path_separators(root).split("/") if part] for root in roots]
    common: list[str] = []
    for index, part in enumerate(split_roots[0]):
        if all(len(parts) > index and parts[index] == part for parts in split_roots[1:]):
            common.append(part)
            continue
        break
    return "/".join(common) if common else roots[0]


def _build_package_file_item(root: str, file: LibraryFile, is_anchor: bool) -> LibraryPackageFileItem:
    full_path = build_library_file_storage_path(file)
    relative = full_path
    normalized_root = root.rstrip("/")
    if full_path == normalized_root:
        relative = file.file_name or full_path.rsplit("/", 1)[-1]
    elif full_path.startswith(f"{normalized_root}/"):
        relative = full_path[len(normalized_root) + 1:]
    return LibraryPackageFileItem(
        id=file.id,
        path=f"/{normalize_path_separators(file.path or '').lstrip('/')}" if file.path else "/",
        file_name=file.file_name,
        relative_path=relative,
        file_size=file.file_size,
        file_index=file.file_index,
        is_anchor=is_anchor,
    )


def _package_file_sort_key(file: LibraryFile) -> tuple[int, str]:
    anchor_rank, text = package_representative_sort_key(file)
    return (anchor_rank, text)
