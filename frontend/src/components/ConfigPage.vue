<template>
  <section class="ui-section w-full max-w-layout">
    <div class="ui-page-header">
      <div class="flex flex-col gap-item">
        <h1 class="text-heading font-semibold text-color">{{ $t('settings.title') }}</h1>
        <p class="text-muted text-caption">{{ $t('settings.description') }}</p>
      </div>
    </div>

    <AppTabs
      v-model="activeTab"
      :tabs="tabs"
      :content-body-class="contentBodyClass"
    >
      <ConfigTabSkeleton v-if="loading" :variant="activeSkeletonVariant" />

      <div v-else-if="activeTab === 'downloader'" class="flex flex-col gap-block">
        <DownloaderConfig :config="downloaderConfig" :apply-config-patch="patchDownloadersConfig" />
      </div>
      <div v-else-if="activeTab === 'indexer'" class="flex flex-col gap-container">
        <p class="text-caption text-muted m-none">{{ $t('settings.indexerSortHint') }}</p>
        <IndexerConfig :config="indexerConfig" :apply-config-patch="patchIndexersConfig" />
      </div>
      <div v-else-if="activeTab === 'mediaserver'" class="flex flex-col gap-block">
        <MediaServerConfig :config="mediaServerConfig" :apply-config-patch="patchMediaServersConfig" />
      </div>
      <div v-else-if="activeTab === 'directory'" class="flex flex-col gap-block">
        <DirectoryConfig :config="directoryConfig" :apply-config-patch="patchDirectoriesConfig" />
      </div>
      <div v-else-if="activeTab === 'naming'" class="flex flex-col gap-block">
        <NamingTemplateConfig :config="namingConfig" :apply-config-patch="patchNamingConfig" />
      </div>
      <div v-else-if="activeTab === 'filter'" class="flex flex-col gap-block">
        <FilterConfig />
      </div>
      <div v-else-if="activeTab === 'tag'" class="flex flex-col gap-block">
        <TagConfig />
      </div>
      <div v-else-if="activeTab === 'quality'" class="flex flex-col gap-block">
        <QualityProfileConfig />
      </div>
      <div v-else-if="activeTab === 'addon'" class="flex flex-col gap-block">
        <AddonConfig :config="addonConfig" :services-config="metadataConfig" :focus-addon="focusedAddon" />
      </div>
      <div v-else-if="activeTab === 'metadata'" class="flex flex-col gap-block">
        <MetadataConfig :config="metadataConfig" :apply-config-patch="patchServicesConfig" />
      </div>
      <div v-else-if="activeTab === 'system'" class="flex flex-col gap-block">
        <SystemConfig :config="systemConfig" :apply-config-patch="patchSystemConfig" />
      </div>
    </AppTabs>
  </section>
</template>

