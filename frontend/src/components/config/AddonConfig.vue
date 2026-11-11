<template>
  <div class="pb-container">
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-container ui-settings-grid-regular">
      <div
        v-for="entry in settingsEntries"
        :key="entry.id"
        :ref="element => setAddonRef(entry.id, element)"
        :data-addon-card="entry.id"
      >
        <component :is="entry.component" :config="props.config" v-bind="entry.props" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, watch } from 'vue'
import { resolveAddonSettings } from '@/addons/registry'

const props = defineProps({
  config: {
    type: Object,
    required: true
  },
  focusAddon: {
    type: String,
    default: '',
  },
  servicesConfig: {
    type: Object,
    required: true,
  },
})

const addonRefs = new Map()
const settingsEntries = computed(() => resolveAddonSettings({ servicesConfig: props.servicesConfig }))

function setAddonRef(id, element) {
  if (element) addonRefs.set(id, element)
  else addonRefs.delete(id)
}

function focusAddonCard(name) {
  const entry = settingsEntries.value.find(item => item.id === name || item.aliases.includes(name))
  const target = entry ? addonRefs.get(entry.id) : null
  if (!target) return
  target.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

watch(
  () => props.focusAddon,
  async (value) => {
    if (!value) return
    await nextTick()
    focusAddonCard(value)
  },
  { immediate: true },
)
</script>
