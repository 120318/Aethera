import { t } from '@/i18n'

export const TorrentStatus = {
  DOWNLOADING: 'downloading',
  ACTIVE: 'active',
  MISSING: 'missing'
}

export const MediaStatus = {
  ACTIVE: 'active',
  MISSING: 'missing'
}

export const CombinedStatus = {
  DOWNLOADING_WITH_MEDIA: 'downloading_with_media',
  DOWNLOADING_MISSING: 'downloading_missing',
  SEEDING_IN_LIBRARY: 'seeding_in_library',
  SEEDING_ONLY: 'seeding_only',
  MEDIA_ONLY: 'media_only',
  BOTH_MISSING: 'both_missing'
}

export function getCombinedStatus(torrentStatus, mediaStatus) {
  const torrent = torrentStatus || TorrentStatus.MISSING
  const media = mediaStatus || MediaStatus.MISSING
  
  if (torrent === TorrentStatus.DOWNLOADING) {
    return media === MediaStatus.ACTIVE 
      ? CombinedStatus.DOWNLOADING_WITH_MEDIA
      : CombinedStatus.DOWNLOADING_MISSING
  }
  
  if (torrent === TorrentStatus.ACTIVE) {
    return media === MediaStatus.ACTIVE
      ? CombinedStatus.SEEDING_IN_LIBRARY
      : CombinedStatus.SEEDING_ONLY
  }
  
  if (torrent === TorrentStatus.MISSING) {
    return media === MediaStatus.ACTIVE
      ? CombinedStatus.MEDIA_ONLY
      : CombinedStatus.BOTH_MISSING
  }
  
  return CombinedStatus.BOTH_MISSING
}

export function getStatusDisplay(torrentStatus, mediaStatus) {
  const combined = getCombinedStatus(torrentStatus, mediaStatus)
  
  const displayMap = {
    [CombinedStatus.DOWNLOADING_MISSING]: {
      text: t('resourceStatus.combined.downloadingMissing.text'),
      type: 'primary',
      icon: 'Download',
      description: t('resourceStatus.combined.downloadingMissing.description')
    },
    [CombinedStatus.DOWNLOADING_WITH_MEDIA]: {
      text: t('resourceStatus.combined.downloadingWithMedia.text'),
      type: 'primary',
      icon: 'Download',
      description: t('resourceStatus.combined.downloadingWithMedia.description')
    },
    [CombinedStatus.SEEDING_IN_LIBRARY]: {
      text: t('resourceStatus.combined.seedingInLibrary.text'),
      type: 'success',
      icon: 'Upload',
      description: t('resourceStatus.combined.seedingInLibrary.description')
    },
    [CombinedStatus.SEEDING_ONLY]: {
      text: t('resourceStatus.combined.seedingOnly.text'),
      type: 'warning',
      icon: 'Upload',
      description: t('resourceStatus.combined.seedingOnly.description')
    },
    [CombinedStatus.MEDIA_ONLY]: {
      text: t('resourceStatus.combined.mediaOnly.text'),
      type: 'success',
      icon: 'VideoCamera',
      description: t('resourceStatus.combined.mediaOnly.description')
    },
    [CombinedStatus.BOTH_MISSING]: {
      text: t('resourceStatus.combined.bothMissing.text'),
      type: 'info',
      icon: 'Delete',
      description: t('resourceStatus.combined.bothMissing.description')
    }
  }
  
  return displayMap[combined] || {
    text: t('common.unknown'),
    type: 'info',
    icon: 'QuestionFilled',
    description: t('taskLive.unknownStatus')
  }
}

export function getTorrentStatusDisplay(torrentStatus) {
  const displayMap = {
    [TorrentStatus.DOWNLOADING]: {
      text: t('resourceStatus.torrent.downloading'),
      type: 'primary',
      color: 'var(--state-info)'
    },
    [TorrentStatus.ACTIVE]: {
      text: t('resourceStatus.torrent.active'),
      type: 'success',
      color: 'var(--state-success)'
    },
    [TorrentStatus.MISSING]: {
      text: t('resourceStatus.torrent.missing'),
      type: 'info',
      color: 'var(--p-surface-500)'
    }
  }
  
  return displayMap[torrentStatus] || {
    text: t('common.unknown'),
    type: 'info',
    color: 'var(--p-surface-500)'
  }
}

export function getMediaStatusDisplay(mediaStatus) {
  const displayMap = {
    [MediaStatus.ACTIVE]: {
      text: t('resourceStatus.media.active'),
      type: 'success',
      color: 'var(--state-success)'
    },
    [MediaStatus.MISSING]: {
      text: t('resourceStatus.media.missing'),
      type: 'info',
      color: 'var(--p-surface-500)'
    }
  }
  
  return displayMap[mediaStatus] || {
    text: t('common.unknown'),
    type: 'info',
    color: 'var(--p-surface-500)'
  }
}

export function getAvailableActions(torrentStatus, mediaStatus) {
  return {
    canDeleteTorrent: torrentStatus !== TorrentStatus.MISSING,
    canDeleteMedia: mediaStatus === MediaStatus.ACTIVE,
    canTransfer: torrentStatus === TorrentStatus.ACTIVE && mediaStatus === MediaStatus.MISSING,
    canDownload: torrentStatus === TorrentStatus.MISSING,
    
    showTorrentOption: torrentStatus !== TorrentStatus.MISSING,
    showMediaOption: mediaStatus === MediaStatus.ACTIVE,
    showBothOption: torrentStatus !== TorrentStatus.MISSING && mediaStatus === MediaStatus.ACTIVE,
    
    defaultDeleteOption: (() => {
      if (torrentStatus === TorrentStatus.MISSING) return 'media'
      if (mediaStatus === MediaStatus.MISSING) return 'torrent'
      return 'both'
    })()
  }
}

export function canTransfer(resource) {
  if (!resource) return false
  
  const progress = resource.progress || 0
  if (progress < 1) return false
  
  const torrentStatus = resource.torrent_status
  const mediaStatus = resource.media_status
  
  return torrentStatus === TorrentStatus.ACTIVE && mediaStatus === MediaStatus.MISSING
}

export function getProgressBarClass(torrentStatus, mediaStatus, progress) {
  if (torrentStatus === TorrentStatus.MISSING) {
    return 'missing'
  }
  
  if (torrentStatus === TorrentStatus.DOWNLOADING && progress < 1) {
    return 'downloading'
  }
  
  if (torrentStatus === TorrentStatus.ACTIVE || (torrentStatus === TorrentStatus.DOWNLOADING && progress >= 1)) {
    if (mediaStatus === MediaStatus.ACTIVE) {
      return 'transferred'
    }
    return 'seeding'
  }
  
  return ''
}

export function isResourceRemoved(resource) {
  return resource?.torrent_status === TorrentStatus.MISSING ||
         resource?.media_status === MediaStatus.MISSING
}

export function isTorrentRemoved(resource) {
  return resource?.torrent_status === TorrentStatus.MISSING
}

export function isMediaRemoved(resource) {
  return resource?.media_status === MediaStatus.MISSING
}

export function isMediaMissing(resource) {
  return resource?.media_status === MediaStatus.MISSING
}
