<template>
  <section class="ui-panel p-container source-mapping-card">
    <div class="source-mapping-header">
      <div class="flex flex-col gap-item min-w-0 w-full">
        <h1 class="text-title font-semibold text-color m-none">{{ $t('mediaDetail.sourceMappingTitle') }}</h1>
        <p class="ui-dialog-subsection text-body text-muted text-center items-center w-full m-none">
          <a
            v-if="doubanUrl"
            :href="doubanUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="source-mapping-title-link"
          >{{ mapping.title }}（{{ mapping.year }}）</a>
          <span v-else class="source-mapping-title-link source-mapping-title-static">{{ mapping.title }}（{{ mapping.year }}）</span>
          {{ $t('mediaDetail.sourceMappingAutoMatchFailed') }}
        </p>
      </div>
    </div>
    <div class="source-mapping-form grid gap-container">
      <div class="ui-dialog-section">
        <label class="ui-dialog-item-title block" for="source-mapping-search-input">{{ $t('mediaDetail.searchTerm') }}</label>
        <div class="source-mapping-search-row">
          <InputText
            id="source-mapping-search-input"
            v-model.trim="form.searchQuery"
            class="w-full"
            :placeholder="$t('mediaDetail.searchTmdbTitle')"
            :disabled="form.submitting || candidatesLoading"
            @keyup.enter="$emit('search')"
          />
          <Button
            icon="pi pi-search"
            severity="secondary"
            outlined
            :loading="candidatesLoading"
            :disabled="form.submitting"
            :aria-label="$t('mediaDetail.searchTmdbCandidates')"
            @click="$emit('search')"
          />
        </div>
      </div>
      <div class="ui-dialog-section">
        <label class="ui-dialog-item-title block" for="source-mapping-candidate-select">{{ $t('mediaDetail.tmdbCandidates') }}</label>
        <Select
          v-model="form.selectedCandidateId"
          input-id="source-mapping-candidate-select"
          :options="candidates"
          option-label="label"
          option-value="tmdbId"
          class="w-full source-mapping-select"
          :placeholder="$t('mediaDetail.selectTmdbCandidate')"
          :empty-message="$t('mediaDetail.noCandidates')"
          append-to="self"
          :loading="candidatesLoading"
          :disabled="form.submitting"
          @update:model-value="$emit('candidate-select', $event)"
        >
          <template #value="{ value, placeholder }">
            <span v-if="candidateById(value)" class="source-mapping-selected">
              {{ candidateById(value).title }}
              <span v-if="candidateById(value).year" class="text-muted">· {{ candidateById(value).year }}</span>
            </span>
            <span v-else class="text-muted">{{ placeholder }}</span>
          </template>
          <template #option="{ option }">
            <div class="source-mapping-option">
              <div class="source-mapping-option-main">
                <div class="source-mapping-option-title">
                  <span class="text-color source-mapping-option-name">{{ option.title }}</span>
                  <span v-if="option.year" class="text-muted">{{ option.year }}</span>
                  <span class="text-muted">{{ option.mediaType === 'tv' ? $t('mediaDetail.tv') : $t('mediaDetail.movie') }}</span>
                  <span v-if="option.rating" class="text-muted">{{ $t('mediaDetail.rating', { rating: option.rating }) }}</span>
                </div>
                <div class="source-mapping-option-meta">
                  {{ option.overview || option.subtitle || $t('mediaDetail.tmdbIdValue', { id: option.tmdbId }) }}
                </div>
              </div>
              <a
                class="source-mapping-option-link"
                :href="tmdbCandidateUrl(option)"
                target="_blank"
                rel="noopener noreferrer"
                :title="$t('mediaDetail.openTmdb')"
                @pointerdown.stop
                @mousedown.stop
                @click="$emit('open-candidate', $event, option)"
              >
                <i class="pi pi-external-link" />
              </a>
            </div>
          </template>
        </Select>
      </div>
      <div :class="['source-mapping-id-row', mapping.media_type === 'tv' ? 'source-mapping-id-row--tv' : '']">
        <div class="ui-dialog-section">
          <label class="ui-dialog-item-title block" for="source-mapping-tmdb-id-input">{{ $t('mediaDetail.tmdbIdLabel') }}</label>
          <InputText
            id="source-mapping-tmdb-id-input"
            v-model.trim="form.tmdbId"
            class="w-full"
            :placeholder="$t('mediaDetail.tmdbIdPlaceholder')"
            :disabled="form.submitting"
            @input="$emit('tmdb-input')"
            @keyup.enter="$emit('submit')"
          />
        </div>
        <div v-if="mapping.media_type === 'tv'" class="ui-dialog-section">
          <label class="ui-dialog-item-title block" for="source-mapping-season-number-input">{{ $t('mediaDetail.seasonNumber') }}</label>
          <InputNumber
            id="source-mapping-season-number-input"
            v-model="form.seasonNumber"
            class="w-full"
            input-class="w-full"
            :placeholder="$t('mediaDetail.seasonNumberPlaceholder')"
            :min="1"
            :use-grouping="false"
            :disabled="form.submitting"
            @keyup.enter="$emit('submit')"
          />
        </div>
        <div v-if="mapping.media_type === 'tv'" class="ui-dialog-section">
          <label class="ui-dialog-item-title block" for="source-mapping-episode-count-override-input">{{ $t('mediaDetail.episodeCountOverride') }}</label>
          <InputNumber
            id="source-mapping-episode-count-override-input"
            v-model="form.episodeCountOverride"
            class="w-full"
            input-class="w-full"
            :placeholder="$t('mediaDetail.episodeCountOverridePlaceholder')"
            :min="1"
            :use-grouping="false"
            :disabled="form.submitting"
            @keyup.enter="$emit('submit')"
          />
        </div>
      </div>
    </div>
    <div class="source-mapping-actions">
      <Button :label="$t('mediaDetail.retryAutoMatch')" severity="secondary" outlined :disabled="form.submitting" @click="$emit('retry')" />
      <Button :label="$t('mediaDetail.saveAndContinue')" :loading="form.submitting" @click="$emit('submit')" />
    </div>
  </section>
