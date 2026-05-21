import http from '@/utils/http'

export const getDiscoverListMetas = (source = null) => (
  http.get('/api/v1/discover/lists/options', source ? { params: { source } } : undefined)
)

export const getDiscoverLists = (params) => http.get('/api/v1/discover/lists', { params })
