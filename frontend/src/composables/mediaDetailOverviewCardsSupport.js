import { formatAbsoluteDateTime, formatRelativeTime } from '@/utils/formatters'
import { t } from '@/i18n'
import { dedupePlatforms, platformDisplayName } from '@/utils/mediaPlatforms'

export function buildMediaDetailOverviewCards({
  detailOverviewSummary,
  loading,
  loadingSubscription,
  dataLoaded,
  isTvMedia,
  subscription,
  detail,
  filterPresetName,
}) {
  const summary = detailOverviewSummary.value
  const local = summary?.local_resources || null
  const resourceDiscovery = summary?.resource_discovery || null
  const config = summary?.download_config || null
  const subscriptionSummary = summary?.subscription || null

  return {
    showSkeleton: loading.value || loadingSubscription.value || !dataLoaded.overview,
    subscription: {
      subscribed: !!subscriptionSummary?.subscribed,
      followed: !!subscriptionSummary?.followed,
      modeLabel: t('mediaDetail.subscriptionModeLabel'),
      mode: resolveSubscriptionModeLabel(
        subscriptionSummary?.subscription_mode,
        isTvMedia.value ? 'current_aired_complete' : 'first_release',
      ),
      lastCheckedAt: subscription.value?.last_checked_at || null,
      lastCheckedLabel: subscription.value?.last_checked_at ? formatRelativeTime(subscription.value.last_checked_at) : '',
      endedReason: resolveEndedReasonLabel(subscription.value?.ended_reason),
    },
    availableResources: {
      searched: !!resourceDiscovery?.searched,
      searchState: resourceDiscovery?.search_state || 'idle',
      availableCount: Number(resourceDiscovery?.available_count || 0),
      matchedByIdCount: Number(resourceDiscovery?.matched_by_id_count || 0),
      matchedByCustomRuleCount: Number(resourceDiscovery?.matched_by_custom_rule_count || 0),
    },
    currentConfig: {
      directory: resolveConfigLabel(config?.directory, t('common.notSet')),
      filter: resolveConfigLabel(config?.filter, filterPresetName.value || t('mediaDetail.emptyValue')),
      qualityProfile: resolveConfigLabel(config?.quality_profile, t('common.notSet')),
      customRules: resolveSummaryLabel(config?.custom_rules, t('common.notSet')),
    },
    localResources: {
      totalEpisodes: Number(local?.total_episodes || detail.value?.episodes_count || 0),
      collectedCount: Number(local?.collected_count || 0),
      downloadingCount: Number(local?.downloading_count || 0),
      missingCount: Math.max(0, Number(local?.total_episodes || detail.value?.episodes_count || 0) - Number(local?.collected_count || 0)),
      nextEpisodeToAir: local?.next_episode_to_air || null,
      schedule: local?.schedule || null,
      releaseDates: Array.isArray(local?.schedule?.release_dates) ? local.schedule.release_dates : [],
      airings: Array.isArray(detail.value?.airings) ? detail.value.airings : [],
    },
    resourceSummary: {
      primaryParts: buildResourcePrimaryParts(local, detail.value),
      statsParts: buildResourceStatsParts(local, detail.value),
      secondaryParts: buildResourceSecondaryParts(resourceDiscovery),
    },
  }
}

function resolveConfigLabel(item, fallback) {
  if (item?.name) return item.name
  if (item?.name_key) return t(item.name_key, item.name_params || {})
  return fallback
}

function resolveSummaryLabel(item, fallback) {
  if (item?.summary) return item.summary
  if (item?.summary_key) return t(item.summary_key, item.summary_params || {})
  return fallback
}

function resolveEndedReasonLabel(reason) {
  if (!reason) return ''
  if (reason === 'manual') return t('mediaDetail.overviewText.endedManual')
  if (reason === 'movie_library_completed') return t('mediaDetail.overviewText.endedMovieLibraryCompleted')
  if (reason === 'movie_downloading_completed') return t('mediaDetail.overviewText.endedMovieDownloadingCompleted')
  if (reason === 'tv_completed') return t('mediaDetail.overviewText.endedTvCompleted')
  if (reason === 'tv_upgrade_completed') return t('mediaDetail.overviewText.endedTvUpgradeCompleted')
  return ''
}

function resolveSubscriptionModeLabel(mode, fallbackMode) {
  const normalized = String(mode || fallbackMode || '').trim().toLowerCase()
  if (normalized === 'first_release' || normalized === 'first release') return t('subscription.modeFirstRelease')
  if (normalized === 'current_aired_complete' || normalized === 'until complete') return t('subscription.modeCurrentAiredComplete')
  if (normalized === 'upgrade_continuous' || normalized === 'continuous upgrade') return t('subscription.modeUpgradeContinuous')
  return mode || ''
}

function isEndedScheduleStatus(statusLabel) {
  const normalized = String(statusLabel || '').trim().toLowerCase()
  return normalized === 'ended' || normalized === t('mediaDetail.overviewText.statusEnded').toLowerCase()
}