</template>

<script setup>
import Button from 'primevue/button'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'

const props = defineProps({
  mapping: { type: Object, required: true },
  form: { type: Object, required: true },
  candidates: { type: Array, default: () => [] },
  candidatesLoading: { type: Boolean, default: false },
  doubanUrl: { type: String, default: '' },
  tmdbCandidateUrl: { type: Function, required: true },
})

defineEmits(['search', 'candidate-select', 'tmdb-input', 'open-candidate', 'retry', 'submit'])

function candidateById(tmdbId) {
  return props.candidates.find((candidate) => candidate.tmdbId === tmdbId) || null
}
</script>

<style scoped>
.source-mapping-card {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-container);
  max-width: 760px;
  margin: clamp(var(--spacing-block), 8vh, calc(var(--spacing-block) * 3)) auto 0;
}

.source-mapping-header {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-item);
}

.source-mapping-form { width: 100%; }

.source-mapping-id-row {
  gap: var(--spacing-container);
  display: grid;
  grid-template-columns: minmax(0, 1fr);
}

@media (min-width: 640px) { .source-mapping-id-row { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (min-width: 768px) { .source-mapping-id-row--tv { grid-template-columns: repeat(3, minmax(0, 1fr)); } }

.source-mapping-title-link {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  color: var(--text-default);
  font-weight: 500;
  transition: color 0.2s ease;
}

.source-mapping-title-link:hover { color: var(--accent-primary); }
.source-mapping-title-static:hover { color: var(--text-default); }

.source-mapping-search-row {
  gap: var(--spacing-item);
  display: grid;
  align-items: center;
  grid-template-columns: minmax(0, 1fr) auto;
}

.source-mapping-selected {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-inline);
  max-width: 100%;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-mapping-select { max-width: 100%; }

.source-mapping-select :deep(.p-select-overlay) {
  width: 100%;
  max-width: 100%;
}

.source-mapping-select :deep(.p-select-list-container) { max-width: 100%; }

.source-mapping-option {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: var(--spacing-item);
  align-items: center;
  max-width: 100%;
  min-width: 0;
  width: 100%;
}

.source-mapping-option-main { min-width: 0; }

.source-mapping-option-title {
  gap: var(--spacing-inline);
  display: flex;
  align-items: center;
  flex-wrap: nowrap;
  min-width: 0;
  font-size: var(--text-body);
  font-weight: 500;
}

.source-mapping-option-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-mapping-option-meta {
  overflow: hidden;
  max-width: 100%;
  color: var(--text-muted);
  font-size: var(--text-caption);
  line-height: 1.5;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-mapping-option-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  color: var(--text-muted);
  border-radius: var(--p-border-radius-md);
  transition: color 0.2s ease, background-color 0.2s ease;
}

.source-mapping-option-link:hover {
  color: var(--accent-primary);
  background-color: var(--surface-subtle);
}

.source-mapping-actions {
  gap: var(--spacing-item);
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
}
</style>
