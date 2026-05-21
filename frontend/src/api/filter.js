import http from '@/utils/http'

export const getFilters = async () => {
  const data = await http.get('/api/v1/config/filters')
  return data.items
}

export const createFilter = async (data) => {
  const response = await http.post('/api/v1/config/filters', data)
  return response.filter
}

export const updateFilter = async (id, data) => {
  const response = await http.put(`/api/v1/config/filters/${id}`, data)
  return response.filter
}

export const deleteFilter = (id) => http.delete(`/api/v1/config/filters/${id}`)
