import { ref, watch } from 'vue'

export function useDirectoryIntegrityPagination({
  page,
  directoryFilter,
  scopeFilter,
  issueTypeFilters,
  onPageChange,
}) {
  const rows = ref(10)
  const first = ref((Math.max(1, page.value) - 1) * rows.value)
  let directoryFilterInitialized = false

  watch(page, (nextPage) => {
    const nextFirst = (Math.max(1, nextPage) - 1) * rows.value
    if (first.value !== nextFirst) first.value = nextFirst
  })

  watch(directoryFilter, () => {
    if (!directoryFilterInitialized) {
      directoryFilterInitialized = true
      return
    }
    resetPage()
  })
  watch(scopeFilter, resetPage)
  watch(issueTypeFilters, resetPage, { deep: true })

  function onPage(event) {
    first.value = event.first
    rows.value = event.rows
    onPageChange({
      page: Math.floor(event.first / event.rows) + 1,
      history: 'push',
    })
  }

  function resetPage() {
    const changed = first.value !== 0
    first.value = 0
    if (changed || page.value > 1) {
      onPageChange({ page: 1, history: 'replace' })
    }
  }

  return { first, rows, onPage }
}
