import http from '@/utils/http'

const unwrapSubscriptionResponse = (payload) => payload?.data || payload || null

const subscriptionParams = (mediaId, seasonNumber = null) => {
  const params = { media_id: mediaId }
  if (Number.isInteger(Number(seasonNumber)) && Number(seasonNumber) > 0) {
    params.season_number = Number(seasonNumber)
  }
  return params
}

export const getSubscriptionState = async (mediaId, seasonNumber = null) =>
  unwrapSubscriptionResponse(await http.get('/api/v1/subscription/state', { params: subscriptionParams(mediaId, seasonNumber) }))

export const updateMediaSubscriptionState = async (mediaId, payload, seasonNumber = null) =>
  unwrapSubscriptionResponse(await http.put('/api/v1/subscription/state', payload, { params: subscriptionParams(mediaId, seasonNumber) }))

export const endCurrentSubscription = async (mediaId, seasonNumber = null) =>
  unwrapSubscriptionResponse(await http.post('/api/v1/subscription/end-current', {}, { params: subscriptionParams(mediaId, seasonNumber) }))

export const getMediaDownloadConfig = async (mediaId, seasonNumber = null) =>
  unwrapSubscriptionResponse(await http.get('/api/v1/subscription/download-config', { params: subscriptionParams(mediaId, seasonNumber) }))

export const updateMediaDownloadConfig = async (mediaId, payload, seasonNumber = null) =>
  unwrapSubscriptionResponse(await http.put('/api/v1/subscription/download-config', payload, { params: subscriptionParams(mediaId, seasonNumber) }))

export const saveSubscriptionDialog = async (mediaId, payload, seasonNumber = null) =>
  unwrapSubscriptionResponse(await http.put('/api/v1/subscription/dialog-save', payload, { params: subscriptionParams(mediaId, seasonNumber) }))

export const runSubscription = (subId) =>
  http.post('/api/v1/subscription/run', { sub_id: subId })
