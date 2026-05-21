import { ref, reactive } from 'vue'
import { searchMediaByEndpoint } from '@/api/media'
import { useNotificationStore } from '@/stores/notification'
import { t } from '@/i18n'

export function useSearch(options = {}) {
  const {
    apiEndpoint = '/api/v1/media/search',
    defaultFilters = {},
    onSuccess,
    onError
  } = options

  const notification = useNotificationStore()

  const query = ref('')
  const loading = ref(false)
  const results = ref([])
  const hasSearched = ref(false)
  const filters = reactive({ ...defaultFilters })

  const search = async (searchQuery = query.value) => {
    if (!searchQuery?.trim()) {
      notification.warn(t('search.enterKeyword'))
      return
    }

    // Prevent duplicate searches if already loading
    if (loading.value) {
      return
    }

    loading.value = true
    hasSearched.value = true

    try {
      // Copy filters and remove media_type when set to 'all' or empty (means search across all types)
      const paramsFilters = { ...filters }
      if (paramsFilters.media_type === 'all' || paramsFilters.media_type === '') {
        delete paramsFilters.media_type
      }
      const params = {
        query: searchQuery.trim(),
        ...paramsFilters
      }

      const data = await searchMediaByEndpoint(apiEndpoint, params)
      results.value = data.data?.results || data.results || data || []
      const count = results.value.length
      if (count === 0) {
        notification.info(t('search.noMediaFound'))
      } else {
        notification.success(t('search.mediaFound', { count }))
      }
      if (onSuccess) {
        onSuccess(results.value, data)
      }
    } catch (error) {
      console.error(t('search.failedLog'), error)
      results.value = []
      if (onError) {
        onError(error)
      }
    } finally {
      loading.value = false
    }
  }

  const resetSearch = () => {
    query.value = ''
    results.value = []
    hasSearched.value = false
    Object.keys(filters).forEach(key => {
      filters[key] = defaultFilters[key] || ''
    })
  }

  const clearResults = () => {
    results.value = []
    hasSearched.value = false
  }

  return {
    query,
    loading,
    results,
    hasSearched,
    filters,
    search,
    resetSearch,
    clearResults
  }
}
