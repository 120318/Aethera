import { ref } from 'vue'
import { getDirectories } from '@/api/config'
import { getTags } from '@/api/tags'
import { getFilters } from '@/api/filter'
import { getQualityProfiles } from '@/api/quality_profiles'
import { getResourceSites } from '@/api/resource'
import {
  buildTagOptions,
  buildDirectoryOptions,
  getDefaultDirectoryId,
} from '@/composables/subscriptionConfigDialogSupport'

export function useSubscriptionDialogCatalogs({ props, mediaType, form, notification, t }) {
  const loadingDirs = ref(false)
  const directoryOptions = ref([])
  const filterOptions = ref([])
  const qualityProfileOptions = ref([])
  const tagOptions = ref([])
  const siteOptions = ref([])

  async function fetchDirectories() {
    const catalogDirectories = Array.isArray(props.catalogs?.directories) ? props.catalogs.directories : []
    if (catalogDirectories.length > 0) {
      const typedDirectories = buildDirectoryOptions(mediaType.value, catalogDirectories)
      directoryOptions.value = typedDirectories
      if (!form.directory_id) {
        form.directory_id = getDefaultDirectoryId(mediaType.value, typedDirectories)
      }
      return
    }
    loadingDirs.value = true
    try {
      const response = await getDirectories()
      const directories = response.directories || []
      const typedDirectories = buildDirectoryOptions(mediaType.value, directories)
      directoryOptions.value = typedDirectories
      if (!form.directory_id) {
        form.directory_id = getDefaultDirectoryId(mediaType.value, typedDirectories)
      }
    } catch (error) {
      console.error(t('subscription.loadDirectoriesFailedLog'), error)
      notification.error(t('subscription.loadDirectoriesFailed'))
    } finally {
      loadingDirs.value = false
    }
  }

  async function fetchFilterPresets() {
    const catalogFilters = Array.isArray(props.catalogs?.filters) ? props.catalogs.filters : []
    if (catalogFilters.length > 0) {
      filterOptions.value = catalogFilters
      return
    }
    try {
      filterOptions.value = await getFilters()
    } catch (error) {
      console.error(t('subscription.loadFilterListFailed'), error)
    }
  }

  async function fetchQualityProfiles() {
    const catalogProfiles = Array.isArray(props.catalogs?.quality_profiles) ? props.catalogs.quality_profiles : []
    if (catalogProfiles.length > 0) {
      qualityProfileOptions.value = catalogProfiles
      return
    }
    try {
      qualityProfileOptions.value = await getQualityProfiles()
    } catch (error) {
      console.error(t('subscription.loadQualityProfilesFailed'), error)
    }
  }

  async function fetchTags() {
    try {
      tagOptions.value = buildTagOptions(await getTags())
    } catch (error) {
      console.error(t('subscription.loadTagsFailed'), error)
    }
  }

  async function fetchSites() {
    const catalogSites = Array.isArray(props.catalogs?.sites) ? props.catalogs.sites : []
    if (catalogSites.length > 0) {
      siteOptions.value = buildSiteOptions(catalogSites)
      return
    }
    try {
      const data = await getResourceSites()
      const sites = Array.isArray(data?.sites) ? data.sites : []
      siteOptions.value = buildSiteOptions(sites)
    } catch (error) {
      console.error(t('subscription.loadSitesFailed'), error)
    }
  }

  function buildSiteOptions(sites) {
    return sites.map((site) => ({
      label: site?.name || site?.description || site?.id,
      value: site?.id,
    })).filter((site) => site.value)
  }

  return {
    loadingDirs,
    directoryOptions,
    filterOptions,
    qualityProfileOptions,
    tagOptions,
    siteOptions,
    fetchDirectories,
    fetchFilterPresets,
    fetchQualityProfiles,
    fetchTags,
    fetchSites,
  }
}
