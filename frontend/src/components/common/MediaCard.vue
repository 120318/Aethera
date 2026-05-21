<template>
  <component
    :is="wrapperComponent"
    v-bind="wrapperProps"
    class="block h-full rounded-container no-underline text-inherit focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
    @click="handleWrapperClick"
  >
    <Card
      class="ui-card relative h-full group overflow-visible transition-shadow duration-200 hover:shadow-content"
      :class="[mediaTypeCardClass, interactiveCardClass]"
      :pt="cardPt"
    >
      <template #content>
        <div class="flex flex-row gap-container h-full relative">

          <div :class="['relative shrink-0', posterWidthClass]">
            <div
              class="aspect-2/3 w-full rounded-container overflow-hidden bg-emphasis border border-separator-subtle relative"
            >
              <Image
                v-if="posterUrl" :src="proxyImg(posterUrl)"
                image-class="w-full h-full object-cover transition-transform duration-700 ease-in-out group-hover:scale-media-image"
                :alt="media.title"
              >
                <template #error>
                  <div class="w-full h-full flex items-center justify-center text-muted">
                    <i class="pi pi-image text-heading"></i>
                  </div>
                </template>
              </Image>
              <div v-else class="w-full h-full flex items-center justify-center text-muted bg-placeholder">
                <i class="pi pi-image text-heading"></i>
              </div>

            </div>
          </div>

          <div v-if="showRatingBadge" class="absolute top-none right-0 z-10 group/rating">
            <div
              class="rounded-border shadow-badge flex items-center justify-center w-control-badge-sm h-control-badge-sm font-bold text-body"
              :class="[getRateColorClass(rating), getRateTextClass(rating)]"
            >
              <span>{{ ratingLabel }}</span>
            </div>
            <div
              v-if="ratingCount"
              class="absolute bottom-full left-1/2 -translate-x-1/2 mb-inline bg-placeholder px-item py-inline text-body font-medium text-muted rounded-item whitespace-nowrap opacity-0 pointer-events-none transition-opacity group-hover/rating:opacity-100 group-focus-within/rating:opacity-100"
            >
              {{ ratingTooltip }}
            </div>
          </div>

          <div class="flex-1 flex flex-col min-w-0 py-inline pl-inline pr-block relative">
            <div class="mb-item">
              <h3
                :class="[
                  'text-title font-semibold leading-tight truncate',
                  isViewed ? 'text-color' : 'text-primary-emphasis'
                ]"
                :title="media.title"
              >
                {{ media.title }}
                <span v-if="media.year" class="text-subtitle font-normal text-muted">({{ media.year }})</span>
              </h3>
            </div>

            <div class="flex flex-col gap-inline mb-item">
              <div v-if="subtitleLine1" :class="subtitleLine1Class">
                {{ subtitleLine1 }}
              </div>

              <div v-if="subtitleLine2" :class="subtitleLine2Class">
                {{ subtitleLine2 }}
              </div>
            </div>

            <div class="flex-1 min-h-0 relative mt-auto">
              <div
                v-if="overview"
                class="text-caption text-muted leading-relaxed"
                :class="{ 'line-clamp-none': summaryExpanded, 'line-clamp-3': !summaryExpanded }"
                @click.stop="toggleSummary"
              >
                {{ overview }}
              </div>
            </div>
          </div>
        </div>

        <div
          v-if="mediaTypeInfo"
          class="absolute right-0 bottom-0 inline-flex items-center px-item py-inline rounded-tl-border text-tiny font-medium border border-separator shadow-content"
          :class="mediaTypeBadgeClass"
        >
          <span>{{ mediaTypeInfo.label }}</span>
        </div>

        <Button
          v-if="showDelete" icon="pi pi-trash" severity="danger" text rounded :aria-label="t('common.delete')"
          class="!absolute top-item right-item z-20 opacity-0 group-hover:opacity-100 transition-opacity bg-surface border border-separator shadow-content scale-90"
          @click.stop="emit('delete', props.media)"
        />
      </template>
    </Card>
  </component>
</template>


<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'
import Card from 'primevue/card'
import Image from 'primevue/image'
import Button from 'primevue/button'
import { formatCount } from '@/utils/formatters'
import { resolveMediaImageUrl } from '@/utils/mediaImage'

