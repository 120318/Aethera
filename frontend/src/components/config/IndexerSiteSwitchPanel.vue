<template>
  <div class="mt-item flex flex-col gap-item">
    <section class="flex flex-col gap-inline rounded-md bg-surface-subtle">
      <div class="grid grid-cols-1 gap-inline sm:grid-cols-3">
        <span class="text-tiny font-semibold text-muted">{{ $t('settings.indexerSite.siteStatus') }}</span>
        <span class="text-tiny font-semibold text-muted sm:col-span-2">{{ $t('settings.indexerSite.mediaTypes') }}</span>
      </div>
      <div class="grid grid-cols-1 gap-item sm:grid-cols-3">
        <div class="flex items-center justify-start gap-inline">
          <ToggleSwitch
            :model-value="site.settings.enabled"
            :disabled="siteSettingDisabled"
            @update:model-value="(value) => emit('updateSiteSetting', 'enabled', value)"
          />
          <span class="text-caption font-medium text-color">{{ $t('settings.indexerSite.enabled') }}</span>
        </div>

        <div class="flex items-center justify-start gap-inline">
          <ToggleSwitch
            :model-value="site.effective.supports_movie"
            :disabled="isMediaDisabled('movie')"
            @update:model-value="(value) => emit('updateMediaType', 'movie', value)"
          />
          <span class="text-caption font-medium text-color">{{ $t('settings.indexerSite.movie') }}</span>
        </div>

        <div class="flex items-center justify-start gap-inline">
          <ToggleSwitch
            :model-value="site.effective.supports_tv"
            :disabled="isMediaDisabled('tv')"
            @update:model-value="(value) => emit('updateMediaType', 'tv', value)"
          />
          <span class="text-caption font-medium text-color">{{ $t('settings.indexerSite.tv') }}</span>
        </div>
      </div>
    </section>

    <section class="flex flex-col gap-inline rounded-md bg-surface-subtle">
      <span class="text-tiny font-semibold text-muted">{{ $t('settings.indexerSite.searchModes') }}</span>
      <div class="grid grid-cols-1 gap-item sm:grid-cols-3">
        <div
          v-for="mode in searchModes"
          :key="mode.key"
          class="flex items-center justify-start gap-inline"
        >
          <ToggleSwitch
            :model-value="site.effective[mode.effectiveKey]"
            :disabled="isSearchDisabled(mode.key)"
            @update:model-value="(value) => emit('updateSearchMode', mode.key, value)"
          />
          <span
            class="text-caption font-medium"
            :class="getSearchModeTextClass(mode.key)"
          >{{ mode.label }}</span>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import ToggleSwitch from 'primevue/toggleswitch'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  isMediaTypeToggleDisabled,
  isSearchToggleDisabled,
} from '@/composables/useIndexerSiteSettings'

const props = defineProps({
  site: {
    type: Object,
    required: true,
  },
  siteSettingDisabled: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['updateSiteSetting', 'updateMediaType', 'updateSearchMode'])
const { t } = useI18n()

const searchModes = computed(() => [
  { key: 'douban', label: t('settings.indexerSite.doubanId'), effectiveKey: 'use_douban' },
  { key: 'imdb', label: t('settings.indexerSite.imdbId'), effectiveKey: 'use_imdb' },
  { key: 'title', label: t('settings.indexerSite.title'), effectiveKey: 'use_title' },
])

function isMediaDisabled(mediaType) {
  return isMediaTypeToggleDisabled(props.site, mediaType, props.siteSettingDisabled)
}

function isSearchDisabled(mode) {
  return isSearchToggleDisabled(props.site, mode, props.siteSettingDisabled)
}

function getSearchModeTextClass(mode) {
  if (mode === 'title' && !props.site.capabilities.supports_title) return 'text-muted'
  if (mode === 'imdb' && !props.site.capabilities.supports_imdb) return 'text-muted'
  if (mode === 'douban' && !props.site.capabilities.supports_douban) return 'text-muted'
  return 'text-color'
}
</script>
