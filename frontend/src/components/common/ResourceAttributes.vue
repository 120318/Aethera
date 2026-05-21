<template>
  <div class="flex flex-wrap items-center gap-x-inline gap-y-inline" :class="wrapperClass">
    <AppTag
      v-for="(tag, idx) in tags"
      :key="idx"
      :value="tag.value"
      :icon="tag.icon"
      :tone="tag.tone"
      :size="resolvedSize"
      :tooltip="tag.tooltip"
    />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { DEFAULT_RESOURCE_TAGS } from '@/constants/resourceTagTypes'
import { useResourceTags } from '@/composables/useResourceTags'
import AppTag from '@/components/common/AppTag.vue'

const props = defineProps({
  attributes: { type: Object, default: () => ({}) },
  displayAttributes: { type: Object, default: null },
  leadingTags: { type: Array, default: () => [] },
  site: { type: String, default: '' },
  createdAt: { type: [Number, String], default: null },
  size: { type: [Number, String], default: null },
  tagClass: { type: String, default: '' },
  tagSize: { type: String, default: null },
  visibleTags: { type: Array, default: () => DEFAULT_RESOURCE_TAGS },
})

const { getSortedTags } = useResourceTags()

const resolvedSize = computed(() => (props.tagSize === 'large' ? 'md' : 'sm'))
const wrapperClass = computed(() => props.tagClass)

const resourceData = computed(() => ({
  resource: {
    size: formatSize(props.size),
    site: props.site,
    directory: props.attributes?.directory,
    created_at: props.createdAt,
  },
  attributes: {
    ...(props.attributes || {}),
    groups: props.attributes?.groups?.slice(0, 2),
    sources: props.attributes?.sources?.slice(0, 1),
    versions: props.attributes?.versions?.slice(0, 1)
  },
  displayAttributes: props.displayAttributes,
}))

const tags = computed(() => [
  ...props.leadingTags,
  ...getSortedTags(resourceData.value, { visibleTags: props.visibleTags }),
])

function formatSize(bytes) {
  if (bytes === undefined || bytes === null) return ''
  const n = Number(bytes)
  if (isNaN(n)) return String(bytes)
  if (n === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = n
  let i = 0
  while (size >= 1024 && i < units.length - 1) {
    size /= 1024
    i++
  }
  return i === 0 ? `${size} ${units[i]}` : `${size.toFixed(2)} ${units[i]}`
}
</script>
