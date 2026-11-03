from pathlib import Path


def video_sidecar_suffix(video_path: Path, artifact_path: Path) -> str | None:
    if artifact_path.parent != video_path.parent:
        return None
    if artifact_path == video_path or not artifact_path.name.startswith(video_path.stem):
        return None
    suffix = artifact_path.name[len(video_path.stem) :]
    return suffix if suffix.startswith((".", "-")) else None
