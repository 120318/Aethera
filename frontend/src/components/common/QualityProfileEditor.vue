<template>
  <div class="flex flex-col gap-container">
    <div class="ui-dialog-section">
      <div class="flex flex-col gap-container mt-item">
        <div class="ui-dialog-section">
          <label class="ui-dialog-item-title block">{{ $t('settings.quality.editor.name') }}</label>
          <InputText v-model="draft.name" class="w-full" :placeholder="$t('settings.quality.editor.namePlaceholder')" :disabled="disabled" />
        </div>

        <div class="ui-dialog-section">
          <label class="inline-flex items-center gap-inline text-body text-color">
            <Checkbox v-model="draft.active_default" binary input-id="quality-profile-default" :disabled="disabled" />
            <span>{{ $t('settings.quality.editor.defaultProfile') }}</span>
          </label>
          <p class="text-caption text-muted m-none mt-micro">{{ $t('settings.quality.editor.defaultProfileHint') }}</p>
        </div>

        <div class="ui-dialog-section">
          <label class="ui-dialog-item-title block">{{ $t('settings.quality.editor.minScore') }}</label>
          <InputNumber v-model="draft.min_score" class="w-full" :disabled="disabled" :placeholder="$t('settings.quality.editor.minScorePlaceholder')" />
          <p class="text-caption text-muted m-none mt-micro">{{ $t('settings.quality.editor.minScoreHint') }}</p>
        </div>

      </div>
    </div>

    <div class="ui-dialog-section">
      <div class="flex items-start justify-between gap-item">
        <div>
          <label class="ui-dialog-item-title block">{{ $t('settings.quality.editor.rankingPanel') }}</label>
          <p class="text-caption text-muted m-none mt-micro">{{ $t('settings.quality.editor.rankingPanelHint') }}</p>
        </div>
      </div>

      <div ref="dimensionListRef" class="mt-item flex flex-col gap-item">
        <div
          v-for="dimension in draft.ranking.dimension_order"
          :key="dimension"
          class="quality-profile-row"
          :data-dimension="dimension"
        >
          <div
            class="flex flex-col gap-item rounded-container border border-separator bg-surface px-item py-item shadow-content"
          >
            <div class="-mx-item -mt-item inline-flex items-center shrink-0 border-b border-separator bg-emphasis">
              <button
                type="button"
                class="quality-profile-row-handle inline-flex h-control-icon-sm w-control-icon-sm shrink-0 items-center justify-center bg-transparent text-muted"
                :disabled="disabled"
                :aria-label="$t('settings.quality.editor.dragDimensionOrder')"
              >
                <i class="pi pi-bars" aria-hidden="true"></i>
              </button>
              <div class="text-body font-semibold text-color">
                {{ dimensionLabel(dimension) }}
              </div>
            </div>
            <div
              :ref="setValueListRef(dimension)"
              class="flex w-full flex-wrap items-center gap-inline"
              :data-dimension="dimension"
            >
              <div
                v-for="value in draft.ranking[dimension]"
                :key="`${dimension}-${value}`"
                class="quality-profile-chip inline-flex cursor-grab select-none touch-none"
                :data-value="value"
              >
                <AppTag :value="value" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="ui-dialog-section">
      <div class="flex items-start justify-between gap-item">
        <div>
          <label class="ui-dialog-item-title block">{{ $t('settings.quality.editor.tagScores') }}</label>
          <p class="text-caption text-muted m-none mt-micro">{{ $t('settings.quality.editor.tagScoresHint') }}</p>
        </div>
      </div>

      <MultiSelect
        v-model="scoreTagIds"
        :options="tagOptions"
        option-label="label"
        option-value="value"
        filter
        display="chip"
        class="w-full mt-item"
        :placeholder="$t('settings.quality.editor.selectScoreTags')"
        :disabled="disabled"
        @change="syncTagScores"
      />

      <div v-if="scoreTagIds.length" class="mt-item flex flex-wrap gap-item">
        <div
          v-for="tagId in scoreTagIds"
          :key="tagId"
          class="inline-flex items-center gap-inline rounded-container border border-separator bg-surface px-item py-inline"
        >
          <span class="text-body text-color">{{ getTagLabel(tagId) }}</span>
          <InputNumber
            v-model="draft.tag_scores[tagId]"
            input-class="text-right"
            class="w-7rem"
            :disabled="disabled"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import Checkbox from 'primevue/checkbox'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import MultiSelect from 'primevue/multiselect'
import Sortable from 'sortablejs'
import AppTag from '@/components/common/AppTag.vue'
import { buildQualityRankingDimensionOptions, cloneQualityRanking } from '@/composables/qualityRankingSupport'
import { normalizeQualityProfile, qualityProfileTagScoreIds } from '@/composables/qualityProfileSupport'

