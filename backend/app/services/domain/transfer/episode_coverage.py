from __future__ import annotations

QualityRank = tuple[int, tuple[int, ...]]
FileRank = tuple[int, tuple[int, ...], int]
EpisodeCoverage = tuple[frozenset[int], FileRank]


def episode_group_dominates(
    candidate_quality: QualityRank,
    candidate_episodes: frozenset[int],
    target_quality: QualityRank,
    target_episodes: frozenset[int],
) -> bool:
    return candidate_quality > target_quality or (
        candidate_quality == target_quality
        and candidate_episodes < target_episodes
    )


def episode_coverage_satisfies(
    library_coverage: list[EpisodeCoverage],
    target_rank: FileRank,
    target_episodes: frozenset[int],
) -> bool:
    return any(
        candidate_episodes == target_episodes and candidate_rank >= target_rank
        for candidate_episodes, candidate_rank in library_coverage
    ) or all(
        any(
            episode in candidate_episodes
            and candidate_episodes != target_episodes
            and episode_group_dominates(
                candidate_rank[:2],
                candidate_episodes,
                target_rank[:2],
                target_episodes,
            )
            for candidate_episodes, candidate_rank in library_coverage
        )
        for episode in target_episodes
    )
