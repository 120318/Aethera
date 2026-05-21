import http from '@/utils/http'

export const getSchedulerJobs = () =>
  http.get('/api/v1/scheduler/jobs')

export const getSchedulerJobHistory = (jobId, params) =>
  http.get(`/api/v1/scheduler/jobs/${jobId}/history`, { params })

export const triggerSchedulerJob = (jobId) =>
  http.post(`/api/v1/scheduler/jobs/${jobId}/trigger`)
