from __future__ import annotations

from pathlib import Path

from app.core.storage_paths import get_download_root, get_library_root

MEDIA_FILE_EXTENSIONS = {
    ".mkv",
    ".mp4",
    ".avi",
    ".mov",
    ".wmv",
    ".m4v",
    ".flv",
    ".m2ts",
    ".ts",
    ".webm",
    ".iso",
    ".bdmv",
    ".ifo",
    ".vob",
}


def normalize_path_separators(value: str) -> str:
    return value.replace("\\", "/")


def split_library_storage_path(file_path: str) -> tuple[str, str]:
    normalized = normalize_path_separators(file_path)
    path_obj = Path(normalized)
    if path_obj.is_absolute():
        library_root = get_library_root()
        try:
            relative = path_obj.relative_to(library_root)
        except ValueError:
            parent = normalize_path_separators(str(path_obj.parent))
            return parent, path_obj.name
    else:
        relative = path_obj
        if relative.parts and relative.parts[0] == "library":
            relative = Path(*relative.parts[1:]) if len(relative.parts) > 1 else Path(".")

    parent = "" if str(relative.parent) == "." else normalize_path_separators(str(relative.parent))
    return parent, relative.name


def to_download_relative_path(path: str) -> str:
    normalized = normalize_path_separators(path)
    path_obj = Path(normalized)
    if path_obj.is_absolute():
        try:
            relative = path_obj.relative_to(get_download_root())
        except ValueError:
            return normalize_path_separators(str(path_obj))
    else:
        relative = path_obj
        if relative.parts and relative.parts[0] == "download":
            relative = Path(*relative.parts[1:]) if len(relative.parts) > 1 else Path(".")

    relative_text = normalize_path_separators(str(relative))
    return "" if relative_text == "." else relative_text.strip("/")


def build_library_file_path(path: str, file_name: str | None = None) -> Path:
    base = Path(normalize_path_separators(path))
    if base.is_absolute():
        return base / file_name if file_name else base

    library_root = get_library_root()
    return library_root / base / file_name if file_name else library_root / base


def build_library_directory_path(path: str) -> Path:
    return build_library_file_path(path)




def build_download_path(path: str | None = None) -> Path:
    if not path:
        return get_download_root()

    normalized = normalize_path_separators(path)
    path_obj = Path(normalized)
    if path_obj.is_absolute():
        return path_obj
    return get_download_root() / path_obj


def path_looks_like_media_file(path: str) -> bool:
    return Path(path).suffix.lower() in MEDIA_FILE_EXTENSIONS


def file_name_looks_like_media_file(file_name: str | None) -> bool:
    return bool(file_name) and Path(file_name).suffix.lower() in MEDIA_FILE_EXTENSIONS
