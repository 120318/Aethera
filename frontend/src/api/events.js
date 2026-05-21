import http from '@/utils/http'
import { serializeArrayQueryParams } from '@/utils/queryParams'

export const listEvents = (params) => http.get('/api/v1/events/', {
  params,
  paramsSerializer: {
    serialize: serializeArrayQueryParams,
  },
})
export const getEventFilterOptions = (params) => http.get('/api/v1/events/filter-options', { params })

export const getEvent = (id) => http.get(`/api/v1/events/${id}`)
