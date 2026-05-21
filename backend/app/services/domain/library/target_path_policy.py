from __future__ import annotations

from pathlib import Path

from app.schemas.config import Template
from app.schemas.domain.resource_attributes import NamingContext, ResourceAttributes
from app.schemas.domain.torrent import TorrentFileItem
from app.schemas.exception.exceptions import TransferException
from app.services.domain.library.naming_policy import format_name


class LibraryTargetPathPolicy:
    def build_destination_path(
        self,
        *,
        destination_base_path: Path,
        template_config: Template | None,
        title: str | None,
        year: int | None,
        season_number: int | None,
        file_item: TorrentFileItem,
        disc_package_name: str | None = None,
    ) -> Path:
        episode_numbers = self.extract_episode_numbers(file_item, season_number=season_number)
        episode_number = episode_numbers[0] if episode_numbers else 0
        naming_context = self._build_transfer_naming_context(
            title=title,
            year=year,
            season_number=season_number,
            episode_number=episode_number,
            episode_numbers=episode_numbers,
            file_item=file_item,
            disc_package_name=disc_package_name,
        )
        rendered_dir = self._render_directory_name(naming_context, template_config)
        rendered_file = self._render_file_name(file_item, naming_context, template_config)
        base_dir = destination_base_path / rendered_dir if rendered_dir else destination_base_path
        return base_dir / rendered_file

    def build_destination_dir(
        self,
        *,
        destination_base_path: Path,
        template_config: Template | None,
        title: str | None,
        year: int | None,
        season_number: int | None,
        file_item: TorrentFileItem,
        disc_package_name: str | None = None,
    ) -> Path:
        naming_context = self._build_transfer_naming_context(
            title=title,
            year=year,
            season_number=season_number,
            episode_number=None,
            episode_numbers=[],
            file_item=file_item,
            disc_package_name=disc_package_name,
        )
        rendered_dir = self._render_directory_name(naming_context, template_config)
        return destination_base_path / rendered_dir if rendered_dir else destination_base_path

    def build_destination_file_name(
        self,
        *,
        template_config: Template | None,
        title: str | None,
        year: int | None,
        season_number: int | None,
        file_item: TorrentFileItem,
        disc_package_name: str | None = None,
    ) -> str:
        naming_context = self._build_transfer_naming_context(
            title=title,
            year=year,
            season_number=season_number,
            episode_number=None,
            episode_numbers=[],
            file_item=file_item,
            disc_package_name=disc_package_name,
        )
        return self._render_file_name(file_item, naming_context, template_config)

    def extract_episode_numbers(self, file_item: TorrentFileItem, *, season_number: int | None = None) -> list[int]:
        episodes = file_item.attrs.episodes if file_item.attrs else []
        return sorted({int(episode) for episode in episodes if int(episode) > 0})

    def extract_episode_number(self, file_item: TorrentFileItem, *, season_number: int | None = None) -> int:
        episodes = self.extract_episode_numbers(file_item, season_number=season_number)
        if episodes:
            return int(episodes[0])
        return 0

    def _build_transfer_naming_context(
        self,
        *,
        title: str | None,
        year: int | None,
        season_number: int | None,
        episode_number: int | None,
        episode_numbers: list[int],
        file_item: TorrentFileItem,
        disc_package_name: str | None = None,
    ) -> NamingContext:
        naming_episodes = episode_numbers or ([episode_number] if episode_number else [])
        naming_context = NamingContext(
            resource_title=title or "",
            attributes=ResourceAttributes(
                title=title,
                year=year if year else None,
                episodes=naming_episodes,
            ),
            size=file_item.size,
            disc_package_name=disc_package_name,
            season_number=season_number,
            media_type="tv" if season_number is not None else "movie",
        )
        if file_item.attrs:
            naming_context.attributes = file_item.attrs.model_copy(
                update={
                    "title": title,
                    "year": year,
                    "episodes": naming_episodes,
                }
            )
        return naming_context

    def _render_file_name(
        self,
        file_item: TorrentFileItem,
        naming_context: NamingContext,
        template_config: Template | None,
    ) -> str:
        if not template_config or not (template_config.file_template or "").strip():
            raise TransferException("backendErrors.transferFileNamingTemplateMissing")
        rendered = format_name(template_config.file_template, naming_context)
        if not rendered:
            raise TransferException("backendErrors.transferFileNameRenderFailed", params={"filename": file_item.filename})
        return f"{rendered}{Path(file_item.filename).suffix}"

    def _render_directory_name(
        self,
        naming_context: NamingContext,
        template_config: Template | None,
    ) -> str:
        if not template_config:
            raise TransferException("backendErrors.transferDirectoryNamingTemplateMissing")
        if not (template_config.dir_template or "").strip():
            return ""
        rendered = format_name(template_config.dir_template, naming_context)
        if not rendered:
            raise TransferException("backendErrors.transferDirectoryPathRenderFailed")
        return rendered


library_target_path_policy = LibraryTargetPathPolicy()
