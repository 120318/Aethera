<template>
  <div class="flex flex-col w-full min-h-0">
    <!-- Chrome-style Tabs Header -->
    <div
      role="tablist"
      class="w-full flex items-end bg-emphasis px-0 pt-0 select-none rounded-t-border relative z-10 border-t border-l border-r border-separator"
      :class="headerClass"
    >
      <div
        ref="tabScrollerRef"
        class="app-tabs-scroll flex items-end gap-inline flex-1 min-w-0 overflow-x-auto overflow-y-hidden relative px-inline"
        :class="{ 'app-tabs-scroll--fit-mobile': fitMobile }"
      >
        <!-- Sliding Indicator -->
        <div
          class="absolute bottom-0 h-tabs bg-surface rounded-t-tab transition-tab-indicator z-20 shadow-tab overflow-visible"
          :style="indicatorStyle"
        >
          <!-- Left Wing SVG -->
          <svg
            class="tab-wing tab-wing-left fill-surface pointer-events-none"
            viewBox="0 0 10 10" xmlns="http://www.w3.org/2000/svg" shape-rendering="geometricPrecision"
          >
            <path d="M 9.5 0.5 A 9 9 0 0 1 0.5 9.5 L 9.5 9.5 Z" />
          </svg>

          <!-- Right Wing SVG -->
          <svg
            class="tab-wing tab-wing-right fill-surface pointer-events-none"
            viewBox="0 0 10 10" xmlns="http://www.w3.org/2000/svg" shape-rendering="geometricPrecision"
          >
            <path d="M 0.5 0.5 A 9 9 0 0 0 9.5 9.5 L 0.5 9.5 Z" />
          </svg>
        </div>

        <button 
          v-for="(tab, index) in tabs" 
          :key="tab.value" 
          :ref="(el) => { if (el) tabElements[tab.value] = el }"
          role="tab"
          :aria-selected="modelValue === tab.value"
          class="relative h-tabs flex items-center justify-center gap-item transition-tab-state cursor-pointer group rounded-t-tab border-none outline-none"
          :class="[
            fitMobile
              ? 'min-w-0 md:min-w-tab max-w-none md:max-w-tab flex-1 md:flex-none px-inline md:px-item whitespace-normal md:whitespace-nowrap'
              : 'min-w-tab max-w-tab px-item whitespace-nowrap',
            modelValue === tab.value
              ? 'text-subtitle z-20 text-primary font-bold'
              : 'bg-transparent text-muted hover:text-color'
          ]"
          @click="$emit('update:modelValue', tab.value)"
        >
          <i v-if="tab.icon" :class="[tab.icon, fitMobile ? 'text-body md:text-subtitle' : 'text-subtitle']" />
          <span :class="fitMobile ? 'text-body md:text-subtitle leading-tight text-center line-clamp-2 md:line-clamp-none' : 'text-subtitle'">{{ tab.label }}</span>

          <!-- Separator Line -->
          <div
            v-if="
              modelValue !== tab.value &&
                tabs[index + 1]?.value !== modelValue &&
                index < tabs.length - 1
            " class="absolute right-0 top-1/2 -translate-y-1/2 h-5 w-px bg-separator/40 pointer-events-none"
          ></div>
        </button>
      </div>

      <div v-if="$slots.actions" class="h-tabs px-item flex items-center gap-item shrink-0">
        <slot name="actions" />
      </div>
    </div>

    <!-- Unified Container Content -->
    <div
      class="w-full border-b border-l border-r border-separator bg-surface ui-tab-content rounded-b-border overflow-hidden shadow-content relative z-0 flex flex-col flex-1"
      :class="contentClass"
    >
      <div
        class="w-full flex-1 px-item py-inline"
        :class="[minHeight ? 'min-h-tab-content' : 'min-h-0', contentBodyClass]"
      >
        <slot />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted, onUnmounted, reactive } from 'vue'

const props = defineProps({
  modelValue: {
    type: String,
    required: true,
  },
  minHeight: {
    type: Boolean,
    default: true,
  },
  tabs: {
    type: Array,
    required: true,
    default: () => [],
  },
  contentClass: {
    type: [String, Array, Object],
    default: '',
  },
  headerClass: {
    type: [String, Array, Object],
    default: '',
  },
  contentBodyClass: {
    type: [String, Array, Object],
    default: '',
  },
  fitMobile: {
    type: Boolean,
    default: false,
  },
})

defineEmits(['update:modelValue'])

const tabElements = ref({})
const tabScrollerRef = ref(null)
const indicatorStyle = reactive({
  left: '0px',
  width: '0px',
  opacity: 0,
})

const scrollActiveTabIntoView = () => {
  const el = tabElements.value[props.modelValue]
  if (!el || !tabScrollerRef.value) return
  el.scrollIntoView({ block: 'nearest', inline: 'nearest' })
}

const updateIndicator = () => {
  const el = tabElements.value[props.modelValue]
  if (el) {
    indicatorStyle.left = `${el.offsetLeft}px`
    indicatorStyle.width = `${el.offsetWidth}px`
    indicatorStyle.opacity = 1
  } else {
    indicatorStyle.opacity = 0
  }
}

watch(
  () => props.modelValue,
  () => {
    nextTick(() => {
      updateIndicator()
      scrollActiveTabIntoView()
    })
  }
)

watch(
  () => props.tabs,
  () => {
    nextTick(() => {
      updateIndicator()
      scrollActiveTabIntoView()
    })
  },
  { deep: true }
)

onMounted(() => {
  nextTick(() => {
    updateIndicator()
    scrollActiveTabIntoView()
    window.addEventListener('resize', updateIndicator)
  })
})

onUnmounted(() => {
  window.removeEventListener('resize', updateIndicator)
})
</script>

<style scoped>
.app-tabs-scroll {
  scrollbar-width: none;
}

.app-tabs-scroll::-webkit-scrollbar {
  display: none;
}

@media (max-width: 767px) {
  .app-tabs-scroll--fit-mobile {
    overflow-x: hidden;
  }
}
</style>
