import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

export function useUrlParams(options = {}) {
  const {
    autoRestore = true,
    updateMethod = 'replace'
  } = options

  const route = useRoute()
  const router = useRouter()
  
  const params = ref({})

  const restoreFromUrl = () => {
    const urlParams = new URLSearchParams(window.location.search)
    const restored = {}
    
    for (const [key, value] of urlParams.entries()) {
      restored[key] = value
    }
    
    params.value = restored
    return restored
  }

  const updateUrl = (newParams = params.value) => {
    const searchParams = new URLSearchParams()
    
    Object.entries(newParams).forEach(([key, value]) => {
      if (value !== null && value !== undefined && value !== '') {
        searchParams.set(key, String(value))
      }
    })

    const currentHash = window.location.hash || route.hash || ''
    const newUrl = searchParams.toString()
      ? `${window.location.pathname}?${searchParams.toString()}${currentHash}`
      : `${window.location.pathname}${currentHash}`

    if (updateMethod === 'replace') {
      window.history.replaceState({}, '', newUrl)
    } else {
      router.push({ 
        path: route.path, 
        query: Object.fromEntries(searchParams.entries()) 
      })
    }
  }

  const setParam = (key, value) => {
    params.value[key] = value
    updateUrl()
  }

  const setParams = (newParams) => {
    params.value = { ...newParams }
    updateUrl()
  }

  const removeParam = (key) => {
    delete params.value[key]
    updateUrl()
  }

  const clearParams = () => {
    params.value = {}
    updateUrl()
  }

  watch(() => route.query, (newQuery) => {
    params.value = { ...newQuery }
  }, { immediate: true })

  if (autoRestore) {
    restoreFromUrl()
  }

  return {
    params,
    restoreFromUrl,
    updateUrl,
    setParam,
    setParams,
    removeParam,
    clearParams
  }
}
