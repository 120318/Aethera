<template>
  <ConfigDialog
    :model-value="visible"
    :title="title"
    size="lg"
    :intro="$t('settings.indexer.sitesIntro')"
    @update:model-value="$emit('update:visible', $event)"
  >
    <div class="ui-dialog-section min-h-placeholder-md">
      <div
        v-if="healthLoading || sitesLoading"
        class="py-item text-small font-muted text-muted"
      >
        {{ $t('common.loading') }}
      </div>
      <div
        v-else-if="sites.length === 0"
        class="py-item text-small font-muted text-muted"
      >
        {{ $t('settings.indexer.noSites') }}
      </div>
      <div v-else>
        <div
          v-if="sitesError"
          class="mb-item text-tiny text-status-warn"
        >
          {{ $t('settings.indexer.siteListWarning', { message: sitesError }) }}
        </div>
        <div class="ui-dialog-grid">
          <div
            v-for="site in sites"
            :key="`${indexerId}-${site.site_id}`"
            class="ui-surface-item"
          >
            <div class="flex items-start justify-between gap-item">
              <div class="flex min-w-0 flex-col gap-inline">
                <span class="text-small font-medium">{{
                  site.site_name || site.description || site.site_id
                }}</span>
              </div>
              <div class="flex shrink-0 items-center gap-inline">
                <AppTag
                  :value="site.is_live ? $t('settings.indexer.online') : $t('settings.indexer.offline')"
                  :tone="site.is_live ? 'accent' : 'neutral'"
                />
                <AppTag
                  :value="getStatusLabel(site.status)"
                  :tone="getStatusTone(site.status)"
                />
              </div>
            </div>
            <div class="flex flex-col gap-inline text-tiny font-muted text-muted">
              <span>{{ $t('settings.indexer.consecutiveFailures', { count: site.consecutive_failures || 0 }) }}</span>
              <span>{{ $t('settings.indexer.lastChecked', { time: formatTime(site.checked_at) }) }}</span>
            </div>
            <IndexerSiteSwitchPanel
              :site="site"
              :site-setting-disabled="isSiteSettingDisabled(site)"
              @update-site-setting="(key, value) => $emit('update-site-setting', site, key, value)"
              @update-media-type="(mediaType, value) => $emit('update-media-type', site, mediaType, value)"
              @update-search-mode="(mode, value) => $emit('update-search-mode', site, mode, value)"
            />
          </div>
        </div>
      </div>
    </div>
  </ConfigDialog>
</template>

<script setup>
import AppTag from '@/components/common/AppTag.vue'
import ConfigDialog from '@/components/common/ConfigDialog.vue'
import IndexerSiteSwitchPanel from '@/components/config/IndexerSiteSwitchPanel.vue'

defineProps({
  visible: { type: Boolean, default: false },
  title: { type: String, default: '' },
  indexerId: { type: String, default: '' },
  sites: { type: Array, default: () => [] },
  sitesError: { type: String, default: '' },
  healthLoading: { type: Boolean, default: false },
  sitesLoading: { type: Boolean, default: false },
  getStatusLabel: { type: Function, required: true },
  getStatusTone: { type: Function, required: true },
  formatTime: { type: Function, required: true },
  isSiteSettingDisabled: { type: Function, required: true },
})

defineEmits([
  'update:visible',
  'update-site-setting',
  'update-media-type',
  'update-search-mode',
])
</script>
