import http from '@/utils/http'

export const getBackendLogs = (params) => http.get('/api/v1/logs/backend', { params })
