from __future__ import annotations

import logging
from pathlib import Path

from app.schemas.config import DanmuAddonConfig
from app.services.application.workflows.danmu.formatters import build_ass, build_xml
from app.services.integration.danmu.models import DanmuFetchResult
from app.utils.fs_utils import write_text_file

logger = logging.getLogger("app.application.danmu")


def sidecar_path(video_path: Path, suffix: str) -> Path:
    return video_path.with_name(f"{video_path.stem}.danmu.{suffix}")


def expected_sidecar_paths(video_path: Path, config: DanmuAddonConfig) -> list[Path]:
    paths: list[Path] = []
    if config.output_xml:
        paths.append(sidecar_path(video_path, "xml"))
    if config.output_ass:
        paths.append(sidecar_path(video_path, "ass"))
    return paths


def write_outputs(
    video_path: Path,
    result: DanmuFetchResult,
    config: DanmuAddonConfig,
) -> tuple[Path | None, Path | None]:
    xml_path: Path | None = None
    ass_path: Path | None = None
    if config.output_xml:
        xml_path = sidecar_path(video_path, "xml")
        write_text_file(
            xml_path,
            build_xml(
                result.comments,
                font_size=config.font_size,
                scroll_duration_seconds=config.scroll_duration_seconds,
                density_percent=config.density_percent,
                display_area=config.display_area,
            ),
        )
    if config.output_ass:
        ass_path = sidecar_path(video_path, "ass")
        write_text_file(
            ass_path,
            build_ass(
                result.comments,
                font_size=config.font_size,
                font_opacity_percent=config.font_opacity_percent,
                scroll_duration_seconds=config.scroll_duration_seconds,
                density_percent=config.density_percent,
                display_area=config.display_area,
            ),
        )
    return xml_path, ass_path


def remove_outputs(video_path: Path, config: DanmuAddonConfig) -> None:
    for path in expected_sidecar_paths(video_path, config):
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Danmu sidecar cleanup failed: path=%s error=%s", path, exc)
