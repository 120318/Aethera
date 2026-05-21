import http from '@/utils/http'

export const getTags = async () => {
  const data = await http.get('/api/v1/config/tags')
  return data.items
}

export const createTag = async (data) => {
  const response = await http.post('/api/v1/config/tags', data)
  return response.tag
}

export const updateTag = async (id, data) => {
  const response = await http.put(`/api/v1/config/tags/${id}`, data)
  return response.tag
}

export const deleteTag = (id) => http.delete(`/api/v1/config/tags/${id}`)
