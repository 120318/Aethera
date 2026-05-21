<template>
  <Card :class="['ui-panel', mediaTypeCardClass]">
    <template #content>
      <div v-if="loading" class="relative">
        <div class="absolute top-item right-item z-10">
          <Skeleton
            class="shadow-badge"
            width="var(--size-control-badge-detail)"
            height="var(--size-control-badge-detail)"
            border-radius="var(--radius-border)"
          />
        </div>
        <div class="media-static-layout">
          <div>
            <div class="media-static-poster-frame aspect-2/3 w-full rounded-container overflow-hidden">
              <Skeleton width="100%" height="100%" />
            </div>
          </div>

          <div class="media-static-copy">
            <div class="flex flex-col h-full gap-item">
              <div class="flex flex-col gap-item">
                <Skeleton width="50%" height="var(--size-placeholder-tiny)" class="mb-inline" />
                <Skeleton width="30%" height="var(--text-title)" />

                <div class="flex gap-item flex-wrap mt-item">
                  <Skeleton
                    width="var(--size-poster-xxs)" height="var(--size-control-icon-sm)"
                    border-radius="var(--radius-container)"
                  />
                  <Skeleton
                    width="var(--size-poster-xs)" height="var(--size-control-icon-sm)"
                    border-radius="var(--radius-container)"
                  />
                  <Skeleton
                    width="var(--size-control-badge-sm)" height="var(--size-control-icon-sm)"
                    border-radius="var(--radius-container)"
                  />
                </div>
              </div>

              <div class="flex-1 min-h-0 flex flex-col gap-item mt-item">
                <Skeleton width="100%" height="var(--text-body)" />
                <Skeleton width="100%" height="var(--text-body)" />
                <Skeleton width="100%" height="var(--text-body)" />
                <Skeleton width="100%" height="var(--text-body)" />
                <Skeleton width="100%" height="var(--text-body)" />
                <Skeleton width="60%" height="var(--text-body)" />
              </div>

              <div class="mt-auto">
                <div class="grid grid-cols-3 md:grid-cols-6 gap-item w-full overflow-hidden">
                  <div v-for="i in 6" :key="i" class="flex flex-col items-center min-w-0">
                    <Skeleton shape="circle" size="var(--size-avatar-lg)" class="mb-item" />
                    <Skeleton width="var(--size-poster-xxs)" height="var(--text-body)" class="mb-inline" />
                    <Skeleton width="var(--size-control-badge-sm)" height="var(--text-small)" />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="relative">
        <div v-if="detail?.poster_path" class="absolute inset-0 overflow-hidden md:hidden opacity-20 -z-10">
          <img :src="proxyImg(detail.poster_path)" class="w-full h-full object-cover blur-xl" :alt="detail?.title" />
          <div class="absolute inset-0 gradient-fade-b"></div>
        </div>

        <div
          v-tooltip.top="ratingTooltip"
          class="absolute top-item right-item z-10 rounded-border shadow-badge flex items-center justify-center w-control-badge-detail h-control-badge-detail font-bold text-heading"
          :class="[getRateColorClass(rating), getRateTextClass(rating)]"
        >
          <span>{{ ratingLabel }}</span>
        </div>

        <div class="media-static-layout">
          <div class="relative group">
            <div class="media-static-poster-frame aspect-2/3 w-full rounded-container overflow-hidden bg-surface">
              <Image
                v-if="detail?.poster_path" :src="proxyImg(detail.poster_path)"
                image-class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-media-image"
                :alt="detail?.title" preview
              >
                <template #error>
                  <div class="w-full h-full flex items-center justify-center text-muted">
                    <span class="text-tiny text-muted">{{ $t('mediaStaticInfo.noPoster') }}</span>
                  </div>
                </template>
              </Image>
              <div v-else class="w-full h-full flex items-center justify-center text-muted">
                <span class="text-tiny text-muted">{{ $t('mediaStaticInfo.noPoster') }}</span>
              </div>
            </div>
          </div>

          <div class="media-static-copy">
            <div ref="metaContainerRef" class="flex flex-col h-full gap-item">
              <div ref="metaHeaderRef" class="flex flex-col gap-item">
                <div class="flex flex-wrap items-center justify-center md:justify-start gap-item text-center md:text-left">
                  <h1 class="inline-flex flex-wrap items-baseline justify-center md:justify-start gap-x-inline gap-y-micro max-w-full min-w-0 leading-tight font-semibold text-heading md:text-hero text-color">
                    <span class="min-w-0 break-words">{{ detail?.title }}</span>
                    <span v-if="detail?.year" class="text-body md:text-title font-normal text-muted shrink-0">({{ detail.year }})</span>
                  </h1>

                  <div
                    v-if="vendorLinks.length"
                    class="flex items-center gap-item"
                  >
                    <a
                      v-for="vendor in vendorLinks" :key="vendor.key" :href="vendor.url" target="_blank"
                      class="transform transition-transform hover:scale-media-image" :title="vendor.name"
                    >
                      <Image
                        v-if="vendor.logo" :src="vendor.logo"
                        :alt="vendor.name"
                        image-class="w-control-icon-sm h-control-icon-sm object-contain"
                      />
                      <AppTag v-else :label="vendor.name" />
                    </a>
                  </div>

                  <Button
                    v-if="canEditExternalMapping"
                    v-tooltip.top="$t('mediaDetail.correctMedia')"
                    icon="pi pi-hammer"
                    text
                    rounded
                    size="small"
                    :loading="externalMappingLoading"
                    class="media-mapping-trigger"
                    :aria-label="$t('mediaStaticInfo.correctExternalMapping')"
                    @click="$emit('edit-external-mapping')"
                  />
                </div>

                <div
                  v-if="detail?.original_title && detail.original_title !== detail.title"
                  class="text-body md:text-subtitle font-normal text-center md:text-left"
                >
                  {{ $t('mediaStaticInfo.originalTitle', { title: detail.original_title }) }}
                </div>

                <div class="flex flex-wrap gap-inline items-center justify-center md:justify-start">
                  <template v-for="tag in detailTags" :key="tag.key">
                    <AppTag
                      :label="tag.label"
                      :icon="tag.icon"
                      :tone="tag.tone || 'default'"
                      size="md"
                    />
                    <Select
                      v-if="tag.key === 'media-type' && seasonOptions.length > 0"
                      :model-value="selectedSeasonNumber"
                      :options="seasonOptions"
                      option-label="label"
                      option-value="value"
                      class="media-season-select"
                      :pt="seasonSelectPt"
                      @update:model-value="handleSeasonSelect"
                    />
                  </template>
                </div>
              </div>

              <div ref="overviewSectionRef" class="flex-1 min-h-0 relative overview-section">
                <div
                  v-if="detail?.overview"
                  ref="overviewTextRef"
                  class="text-body font-normal text-muted leading-relaxed overflow-hidden transition-all duration-300"
                  :class="{ 'line-clamp-none': summaryExpanded, 'line-clamp-4': !summaryExpanded && showSummaryToggle }"
                >
                  {{ detail.overview }}
                </div>
                <div v-if="showSummaryToggle" class="meta-tags-container">
                  <Button
                    :label="summaryExpanded ? $t('mediaStaticInfo.collapse') : $t('mediaStaticInfo.expandAll')" link size="small"
                    class="p-none" @click="toggleSummary"
                  />
                </div>
              </div>

              <div ref="metaFooterRef" class="mt-auto">
                <div
                  v-if="displayActors.length"
                  class="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-x-item gap-y-container w-full"
                >
                  <div
                    v-for="actor in displayActors" :key="'actor-' + actor.id"
                    class="flex flex-col items-center text-center group min-w-0"
                  >
                    <div
                      class="relative w-avatar-lg h-avatar-lg mb-item shadow-none transition-transform group-hover:scale-media-image shrink-0 border-none overflow-hidden rounded-full"
                    >
                      <Image
                        v-if="actor.avatar?.large" :src="proxyImg(actor.avatar.large)"
                        class="w-full h-full"
                        image-class="w-full h-full object-cover" :alt="actor.name" preview
                      />
                      <div
                        v-else
                        class="w-full h-full flex items-center justify-center bg-emphasis rounded-full text-title font-bold text-muted"
                      >
                        {{ actor.name?.charAt?.(0) }}
                      </div>
                    </div>
                    <div class="w-full max-w-avatar-lg overflow-hidden px-inline">
                      <div
                        v-tooltip.top="actor.name || ''"
                        class="text-body font-medium line-clamp-2 break-words whitespace-normal leading-snug w-full"
                      >{{
                        actor.name
                      }}</div>
                      <div
                        v-if="actor.character"
                        v-tooltip.top="$t('mediaStaticInfo.characterTooltip', { character: formatCharacter(actor.character) })"
                        class="text-caption text-muted italic line-clamp-2 break-words whitespace-normal leading-snug w-full"
                      >
                        {{ $t('mediaStaticInfo.character', { character: formatCharacter(actor.character) }) }}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </Card>

  <div v-if="loading && detail?.overview" class="fixed -z-50 opacity-0 pointer-events-none" aria-hidden="true">
    <div ref="prerenderTextRef">
      <p>{{ detail.overview }}</p>
    </div>
  </div>
