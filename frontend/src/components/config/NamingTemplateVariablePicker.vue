<template>
  <div class="available-variables">
    <div class="variable-grid">
      <button
        v-for="variable in variables"
        :key="variable.token"
        type="button"
        class="variable-item"
        @click="$emit('select', variable.token)"
      >
        <span class="variable-name">{{ variable.token }}</span>
        <span class="variable-desc">{{ variable.desc }}</span>
      </button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  variables: {
    type: Array,
    default: () => [],
  },
})

defineEmits(['select'])
</script>

<style scoped>
.available-variables {
  max-height: var(--size-content-height);
  overflow-y: auto;
}

.variable-grid {
  display: grid;
  grid-template-columns: repeat(1, minmax(0, 1fr));
  gap: var(--spacing-item);
}

@media (min-width: 768px) {
  .variable-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

.variable-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--spacing-item);
  padding: var(--spacing-item);
  background-color: var(--surface-content);
  border-radius: var(--radius-container);
  border: 1px solid var(--border-default);
  box-shadow: var(--shadow-content);
  cursor: pointer;
  text-align: left;
  transition: border-color 0.2s ease, background-color 0.2s ease, box-shadow 0.2s ease;
}

.variable-item:hover {
  background-color: color-mix(in srgb, var(--accent-primary) 8%, var(--surface-content));
  border-color: color-mix(in srgb, var(--accent-primary) 24%, var(--border-default));
  box-shadow: var(--shadow-content);
}

.variable-name {
  font-family: monospace;
  font-size: var(--text-small);
  font-weight: 600;
  color: var(--accent-primary);
  background-color: color-mix(in srgb, var(--accent-primary) 10%, transparent);
  padding-inline: var(--spacing-item);
  padding-block: var(--spacing-inline);
  border-radius: var(--radius-container);
  line-height: 1.4;
}

.variable-desc {
  font-size: var(--text-tiny);
  color: var(--text-muted);
  line-height: 1.5;
}
</style>