function resolveScheduleStatusLabel(statusLabel) {
  const normalized = String(statusLabel || '').trim().toLowerCase()
  if (normalized === 'ended') return t('mediaDetail.overviewText.statusEnded')
  if (normalized === 'airing') return t('mediaDetail.overviewText.statusAiring')
  return statusLabel || ''
}

function buildResourcePrimaryParts(local, detail) {
  const totalEpisodes = Number(local?.total_episodes || detail?.episodes_count || 0)
  const mediaType = local?.schedule?.media_type || detail?.media_type || detail?.type || ''
  const capabilities = detail?.metadata_capabilities || {}

  if (mediaType === 'tv') {
    const parts = []
    if (capabilities.has_schedule || totalEpisodes > 0) {
      parts.push({
        key: 'total',
        segments: [
          { text: capabilities.has_schedule ? t('mediaDetail.overviewText.scheduleLabel') : t('mediaDetail.overviewText.currentInfoLabel'), accent: false, muted: true },
          { text: t('mediaDetail.overviewText.totalPrefix'), accent: false },
          { text: totalEpisodes > 0 ? String(totalEpisodes) : '--', accent: true },
          { text: t('mediaDetail.overviewText.episodeUnit'), accent: false },
        ],
      })
    }

    if (local?.schedule?.first_air_date) {
      parts.push({
        key: 'first-air',
        segments: [
          { text: t('mediaDetail.overviewText.firstAiredAt'), accent: false },
          { text: formatDate(local.schedule.first_air_date), accent: false },
        ],
      })
    }

    const platforms = formatPlatforms(resolveSchedulePlatforms(local?.schedule))
    if (platforms.length > 0) {
      const segments = [{ text: t('mediaDetail.overviewText.onPlatformPrefix'), accent: false }]
      platforms.forEach((platform, index) => {
        if (index > 0) segments.push({ text: t('mediaDetail.overviewText.platformSeparator'), accent: false })
        segments.push({ text: platform.name, accent: true, url: platform.url || '', key: platform.key })
      })
      segments.push({ text: t('mediaDetail.overviewText.platformSuffix'), accent: false })
      parts.push({ key: 'platforms', segments })
    }

    if (isEndedScheduleStatus(local?.schedule?.status_label)) {
      parts.push({ key: 'status-ended', segments: [{ text: t('mediaDetail.overviewText.currentPrefix'), accent: false }, { text: t('mediaDetail.overviewText.statusEnded'), accent: true }] })
    } else {
      if (local?.schedule?.latest_aired_episode?.episode_number) {
        parts.push({ key: 'latest-aired', segments: [{ text: t('mediaDetail.overviewText.latestAiredPrefix'), accent: false }, ...buildEpisodeSegments(local.schedule.latest_aired_episode)] })
      } else if (Number(local?.schedule?.aired_episode_count || 0) > 0) {
        parts.push({
          key: 'aired-count',
          segments: [
            { text: t('mediaDetail.overviewText.airedCountPrefix'), accent: false },
            { text: String(Number(local.schedule.aired_episode_count || 0)), accent: true },
            { text: t('mediaDetail.overviewText.episodeUnit'), accent: false },
          ],
        })
      }
      if (local?.schedule?.next_episode_to_air?.air_date) {
        parts.push({
          key: 'next-air',
          segments: [
            { text: t('mediaDetail.overviewText.nextEpisodePrefix'), accent: false },
            ...buildEpisodeSegments(local.schedule.next_episode_to_air),
            { text: t('mediaDetail.overviewText.atDatePrefix'), accent: false },
            { text: formatDate(local.schedule.next_episode_to_air.air_date), accent: true },
            { text: t('mediaDetail.overviewText.airDateSuffix'), accent: false },
          ],
        })
      } else if (local?.schedule?.status_label) {
        parts.push({ key: 'status', segments: [{ text: t('mediaDetail.overviewText.currentPrefix'), accent: false }, { text: resolveScheduleStatusLabel(local.schedule.status_label), accent: true }] })
      }
    }

    return parts
  }

  const parts = []
  if (local?.schedule?.theatrical_release_date) {
    parts.push({ key: 'theatrical', segments: [{ text: t('mediaDetail.overviewText.theatricalReleasedAt'), accent: false }, { text: formatDate(local.schedule.theatrical_release_date), accent: false }] })
  }
  if (local?.schedule?.digital_release_date) {
    parts.push({ key: 'digital', segments: [{ text: t('mediaDetail.overviewText.digitalReleasedAt'), accent: false }, { text: formatDate(local.schedule.digital_release_date), accent: false }] })
  }
  const platforms = formatPlatforms(resolveSchedulePlatforms(local?.schedule))
  if (platforms.length > 0) {
    const segments = [{ text: t('mediaDetail.overviewText.onPlatformPrefix'), accent: false }]
    platforms.forEach((platform, index) => {
      if (index > 0) segments.push({ text: t('mediaDetail.overviewText.platformSeparator'), accent: false })
      segments.push({ text: platform.name, accent: true, url: platform.url || '', key: platform.key })
    })
    segments.push({ text: t('mediaDetail.overviewText.platformSuffix'), accent: false })
    parts.push({ key: 'platforms', segments })
  }
  if (local?.schedule?.physical_release_date) {
    parts.push({ key: 'physical', segments: [{ text: t('mediaDetail.overviewText.physicalReleasedAt'), accent: false }, { text: formatDate(local.schedule.physical_release_date), accent: false }] })
  }
  if (parts.length > 0) {
    parts[0] = { ...parts[0], segments: [{ text: `${t('mediaDetail.overviewText.releaseDetails')}：`, accent: false, muted: true }, ...parts[0].segments] }
  }
  if (parts.length === 0) {
    return [{ key: 'schedule-missing', segments: [{ text: t('mediaDetail.overviewText.releaseInfoLabel'), accent: false, muted: true }, { text: t('mediaDetail.overviewText.pendingCompletion'), accent: false }] }]
  }
  return parts
}

