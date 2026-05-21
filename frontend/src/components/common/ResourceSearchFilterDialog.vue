<template>
  <Dialog
    :visible="visible" modal :dismissable-mask="true" :header="$t('resourceSearch.filterDialogTitle')" class="w-full max-w-dialog-lg"
    @update:visible="$emit('update:visible', $event)"
  >
    <div class="ui-dialog-body">
      <!-- Search parameters. -->
      <div class="ui-dialog-section">
        <h3 class="text-title font-medium text-color">{{ $t('resourceSearch.searchParameters') }}</h3>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-item">
          <!-- Media ID. -->
          <div v-if="showMediaIdInput" class="flex flex-col gap-item">
            <label class="ui-dialog-item-title text-caption text-muted">{{ $t('resourceSearch.mediaId') }}</label>
            <InputText
              v-model="localSearchState.media_id" :placeholder="$t('resourceSearch.mediaIdPlaceholder')" class="w-full"
              :disabled="disableMediaIdInput || loading"
            />
          </div>

          <!-- Site selection. -->
          <div v-if="showSiteInput" class="flex flex-col gap-item">
            <label class="ui-dialog-item-title text-caption text-muted">{{ $t('resourceSearch.searchSites') }}</label>
            <MultiSelect
              v-model="searchState.site" :options="siteOptions" option-label="label" option-value="value" filter
              :placeholder="$t('resourceSearch.allSites')" display="chip" class="w-full" :disabled="disableSiteInput || loading"
              :max-selected-labels="2"
            />
          </div>

          <!-- Keyword. -->
          <div class="flex flex-col gap-item">
            <label class="ui-dialog-item-title text-caption text-muted">{{ $t('resourceSearch.searchKeyword') }}</label>
            <InputText v-model="searchState.keyword" :placeholder="$t('resourceSearch.keywordSearchPlaceholder')" class="w-full" :disabled="loading" />
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="flex justify-end gap-item">
        <Button :label="$t('common.cancel')" icon="pi pi-times" severity="secondary" text @click="$emit('update:visible', false)" />
        <Button :label="$t('common.confirm')" icon="pi pi-check" @click="$emit('confirm')" />
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import MultiSelect from 'primevue/multiselect'

defineProps({
  visible: Boolean,
  loading: Boolean,
  hasSearched: Boolean,
  alwaysShowResults: Boolean,

  // State objects.
  localSearchState: Object,
  searchState: Object,
  filterForm: Object,

  // Options.
  siteOptions: Array,
  availableResolutions: Array,
  availableSeasons: Array,
  availableEpisodes: Array,
  availableGroups: Array,
  availableSources: Array,
  availableResourceForms: Array,
  sizeOptions: Array,
  seederOptions: Array,

  // Flags.
  showMediaIdInput: Boolean,
  showSiteInput: Boolean,
  disableMediaIdInput: Boolean,
  disableSiteInput: Boolean
})

defineEmits(['update:visible', 'confirm'])

</script>

<style scoped>
/* Optional custom styles. Tailwind covers most cases. */
</style>
