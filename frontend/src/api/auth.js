import http from '@/utils/http'

export const getBootstrapStatus = () => http.get('/api/v1/auth/bootstrap-status')
export const bootstrap = (data) => http.post('/api/v1/auth/bootstrap', data)
export const login = (data) => http.post('/api/v1/auth/login', data)
export const logout = () => http.post('/api/v1/auth/logout')
export const me = () => http.get('/api/v1/auth/me')
export const setPassword = (data) => http.post('/api/v1/auth/set-password', data)
export const changePassword = (data) => http.post('/api/v1/auth/change-password', data)
export const getAuthProviders = async () => {
  const data = await http.get('/api/v1/auth/providers')
  return data.providers || []
}
export const startAuthProviderLogin = (providerId, data) => http.post(`/api/v1/auth/providers/${providerId}/start`, data)