function buildResourceStatsParts(local, detail) {
  const totalEpisodes = Number(local?.total_episodes || detail?.episodes_count || 0)
  const collectedCount = Number(local?.collected_count || 0)
  const downloadingCount = Number(local?.downloading_count || 0)
  const missingCount = Math.max(0, totalEpisodes - collectedCount)
  const mediaType = local?.schedule?.media_type || detail?.media_type || detail?.type || ''
  if (mediaType !== 'tv') return []
  return [
    { key: 'collected', segments: [{ text: t('mediaDetail.overviewText.localResourcesLabel'), accent: false, muted: true }, { text: t('mediaDetail.overviewText.collectedPrefix'), accent: false }, { text: String(collectedCount), accent: true }, { text: t('mediaDetail.overviewText.episodeUnit'), accent: false }] },
    { key: 'downloading', segments: [{ text: t('mediaDetail.overviewText.downloadingPrefix'), accent: false }, { text: String(downloadingCount), accent: true }, { text: t('mediaDetail.overviewText.episodeUnit'), accent: false }] },
    { key: 'missing', segments: [{ text: t('mediaDetail.overviewText.missingPrefix'), accent: false }, { text: String(missingCount), accent: true }, { text: t('mediaDetail.overviewText.episodeUnit'), accent: false }] },
  ]
}

function buildResourceSecondaryParts(resourceDiscovery) {
  if (!resourceDiscovery?.searched) return []
  const availableCount = Number(resourceDiscovery.available_count || 0)
  const matchedByIdCount = Number(resourceDiscovery.matched_by_id_count || 0)
  const matchedByCustomRuleCount = Number(resourceDiscovery.matched_by_custom_rule_count || 0)
  const parts = [
    { key: 'history-available', segments: [{ text: t('mediaDetail.overviewText.searchResultsLabel'), accent: false, muted: true }, { text: String(availableCount), accent: true }, { text: t('mediaDetail.overviewText.availableResourcesSuffix'), accent: false }] },
    { key: 'matched-id', segments: [{ text: String(matchedByIdCount), accent: true }, { text: t('mediaDetail.overviewText.matchedIdSuffix'), accent: false }] },
    { key: 'matched-rule', segments: [{ text: String(matchedByCustomRuleCount), accent: true }, { text: t('mediaDetail.overviewText.matchedRuleSuffix'), accent: false }] },
  ]
  if (resourceDiscovery.searched_at) {
    parts.push({
      key: 'searched-at',
      segments: [
        {
          text: formatRelativeTime(resourceDiscovery.searched_at),
          accent: true,
          tooltip: formatAbsoluteDateTime(resourceDiscovery.searched_at),
        },
        { text: t('mediaDetail.overviewText.searchedAtSuffix'), accent: false },
      ],
    })
  }
  return parts
}

function buildEpisodeSegments(episode) {
  return [{ text: t('mediaDetail.overviewText.episodePrefix'), accent: false }, { text: String(episode?.episode_number || 0), accent: true }, { text: t('mediaDetail.overviewText.episodeUnit'), accent: false }]
}

function formatDate(value) {
  return String(value || '').slice(0, 10)
}

function isTmdbWatchUrl(url) {
  if (!url) return false
  try {
    const parsed = new URL(url)
    return parsed.hostname.includes('themoviedb.org') && parsed.pathname.endsWith('/watch')
  } catch {
    return false
  }
}

function formatPlatforms(platforms) {
  if (!Array.isArray(platforms) || platforms.length === 0) return []
  return dedupePlatforms(platforms, 3)
    .map((platform) => ({
      key: `${platform?.id || platform?.name || 'platform'}-${platform?.region || ''}`,
      name: platformDisplayName(platform),
      url: isTmdbWatchUrl(platform?.url) ? '' : (platform?.url || ''),
    }))
    .filter((platform) => platform.name)
    .slice(0, 3)
}

function resolveSchedulePlatforms(schedule) {
  if (!schedule) return []
  return Array.isArray(schedule.platforms) ? schedule.platforms : []
}
