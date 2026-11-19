from __future__ import annotations

import re

from pydantic import BaseModel

from app.services.integration.danmu.models import DanmuEpisodeCandidate, DanmuEpisodeMatch


class _IssueEpisode(BaseModel):
    candidate: DanmuEpisodeCandidate
    issue_number: int
    part_number: int


class DanmuEpisodeMatcher:
    """Select a regular video from a normalized, season-scoped provider catalog."""

    def has_issue_label(self, candidate: DanmuEpisodeCandidate) -> bool:
        return self._issue_episode(candidate) is not None

    def select(
        self,
        candidates: list[DanmuEpisodeCandidate],
        episode_number: int,
        *,
        absolute_episode_number: int | None = None,
    ) -> DanmuEpisodeMatch:
        if episode_number < 1:
            return DanmuEpisodeMatch()
        regular = [candidate for candidate in candidates if self._is_regular(candidate)]
        issues = [issue for candidate in regular if (issue := self._issue_episode(candidate)) is not None]
        if issues:
            return DanmuEpisodeMatch(
                candidate=self._select_issue_episode(issues, episode_number),
                has_regular_episodes=True,
                uses_issue_order=True,
            )
        if regular and all(candidate.sequence_index is not None for candidate in regular):
            return self._select_ordered_episode(regular, episode_number)
        numbered: dict[int, list[DanmuEpisodeCandidate]] = {}
        number_by_video: dict[str, int] = {}
        for candidate in regular:
            number = self._episode_number(candidate)
            if number is not None:
                if candidate.external_id in number_by_video and number_by_video[candidate.external_id] != number:
                    return DanmuEpisodeMatch(has_regular_episodes=True)
                number_by_video[candidate.external_id] = number
                numbered.setdefault(number, []).append(candidate)
        if numbered:
            for number in dict.fromkeys([episode_number, absolute_episode_number]):
                if number is None or number not in numbered:
                    continue
                matches = {candidate.external_id: candidate for candidate in numbered[number]}
                return DanmuEpisodeMatch(
                    candidate=next(iter(matches.values())) if len(matches) == 1 else None,
                    has_regular_episodes=True,
                )
            return DanmuEpisodeMatch(has_regular_episodes=True)
        return self._select_ordered_episode(regular, episode_number)

    def _is_regular(self, candidate: DanmuEpisodeCandidate) -> bool:
        return bool(candidate.external_id) and not candidate.excluded and not any(
            keyword in title
            for title in candidate.titles
            for keyword in ("预告", "花絮", "片花", "彩蛋", "先导片", "加更")
        )

    def _issue_episode(self, candidate: DanmuEpisodeCandidate) -> _IssueEpisode | None:
        for title in candidate.titles:
            match = re.match(
                r"^第\s*([1-9]\d*)\s*期(?:\s*[（(]?\s*([上中下])\s*[）)]?)?\s*(?=[：:]|$)",
                title.strip(),
            )
            if match:
                return _IssueEpisode(
                    candidate=candidate,
                    issue_number=int(match.group(1)),
                    part_number={None: 0, "上": 1, "中": 2, "下": 3}[match.group(2)],
                )
        return None

    def _select_issue_episode(self, episodes: list[_IssueEpisode], episode_number: int) -> DanmuEpisodeCandidate | None:
        by_order: dict[tuple[int, int], DanmuEpisodeCandidate] = {}
        order_by_video: dict[str, tuple[int, int]] = {}
        for episode in episodes:
            order = (episode.issue_number, episode.part_number)
            video_id = episode.candidate.external_id
            if order in by_order and by_order[order].external_id != video_id:
                return None
            if video_id in order_by_video and order_by_video[video_id] != order:
                return None
            by_order[order] = episode.candidate
            order_by_video[video_id] = order
        orders = sorted(by_order)
        if episode_number < 1 or episode_number > len(orders):
            return None
        last_issue = orders[-1][0]
        for issue in range(1, last_issue + 1):
            parts = {part for number, part in orders if number == issue}
            if parts in ({0}, {1, 3}, {1, 2, 3}):
                continue
            if issue == last_issue and parts in ({1}, {1, 2}):
                continue
            return None
        return by_order[orders[episode_number - 1]]

    def _episode_number(self, candidate: DanmuEpisodeCandidate) -> int | None:
        for title in candidate.titles:
            title = title.strip()
            if title.isdecimal():
                return int(title)
            match = re.search(r"(?:第\s*)?0*(\d+)\s*(?:集|话)(?!\d)|_0*(\d+)(?!\d)", title)
            if match:
                return int(match.group(1) or match.group(2))
        return candidate.episode_number

    def _select_ordered_episode(self, candidates: list[DanmuEpisodeCandidate], episode_number: int) -> DanmuEpisodeMatch:
        if not candidates or any(candidate.sequence_index is None for candidate in candidates):
            return DanmuEpisodeMatch()
        by_video: dict[str, DanmuEpisodeCandidate] = {}
        for candidate in candidates:
            previous = by_video.get(candidate.external_id)
            if previous is None or candidate.sequence_index < previous.sequence_index:
                by_video[candidate.external_id] = candidate
        ordered = sorted(by_video.values(), key=lambda candidate: candidate.sequence_index)
        if len({candidate.sequence_index for candidate in ordered}) != len(ordered):
            return DanmuEpisodeMatch(has_regular_episodes=True)
        return DanmuEpisodeMatch(
            candidate=ordered[episode_number - 1] if 1 <= episode_number <= len(ordered) else None,
            has_regular_episodes=True,
        )


danmu_episode_matcher = DanmuEpisodeMatcher()
