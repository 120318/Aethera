import http from '@/utils/http'
import { serializeArrayQueryParams } from '@/utils/queryParams'

export const listActions = (params) => http.get('/api/v1/actions/', {
  params,
  paramsSerializer: {
    serialize: serializeArrayQueryParams,
  },
})
export const getActiveActions = (params = {}) => http.get('/api/v1/actions/active', {
  params,
  paramsSerializer: {
    serialize: serializeArrayQueryParams,
  },
})
export const getActionFilterOptions = (params) => http.get('/api/v1/actions/filter-options', { params })
export const getAction = (id) => http.get(`/api/v1/actions/${id}`)