<script setup>
import { computed, ref, watch, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import AppTabs from "@/components/common/AppTabs.vue";
import ConfigTabSkeleton from "@/components/common/ConfigTabSkeleton.vue";
import { useAddonsConfig } from "@/composables/useAddonsConfig";
import { useServicesConfig } from "@/composables/useServicesConfig";
import { useSystemSettings } from "@/composables/useSystemSettings";
import { useDownloadersTabConfig } from "@/composables/useDownloadersTabConfig";
import { useIndexersTabConfig } from "@/composables/useIndexersTabConfig";
import { useMediaServersTabConfig } from "@/composables/useMediaServersTabConfig";
import { useDirectoriesTabConfig } from "@/composables/useDirectoriesTabConfig";
import { useNamingTabConfig } from "@/composables/useNamingTabConfig";

import DownloaderConfig from "./config/DownloaderConfig.vue";
import IndexerConfig from "./config/IndexerConfig.vue";
import MediaServerConfig from "./config/MediaServerConfig.vue";
import DirectoryConfig from "./config/DirectoryConfig.vue";
import NamingTemplateConfig from "./config/NamingTemplateConfig.vue";
import AddonConfig from "./config/AddonConfig.vue";
import MetadataConfig from "./config/MetadataConfig.vue";
import SystemConfig from "./config/SystemConfig.vue";
import FilterConfig from "./config/FilterConfig.vue";
import TagConfig from "./config/TagConfig.vue";
import QualityProfileConfig from "./config/QualityProfileConfig.vue";

const route = useRoute();
const router = useRouter();
const { t } = useI18n();
const { config: downloaderConfig, loading: downloaderLoading, fetchConfig: fetchDownloadersConfig, patchConfig: patchDownloadersConfigRaw } = useDownloadersTabConfig();
const { config: indexerConfig, loading: indexerLoading, fetchConfig: fetchIndexersConfig, patchConfig: patchIndexersConfig } = useIndexersTabConfig();
const { config: mediaServerConfig, loading: mediaServerLoading, fetchConfig: fetchMediaServersConfig, patchConfig: patchMediaServersConfigRaw } = useMediaServersTabConfig();
const { config: directoryConfig, loading: directoryLoading, fetchConfig: fetchDirectoriesConfig, patchConfig: patchDirectoriesConfigRaw, invalidate: invalidateDirectoriesTab } = useDirectoriesTabConfig();
const { config: namingConfig, loading: namingLoading, fetchConfig: fetchNamingConfig, patchConfig: patchNamingConfigRaw } = useNamingTabConfig();
const { systemConfig, loading: systemLoading, fetchSystemSettings, patchSystemConfig } = useSystemSettings();
const { services, loading: servicesLoading, fetchServicesConfig, patchServicesConfig } = useServicesConfig();
const { addons, loading: addonsLoading, fetchAddonsConfig } = useAddonsConfig();

const tabDefinitions = [
  { labelKey: "settings.tabs.downloader", value: "downloader" },
  { labelKey: "settings.tabs.indexer", value: "indexer" },
  { labelKey: "settings.tabs.mediaServer", value: "mediaserver" },
  { labelKey: "settings.tabs.directory", value: "directory" },
  { labelKey: "settings.tabs.naming", value: "naming" },
  { labelKey: "settings.tabs.tag", value: "tag" },
  { labelKey: "settings.tabs.quality", value: "quality" },
  { labelKey: "settings.tabs.filter", value: "filter" },
  { labelKey: "settings.tabs.addon", value: "addon" },
  { labelKey: "settings.tabs.metadata", value: "metadata" },
  { labelKey: "settings.tabs.system", value: "system" },
];

const tabs = computed(() => tabDefinitions.map((tab) => ({
  label: t(tab.labelKey),
  value: tab.value,
})));

const validTabs = new Set(tabDefinitions.map((tab) => tab.value));

const hashToTab = (hash) => {
  if (!hash) return null;
  const value = hash.replace(/^#/, "");
  return validTabs.has(value) ? value : null;
};

const activeTab = ref(hashToTab(route.hash) || "downloader");

const contentBodyClass = computed(() => (
  'flex flex-col gap-block min-h-settings-tab-content'
));

const loading = computed(() => {
  if (activeTab.value === 'downloader') return downloaderLoading.value
  if (activeTab.value === 'indexer') return indexerLoading.value
  if (activeTab.value === 'mediaserver') return mediaServerLoading.value
  if (activeTab.value === 'directory') return directoryLoading.value
  if (activeTab.value === 'naming') return namingLoading.value
  if (activeTab.value === 'addon') {
    return addonsLoading.value
  }
  if (activeTab.value === 'metadata') {
    return servicesLoading.value
  }
  if (activeTab.value === 'system') {
    return systemLoading.value
  }
  return false
})

const focusedAddon = computed(() => (
  activeTab.value === 'addon' ? String(route.query.focus || '') : ''
))

const addonConfig = computed(() => ({ addons }))
const metadataConfig = computed(() => services)

function patchDownloadersConfig(patch) {
  patchDownloadersConfigRaw(patch)
  invalidateDirectoriesTab()
}

function patchMediaServersConfig(patch) {
  patchMediaServersConfigRaw(patch)
  invalidateDirectoriesTab()
}

function patchDirectoriesConfig(patch) {
  patchDirectoriesConfigRaw(patch)
}

function patchNamingConfig(patch) {
  patchNamingConfigRaw(patch)
  invalidateDirectoriesTab()
}

const activeSkeletonVariant = computed(() => {
  const variantMap = {
    downloader: 'cards-regular',
    indexer: 'cards-regular',
    mediaserver: 'cards-compact',
    directory: 'cards-tall',
    naming: 'cards-regular',
    tag: 'cards-regular',
    quality: 'cards-tall',
    filter: 'cards-tall',
    addon: 'cards-regular',
    metadata: 'stacked-dense',
    system: 'stacked-dense',
  }

  return variantMap[activeTab.value] || 'cards-regular'
})

watch(
  () => route.hash,
  (newHash) => {
    const nextTab = hashToTab(newHash);
    if (nextTab && nextTab !== activeTab.value) {
      activeTab.value = nextTab;
    }
  }
);

watch(activeTab, (newTab) => {
  const desiredHash = `#${newTab}`;
  if (route.hash !== desiredHash) {
    router.replace({
      hash: desiredHash,
      query: route.query,
    });
  }
  ensureTabData(newTab)
}, { immediate: true });

function ensureTabData(tab) {
  if (tab === 'downloader') return fetchDownloadersConfig()
  if (tab === 'indexer') return fetchIndexersConfig()
  if (tab === 'mediaserver') return fetchMediaServersConfig()
  if (tab === 'directory') return fetchDirectoriesConfig()
  if (tab === 'naming') return fetchNamingConfig()
  if (tab === 'addon') return Promise.all([fetchAddonsConfig(), fetchServicesConfig()])
  if (tab === 'metadata') return fetchServicesConfig()
  if (tab === 'system') return fetchSystemSettings()
}

onMounted(() => {
  if (!route.hash) {
    router.replace({
      hash: `#${activeTab.value}`,
      query: route.query,
    });
  }
});
</script>
