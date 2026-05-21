<template>
  <div v-if="loading" class="directory-integrity-summary-grid">
    <div v-for="index in 4" :key="index" class="ui-panel directory-integrity-summary-card p-container flex flex-col gap-item">
      <div class="h-7 flex items-center">
        <Skeleton width="56%" height="var(--text-title)" />
      </div>
      <Skeleton width="40%" height="var(--text-hero)" />
    </div>
  </div>

  <div v-else class="flex flex-col gap-container">
    <div v-if="globalCards.length > 0" class="directory-integrity-summary-grid">
      <div
        v-for="card in globalCards"
        :key="card.key"
        class="ui-panel directory-integrity-summary-card p-container flex flex-col gap-item"
      >
        <div class="text-title font-bold h-7 flex items-center">{{ card.label }}</div>
        <div :class="['text-hero font-semibold', card.valueClass]">{{ card.value }}</div>
      </div>
    </div>

    <div v-if="currentCards.length > 0" :class="['ui-panel', 'directory-integrity-current-overview', currentPanelClass]">
      <div class="directory-integrity-current-overview__line">
        <template v-for="(card, index) in currentCards" :key="card.key">
          <span v-if="index > 0" class="directory-integrity-current-overview__separator">·</span>
          <span class="directory-integrity-current-overview__part">
            <span class="text-muted">{{ card.label }}</span>
            <span :class="['font-semibold', card.valueClass]">{{ card.value }}</span>
          </span>
        </template>
      </div>
      <div class="directory-integrity-current-overview__line">
        <template v-if="issueCounts.length > 0">
          <template v-for="(item, index) in issueCounts" :key="item.issueType">
            <span v-if="index > 0" class="directory-integrity-current-overview__separator">·</span>
            <span class="directory-integrity-current-overview__part text-status-warning">{{ item.label }}</span>
          </template>
        </template>
        <span v-else class="text-status-success">{{ $t('mediaManagement.directoryIntegrity.clean') }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import Skeleton from 'primevue/skeleton'

defineProps({
  loading: {
    type: Boolean,
    default: false,
  },
  globalCards: {
    type: Array,
    default: () => [],
  },
  currentCards: {
    type: Array,
    default: () => [],
  },
  issueCounts: {
    type: Array,
    default: () => [],
  },
  currentPanelClass: {
    type: String,
    default: '',
  },
})
</script>

<style scoped>
.directory-integrity-summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--spacing-item);
}

.directory-integrity-summary-card {
  min-height: var(--size-placeholder-summary);
}

.directory-integrity-current-overview {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--spacing-inline);
  padding: var(--spacing-item);
  background-color: var(--panel-surface-bg, var(--surface-content));
  color: var(--text-default);
  font-size: var(--text-body);
  line-height: 1.6;
}

.directory-integrity-current-overview__line {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  align-items: center;
  column-gap: var(--spacing-inline);
  row-gap: var(--spacing-micro);
}

.directory-integrity-current-overview__line::before {
  content: "•";
  color: var(--text-muted);
  margin-right: var(--spacing-inline);
  flex-shrink: 0;
}

.directory-integrity-current-overview__part {
  display: inline-flex;
  min-width: 0;
  align-items: baseline;
  gap: var(--spacing-micro);
}

.directory-integrity-current-overview__separator {
  color: var(--text-muted);
}

@media (min-width: 1024px) {
  .directory-integrity-summary-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}
</style>
