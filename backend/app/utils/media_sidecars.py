from pathlib import Path

_DANMU_MARKER = ".danmu"
_DANMU_FORMATS = {".ass", ".xml"}


def danmu_sidecar_path(video_path: Path, suffix: str) -> Path:
    return video_path.with_name(f"{video_path.stem}{_DANMU_MARKER}.{suffix}")


def is_danmu_sidecar_path(path: Path) -> bool:
    return path.suffix.lower() in _DANMU_FORMATS and path.stem.lower().endswith(_DANMU_MARKER)
