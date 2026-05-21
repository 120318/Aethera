from __future__ import annotations

from app.schemas.domain.download import TaskData, TransferFileResult
from app.schemas.domain.import_upgrade import LibraryReplacementPlan
from app.schemas.domain.library import LibraryFile, LibraryPackageSummary
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.quality_profile import QualityProfile
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.services.config.settings_service import settings_service
from app.services.domain.library.service import library_service
from app.services.domain.resource.filtering import compute_preference_score_from_attrs, is_original_disc_attrs
from app.services.domain.resource.quality import quality_sort_key
from app.utils.library_paths import normalize_path_separators


class LibraryReplacementPolicy:
    async def build_plan(
        self,
        task: TaskData,
        transfer_results: list[TransferFileResult],
        season: int | None,
    ) -> LibraryReplacementPlan:
        if not transfer_results:
            return LibraryReplacementPlan(reason="empty transfer")

        if self._is_original_disc_import(transfer_results):
            return await self._build_original_disc_plan(task, transfer_results, season)
        return await self._build_video_file_plan(task, transfer_results, season)

    async def _build_video_file_plan(
        self,
        task: TaskData,
        transfer_results: list[TransferFileResult],
        season: int | None,
    ) -> LibraryReplacementPlan:
        quality_profile = self._quality_profile()
        candidates = [
            item
            for item in await library_service.get_files_by_media(task.media_id, season)
            if item.task_id != task.id and not self._is_original_disc_file(item)
        ]
        episode_file_ids: dict[int, set[str]] = {}
        if task.media_id.media_type == MediaType.tv and season is not None:
            episodes = await library_service.get_episodes_by_media(task.media_id)
            for episode in episodes:
                if episode.season == season:
                    episode_file_ids.setdefault(int(episode.episode), set()).add(episode.file_id)
        replace_files: dict[str, LibraryFile] = {}
        for transfer_result in transfer_results:
            scoped_candidates = self._video_file_candidates_for_result(task, candidates, transfer_result, season, episode_file_ids)
            if not scoped_candidates:
                continue
            incoming_attrs = transfer_result.file_item.attrs or ResourceAttributes()
            incoming_size = transfer_result.file_item.size or 0
            best_existing = max(scoped_candidates, key=lambda item: self._rank(item.resource_attributes, item.file_size or 0, quality_profile))
            if self._rank(incoming_attrs, incoming_size, quality_profile) > self._rank(
                best_existing.resource_attributes, best_existing.file_size or 0, quality_profile
            ):
                for candidate in scoped_candidates:
                    if candidate.id:
                        replace_files[candidate.id] = candidate

        return LibraryReplacementPlan(
            replace_files=list(replace_files.values()),
            reason="video file replacement" if replace_files else "no better video file replacement",
        )

    async def _build_original_disc_plan(
        self,
        task: TaskData,
        transfer_results: list[TransferFileResult],
        season: int | None,
    ) -> LibraryReplacementPlan:
        quality_profile = self._quality_profile()
        files = [
            item for item in await library_service.get_files_by_media(task.media_id, season) if item.task_id != task.id and self._is_original_disc_file(item)
        ]
        packages = library_service.build_package_summaries(files)
        if not packages:
            return LibraryReplacementPlan(reason="no original disc package candidates")

        incoming_attrs = transfer_results[0].file_item.attrs or ResourceAttributes()
        incoming_size = sum(result.file_item.size or 0 for result in transfer_results)
        incoming_roots = self._incoming_package_roots(task, transfer_results)
        incoming_disc_numbers = self._incoming_disc_numbers(transfer_results)
        root_matched_packages = self._original_disc_candidate_packages(packages, incoming_roots)
        has_root_matched_files = any(
            root and self._root_matches_any(root, incoming_roots) for file in files if (root := library_service.resolve_package_root(file))
        )
        scoped_packages = root_matched_packages or packages
        best_existing = max(scoped_packages, key=lambda item: self._rank(item.resource_attributes, item.total_size, quality_profile))
        if self._rank(incoming_attrs, incoming_size, quality_profile) <= self._rank(
            best_existing.resource_attributes, best_existing.total_size, quality_profile
        ):
            return LibraryReplacementPlan(reason="incoming original disc is not better than existing packages")

        replace_files = {
            file.id: file
            for file in files
            if file.id
            and self._should_replace_original_disc_file(
                file,
                best_existing,
                incoming_roots,
                incoming_disc_numbers,
                allow_disc_number_fallback=not root_matched_packages and not has_root_matched_files,
            )
        }
        return LibraryReplacementPlan(
            replace_files=list(replace_files.values()),
            reason="original disc package replacement" if replace_files else "no original disc package files",
        )

    def _video_file_candidates_for_result(
        self,
        task: TaskData,
        candidates: list[LibraryFile],
        transfer_result: TransferFileResult,
        season: int | None,
        episode_file_ids: dict[int, set[str]],
    ) -> list[LibraryFile]:
        if task.media_id.media_type == MediaType.movie:
            return candidates
        episode_numbers = transfer_result.episode_numbers or ([transfer_result.episode_number] if transfer_result.episode_number else [])
        if season is None or not episode_numbers:
            return []
        scoped_candidates: dict[str, LibraryFile] = {}
        for episode in sorted({int(value) for value in episode_numbers if int(value) > 0}):
            known_file_ids = episode_file_ids[episode] if episode in episode_file_ids else set()
            for item in candidates:
                if item.id and (item.id in known_file_ids or self._has_episode(item.resource_attributes, season, episode)):
                    scoped_candidates[item.id] = item
        return list(scoped_candidates.values())

    def _has_episode(self, attrs: ResourceAttributes, season: int, episode: int) -> bool:
        if attrs.seasons and season not in attrs.seasons:
            return False
        return episode in (attrs.episodes or [])

    def _is_original_disc_import(self, transfer_results: list[TransferFileResult]) -> bool:
        return any(self._is_original_disc_attrs(result.file_item.attrs or ResourceAttributes()) for result in transfer_results)

    def _is_original_disc_file(self, file: LibraryFile) -> bool:
        return self._is_original_disc_attrs(file.resource_attributes or ResourceAttributes()) or library_service.resolve_package_root(file) is not None

    def _is_original_disc_attrs(self, attrs: ResourceAttributes) -> bool:
        return is_original_disc_attrs(attrs)

    def _rank(
        self,
        attrs: ResourceAttributes,
        size: int,
        quality_profile: QualityProfile | None,
    ) -> tuple[int, tuple[int, ...], int]:
        preference_score = compute_preference_score_from_attrs(attrs, quality_profile)[0]
        ranking = quality_profile.ranking if quality_profile else None
        return preference_score, quality_sort_key(attrs, ranking), int(size or 0)

    def _quality_profile(self) -> QualityProfile | None:
        return settings_service.get_default_quality_profile()

    def _file_in_package(self, file: LibraryFile, package: LibraryPackageSummary) -> bool:
        return any(item.id == file.id for item in package.files)

    def _incoming_disc_numbers(self, transfer_results: list[TransferFileResult]) -> set[int]:
        disc_numbers: set[int] = set()
        for result in transfer_results:
            attrs = result.file_item.attrs
            if attrs and attrs.disc_number:
                disc_numbers.add(int(attrs.disc_number))
        return disc_numbers

    def _incoming_package_roots(self, task: TaskData, transfer_results: list[TransferFileResult]) -> set[str]:
        roots: set[str] = set()
        for result in transfer_results:
            attrs = result.file_item.attrs
            if not attrs:
                continue
            path = normalize_path_separators(result.destination_path or "").strip("/")
            if not path:
                continue
            directory, _, file_name = path.rpartition("/")
            pseudo_file = LibraryFile(
                id="incoming",
                task_id="incoming",
                directory_id="dir-1",
                media_id=task.media_id,
                path=directory,
                file_name=file_name or path,
                file_size=result.file_item.size,
                file_index=result.file_index,
                created_at=0,
                resource_attributes=attrs,
            )
            if root := library_service.resolve_package_root(pseudo_file):
                roots.add(root)
        return roots

    def _original_disc_candidate_packages(
        self,
        packages: list[LibraryPackageSummary],
        incoming_roots: set[str],
    ) -> list[LibraryPackageSummary]:
        if not incoming_roots:
            return []
        return [package for package in packages if self._root_matches_any(package.package_root, incoming_roots)]

    def _should_replace_original_disc_file(
        self,
        file: LibraryFile,
        best_existing: LibraryPackageSummary,
        incoming_roots: set[str],
        incoming_disc_numbers: set[int],
        *,
        allow_disc_number_fallback: bool,
    ) -> bool:
        root = library_service.resolve_package_root(file)
        if root and self._root_matches_any(root, incoming_roots):
            return True
        if incoming_roots and not allow_disc_number_fallback:
            return False
        attrs = file.resource_attributes or ResourceAttributes()
        if incoming_disc_numbers:
            return bool(self._file_in_package(file, best_existing) and attrs.disc_number and int(attrs.disc_number) in incoming_disc_numbers)
        return self._file_in_package(file, best_existing)

    def _root_matches_any(self, root: str, candidates: set[str]) -> bool:
        normalized_root = normalize_path_separators(root).strip("/")
        for candidate in candidates:
            normalized_candidate = normalize_path_separators(candidate).strip("/")
            if normalized_candidate == normalized_root:
                return True
            if normalized_candidate.endswith(f"/{normalized_root}"):
                return True
            if normalized_root.endswith(f"/{normalized_candidate}"):
                return True
        return False


library_replacement_policy = LibraryReplacementPolicy()
