from __future__ import annotations

QualityRank = tuple[int, tuple[int, ...]]


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