const props = defineProps({
  modelValue: {
    type: Object,
    required: true,
  },
  tagOptions: {
    type: Array,
    default: () => [],
  },
  disabled: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['update:modelValue'])
const { t } = useI18n()

const draft = reactive(normalizeQualityProfile(props.modelValue))
const scoreTagIds = ref(qualityProfileTagScoreIds(draft))
const dimensionListRef = ref(null)
const valueListRefs = ref({})
const qualityRankingDimensionOptions = computed(() => buildQualityRankingDimensionOptions(t))
let dimensionSortable = null
const valueSortables = new Map()

onMounted(() => {
  void setupSortables()
})

onBeforeUnmount(() => {
  destroySortables()
})

watch(
  () => props.modelValue,
  (value) => {
    const next = normalizeQualityProfile(value)
    Object.assign(draft, next)
    draft.ranking = cloneQualityRanking(next.ranking)
    draft.tag_scores = { ...(next.tag_scores || {}) }
    scoreTagIds.value = qualityProfileTagScoreIds(next)
  },
  { deep: true },
)

watch(
  draft,
  () => {
    emit('update:modelValue', normalizeQualityProfile(draft))
  },
  { deep: true },
)

watch(
  () => props.disabled,
  () => {
    syncSortableDisabledState()
  },
)

watch(
  () => draft.ranking.dimension_order.join('|'),
  async () => {
    await setupSortables()
  },
)

function dimensionLabel(key) {
  return qualityRankingDimensionOptions.value.find((item) => item.key === key)?.label || key
}

function setValueListRef(dimension) {
  return (element) => {
    if (element) {
      valueListRefs.value[dimension] = element
      return
    }
    delete valueListRefs.value[dimension]
  }
}

function syncTagScores() {
  const nextScores = {}
  for (const tagId of scoreTagIds.value) {
    const currentValue = draft.tag_scores[tagId]
    nextScores[tagId] = currentValue === 0 || currentValue ? currentValue : 0
  }
  draft.tag_scores = nextScores
}

function getTagLabel(tagId) {
  return props.tagOptions.find((item) => item.value === tagId)?.label || tagId
}

async function setupSortables() {
  await nextTick()
  setupDimensionSortable()
  setupValueSortables()
}

function setupDimensionSortable() {
  if (!dimensionListRef.value) return
  if (dimensionSortable) {
    dimensionSortable.destroy()
  }
  dimensionSortable = Sortable.create(dimensionListRef.value, {
    animation: 180,
    delay: 120,
    delayOnTouchOnly: true,
    ghostClass: 'quality-profile-ghost',
    chosenClass: 'quality-profile-chosen',
    dragClass: 'quality-profile-dragging',
    handle: '.quality-profile-row-handle',
    disabled: props.disabled,
    onEnd(event) {
      if (event.oldIndex == null || event.newIndex == null || event.oldIndex === event.newIndex) return
      const next = [...draft.ranking.dimension_order]
      const [moved] = next.splice(event.oldIndex, 1)
      next.splice(event.newIndex, 0, moved)
      draft.ranking.dimension_order = next
    },
  })
}

function setupValueSortables() {
  const activeDimensions = new Set(draft.ranking.dimension_order)
  for (const [dimension, sortable] of valueSortables.entries()) {
    if (!activeDimensions.has(dimension)) {
      sortable.destroy()
      valueSortables.delete(dimension)
    }
  }

  for (const dimension of draft.ranking.dimension_order) {
    const container = valueListRefs.value[dimension]
    if (!container) continue
    const existing = valueSortables.get(dimension)
    if (existing) {
      existing.option('disabled', props.disabled)
      continue
    }
    const sortable = Sortable.create(container, {
      animation: 160,
      delay: 120,
      delayOnTouchOnly: true,
      ghostClass: 'quality-profile-ghost',
      chosenClass: 'quality-profile-chosen',
      dragClass: 'quality-profile-dragging',
      draggable: '.quality-profile-chip',
      disabled: props.disabled,
      onEnd(event) {
        if (event.oldIndex == null || event.newIndex == null || event.oldIndex === event.newIndex) return
        const currentValues = [...(draft.ranking[dimension] || [])]
        const [moved] = currentValues.splice(event.oldIndex, 1)
        currentValues.splice(event.newIndex, 0, moved)
        draft.ranking[dimension] = currentValues
      },
    })
    valueSortables.set(dimension, sortable)
  }
}

function syncSortableDisabledState() {
  if (dimensionSortable) {
    dimensionSortable.option('disabled', props.disabled)
  }
  for (const sortable of valueSortables.values()) {
    sortable.option('disabled', props.disabled)
  }
}

function destroySortables() {
  if (dimensionSortable) {
    dimensionSortable.destroy()
    dimensionSortable = null
  }
  for (const sortable of valueSortables.values()) {
    sortable.destroy()
  }
  valueSortables.clear()
}
</script>

<style scoped>
.quality-profile-row-handle {
  border: none;
  color: var(--text-muted-color);
  cursor: grab;
}

.quality-profile-row-handle:disabled {
  cursor: default;
  opacity: 0.4;
}

:deep(.quality-profile-ghost) {
  opacity: 0.35;
}

:deep(.quality-profile-chosen) {
  border-color: var(--primary-color);
  background: var(--highlight-background);
}

:deep(.quality-profile-dragging) {
  opacity: 0.8;
}
</style>