</template>

<script setup>
import Card from 'primevue/card'
import Skeleton from 'primevue/skeleton'
import Button from 'primevue/button'
import Image from 'primevue/image'
import Select from 'primevue/select'
import AppTag from '@/components/common/AppTag.vue'
import { useMediaStaticInfo } from '@/composables/useMediaStaticInfo'

const emit = defineEmits(['edit-external-mapping', 'season-change'])

const props = defineProps({
  mediaId: {
    type: String,
    default: ''
  },
  detail: {
    type: Object,
    default: () => ({})
  },
  loading: {
    type: Boolean,
    default: false
  },
  canEditExternalMapping: {
    type: Boolean,
    default: true
  },
  externalMappingLoading: {
    type: Boolean,
    default: false
  },
  selectedSeasonNumber: {
    type: Number,
    default: null
  },
  seasonOptions: {
    type: Array,
    default: () => []
  }
})

const {
  summaryExpanded,
  showSummaryToggle,
  overviewTextRef,
  mediaTypeCardClass,
  vendorLinks,
  rating,
  ratingLabel,
  ratingTooltip,
  displayActors,
  detailTags,
  proxyImg,
  getRateColorClass,
  getRateTextClass,
  formatCharacter,
  toggleSummary,
} = useMediaStaticInfo(props)

