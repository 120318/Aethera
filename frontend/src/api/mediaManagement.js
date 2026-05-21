import http from '@/utils/http'

export const getMediaManagementSummary = () =>
  http.get('/api/v1/media-management/summary')

export const listMediaManagementItems = (params = {}) =>
  http.get('/api/v1/media-management/items', { params })
