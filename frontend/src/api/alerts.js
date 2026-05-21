import http from '@/utils/http'

export const getAlertCenter = () => http.get('/api/v1/alerts/center')

export const acknowledgeAlert = (alertId) => http.post(`/api/v1/alerts/${alertId}/acknowledge`)
