import { ref, watch } from 'vue'

import { getSchedulerJobHistory } from '@/api/scheduler'

export function useSchedulerJobHistory(jobId) {
  const initialLoading = ref(true)
  const listLoading = ref(false)
  const items = ref([])
  const totalRecords = ref(0)
  const first = ref(0)
  const rows = ref(10)

  let loadRequestId = 0

  async function load() {
    const currentJobId = jobId.value
    if (!currentJobId) {
      items.value = []
      totalRecords.value = 0
      initialLoading.value = false
      return
    }

    const requestId = ++loadRequestId
    listLoading.value = true
    try {
      const data = await getSchedulerJobHistory(currentJobId, {
        limit: rows.value,
        offset: first.value,
      })
      if (requestId !== loadRequestId) return
      items.value = data?.items || []
      totalRecords.value = data?.total || 0
    } finally {
      if (requestId === loadRequestId) {
        listLoading.value = false
        initialLoading.value = false
      }
    }
  }

  function onPage(event) {
    first.value = event.first
    rows.value = event.rows
  }

  watch(jobId, () => {
    first.value = 0
    initialLoading.value = true
    load()
  }, { immediate: true })

  watch([first, rows], () => {
    if (!jobId.value) return
    load()
  })

  return {
    first,
    initialLoading,
    items,
    listLoading,
    onPage,
    rows,
    totalRecords,
  }
}
