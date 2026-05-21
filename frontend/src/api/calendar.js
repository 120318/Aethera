import http from '@/utils/http'

export const listAirings = async (params) => {
  const data = await http.get('/api/v1/calendar/airings', { params })
  return data.data || []
}
