import { cloneQualityRanking, qualityRankingDefaultState } from '@/composables/qualityRankingSupport'

export function createEmptyQualityProfile() {
  return {
    id: '',
    name: '',
    active_default: false,
    ranking: cloneQualityRanking(qualityRankingDefaultState),
    min_score: null,
    tag_scores: {},
  }
}

export function normalizeQualityProfile(profile) {
  return {
    ...createEmptyQualityProfile(),
    ...(profile || {}),
    ranking: cloneQualityRanking(profile?.ranking || qualityRankingDefaultState),
    tag_scores: { ...(profile?.tag_scores || {}) },
  }
}

export function qualityProfileTagScoreIds(profile) {
  return Object.keys(profile?.tag_scores || {})
}
