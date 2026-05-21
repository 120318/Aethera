import http from '@/utils/http'

export const getQualityProfiles = async () => {
  const data = await http.get('/api/v1/config/quality_profiles')
  return data.items
}

export const createQualityProfile = async (payload) => {
  const response = await http.post('/api/v1/config/quality_profiles', payload)
  return response.profile
}

export const updateQualityProfile = async (id, payload) => {
  const response = await http.put(`/api/v1/config/quality_profiles/${id}`, payload)
  return response.profile
}

export const deleteQualityProfile = (id) => http.delete(`/api/v1/config/quality_profiles/${id}`)