const seasonSelectPt = {
  root: 'ui-tag ui-tag-accent ui-tag-md ui-tag-interactive media-season-select-root',
  label: 'media-season-select-label',
  dropdown: 'media-season-select-dropdown',
}

function handleSeasonSelect(value) {
  emit('season-change', value)
}
</script>

<style scoped>
.media-static-layout {
  display: grid;
  gap: var(--spacing-container);
  grid-template-columns: minmax(0, 1fr);
}

.media-static-poster-frame {
  max-width: var(--size-poster-lg);
  margin-inline: auto;
}

.media-static-copy {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.media-mapping-trigger {
  color: var(--text-muted);
}

.media-mapping-trigger:hover {
  color: var(--primary-color);
}

@media (min-width: 768px) {
  .media-static-layout {
    grid-template-columns: minmax(var(--size-poster-sm), var(--size-poster-lg)) minmax(0, 1fr);
  }

  .media-static-poster-frame {
    max-width: none;
    margin-inline: 0;
  }

}

:deep(.media-season-select-root) {
  border: 0;
  box-shadow: none;
  color: var(--accent-primary);
  padding-inline: var(--spacing-item);
  padding-block: var(--spacing-tight);
  min-height: 0;
  gap: var(--spacing-inline);
}

:deep(.media-season-select-root:not(.p-disabled).p-focus) {
  box-shadow: none;
}

:deep(.media-season-select-label) {
  color: inherit;
  font-size: inherit;
  font-weight: inherit;
  padding: 0;
  line-height: 1.2;
}

:deep(.media-season-select-dropdown) {
  color: inherit;
  width: auto;
  min-width: 0;
  padding: 0;
}

:deep(.media-season-select-dropdown svg),
:deep(.media-season-select-dropdown .p-icon),
:deep(.media-season-select-dropdown .pi) {
  color: inherit;
}

</style>