const props = defineProps({
  media: {
    type: Object,
    required: true
  },
  posterWidthClass: {
    type: String,
    default: 'w-poster-xxs sm:w-poster-tiny'
  },
  to: {
    type: [String, Object],
    default: null
  },
  showDelete: {
    type: Boolean,
    default: false
  },
  variant: {
    type: String,
    default: 'default'
  },
  showRating: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['click', 'delete'])
const { t } = useI18n()
const cardPt = {
  body: 'p-container h-full',
  content: 'p-none h-full',
}

const summaryExpanded = ref(false)

const normalizedMediaId = computed(() => {
  const v = props.media?.media_id || props.media?.id
  if (!v) return null
  if (typeof v === 'string') return v
  if (typeof v === 'object') {
    const provider = v.provider?.value || v.provider
    const mediaType = v.media_type?.value || v.media_type || v.mediaType
    const id = v.id
    if (provider && mediaType && id) return `${provider}:${mediaType}:${id}`
  }
  const s = String(v)
  return s && s !== '[object Object]' ? s : null
})

const isViewed = computed(() => {
  if (typeof props.media?.viewed === 'boolean') return props.media.viewed
  if (!normalizedMediaId.value) return false
  return true
})

// Computed properties for normalizing data
const posterUrl = computed(() => props.media.poster_path || null)
const rating = computed(() => {
  const raw = props.media.vote_average
  const num = typeof raw === 'number' ? raw : parseFloat(raw)
  return Number.isFinite(num) && num > 0 ? num : null
})
const ratingCount = computed(() => props.media.vote_count || props.media.rating_count)
const showRatingBadge = computed(() => props.showRating)
const ratingLabel = computed(() => {
  const num = parseFloat(rating.value)
  return Number.isFinite(num) ? num.toFixed(1) : '?'
})
const ratingSourceLabel = computed(() => {
  if (props.media?.source === 'tmdb' || props.media?.primary_metadata_source === 'tmdb') return 'TMDB'
  return t('mediaCard.ratingSource.douban')
})
const ratingTooltip = computed(() => t('mediaCard.ratingTooltip', {
  source: ratingSourceLabel.value,
  count: formatCount(ratingCount.value),
}))
const overview = computed(() => props.media.overview || props.media.description)

const subtitleParts = computed(() => (
  String(props.media.subtitle || '')
    .split(' / ')
    .map((part) => part.trim())
    .filter(Boolean)
))
const subtitleLine1 = computed(() => props.media.subtitle_line1 || (subtitleParts.value.length >= 2 ? subtitleParts.value.slice(0, 2).join(' / ') : null))
const subtitleLine2 = computed(() => {
  if (props.media.subtitle_line2) return props.media.subtitle_line2
  if (props.media.subtitle_line1) return null
  return subtitleParts.value.length > 2 ? subtitleParts.value.slice(2).join(' / ') : null
})
const isTodayUpdateVariant = computed(() => props.variant === 'today-update')
const subtitleLine1Class = computed(() => (
  isTodayUpdateVariant.value
    ? 'text-body font-semibold text-primary-emphasis truncate'
    : 'text-body text-muted truncate'
))
const subtitleLine2Class = computed(() => (
  isTodayUpdateVariant.value
    ? 'text-body text-muted truncate'
    : 'text-body text-muted truncate'
))

const mediaTypeInfo = computed(() => {
  const type = props.media.media_type || props.media.type
  if (type === 'movie') return { label: t('mediaManagement.mediaType.movie'), icon: 'pi pi-video' }
  if (type === 'tv') return { label: t('mediaManagement.mediaType.tv'), icon: 'pi pi-desktop' }
  return null
})

const mediaTypeCardClass = computed(() => {
  const type = props.media.media_type || props.media.type
  if (type === 'tv') return 'media-card-tv'
  if (type === 'movie') return 'media-card-movie'
  return ''
})

const mediaTypeBadgeClass = computed(() => {
  const type = props.media.media_type || props.media.type
  if (type === 'tv') return 'bg-surface text-muted'
  if (type === 'movie') return 'bg-surface text-muted'
  return 'bg-surface text-muted'
})

const wrapperComponent = computed(() => (props.to ? RouterLink : 'div'))

const wrapperProps = computed(() => (props.to ? { to: props.to } : {}))

const interactiveCardClass = computed(() => (
  props.to ? 'cursor-pointer' : ''
))

// Helper functions
function proxyImg(url) {
  return resolveMediaImageUrl(url)
}

function getRateColorClass(rate) {
  const num = parseFloat(rate)
  if (isNaN(num)) return "bg-rate-none"
  if (num >= 7.5) return "bg-rate-high"
  if (num >= 6.0) return "bg-rate-medium"
  return "bg-rate-low"
}

function getRateTextClass(rate) {
  const num = parseFloat(rate)
  if (isNaN(num) || num < 6.0) return "text-white"
  return "text-black"
}

function toggleSummary() {
  summaryExpanded.value = !summaryExpanded.value
}

// Event handlers
function handleWrapperClick() {
  if (!props.to) {
    emit('click', props.media)
  }
}
</script>

<style scoped>
.media-card-movie {
  --card-surface-bg: var(--surface-media-card-movie);
}

.media-card-tv {
  --card-surface-bg: var(--surface-media-card-tv);
}
</style>
