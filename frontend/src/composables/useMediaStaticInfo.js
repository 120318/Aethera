import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  buildDetailTags,
  buildVendorLinks,
  formatCharacter,
  getRateColorClass,
  getRateTextClass,
  proxyMediaImage,
  resolveMediaTypeCardClass,
  resolveMediaTypeInfo,
} from '@/composables/mediaStaticInfoSupport'
import { parseMediaId } from '@/composables/mediaIdentitySupport'
import { formatCount } from '@/utils/formatters'

export function useMediaStaticInfo(props) {
  const { t } = useI18n()
  const summaryExpanded = ref(false)
  const showSummaryToggle = ref(false)
  const overviewTextRef = ref(null)
  let resizeObserver = null

  const fallbackMediaType = computed(() => {
    return parseMediaId(props.mediaId)?.media_type || ''
  })

  const resolvedMediaType = computed(() => (
    props.detail?.media_type || props.detail?.type || fallbackMediaType.value
  ))

  const mediaTypeInfo = computed(() => resolveMediaTypeInfo(resolvedMediaType.value, t))
  const mediaTypeCardClass = computed(() => resolveMediaTypeCardClass(resolvedMediaType.value))
  const vendorLinks = computed(() => buildVendorLinks(props.detail))
  const rating = computed(() => {
    if (props.detail?.douban_id && props.detail?.rating_source !== 'douban') return null
    const raw = props.detail?.vote_average
    const num = typeof raw === 'number' ? raw : parseFloat(raw)
    return Number.isFinite(num) && num > 0 ? num : null
  })
  const ratingLabel = computed(() => (
    rating.value != null ? rating.value.toFixed(1) : '?'
  ))
  const ratingSourceLabel = computed(() => {
    if (props.detail?.rating_source === 'douban') return t('mediaCard.ratingSource.douban')
    return 'TMDB'
  })
  const ratingTooltip = computed(() => (
    props.detail?.rating_count
      ? t('mediaCard.ratingTooltip', {
        source: ratingSourceLabel.value,
        count: formatCount(props.detail.rating_count),
      })
      : t('mediaStaticInfo.rating', { source: ratingSourceLabel.value })
  ))

  const displayActors = computed(() => (props.detail?.actors || []).slice(0, 6))

  const detailTags = computed(() => buildDetailTags(props.detail, mediaTypeInfo.value, t))

  function toggleSummary() {
    summaryExpanded.value = !summaryExpanded.value
    nextTick(() => {
      checkOverflow()
    })
  }

  function checkOverflow() {
    const el = overviewTextRef.value
    if (!el) return

    if (summaryExpanded.value) {
      showSummaryToggle.value = true
      return
    }

    showSummaryToggle.value = el.scrollHeight > el.clientHeight
  }

  watch(() => props.detail?.overview, () => {
    summaryExpanded.value = false
    nextTick(() => {
      if (resizeObserver) {
        resizeObserver.disconnect()
        if (overviewTextRef.value) {
          resizeObserver.observe(overviewTextRef.value)
        }
      }
      checkOverflow()
    })
  })

  onMounted(() => {
    resizeObserver = new ResizeObserver(() => {
      checkOverflow()
    })
    if (overviewTextRef.value) {
      resizeObserver.observe(overviewTextRef.value)
    }
    window.setTimeout(checkOverflow, 100)
  })

  onBeforeUnmount(() => {
    if (resizeObserver) {
      resizeObserver.disconnect()
      resizeObserver = null
    }
  })

  return {
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
    proxyImg: proxyMediaImage,
    getRateColorClass,
    getRateTextClass,
    formatCharacter,
    toggleSummary,
    formatCount,
  }
}
