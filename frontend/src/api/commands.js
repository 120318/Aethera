import http from '@/utils/http'
import { serializeArrayQueryParams } from '@/utils/queryParams'

export const createCommand = async (payload) => {
  const data = await http.post('/api/v1/commands/', payload)
  return data.command
}

export const getActiveCommands = async (params = {}) => {
  const data = await http.get('/api/v1/commands/active', {
    params,
    paramsSerializer: {
      serialize: serializeArrayQueryParams,
    },
  })
  return data.items
}

export const getCommands = async (params = {}) => {
  const data = await http.get('/api/v1/commands/', {
    params,
    paramsSerializer: {
      serialize: serializeArrayQueryParams,
    },
  })
  return data.items
}

export const getCommand = async (commandId) => {
  const data = await http.get(`/api/v1/commands/${commandId}`)
  return data.command
}

export const cancelCommand = async (commandId) => {
  const data = await http.post(`/api/v1/commands/${commandId}/cancel`)
  return data.command
}
