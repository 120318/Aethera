<template>
  <TabDialog
    :model-value="visible"
    :active-tab="activeTab"
    :tabs="subscriptionDialogTabs"
    size="md"
    @update:model-value="$emit('update:visible', $event)"
    @update:active-tab="activeTab = $event"
  >
    <template #actions>
      <Button icon="pi pi-times" severity="secondary" text rounded :aria-label="$t('common.close')" @click="$emit('update:visible', false)" />
    </template>

    <template v-if="!loadingInitialData">
      <div v-if="activeTab === 'basic'" class="flex flex-col gap-block">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-container">
          <div class="ui-dialog-section">
            <label class="ui-dialog-item-title">{{ $t('subscription.status') }}</label>
            <div class="flex items-center gap-item mt-item">
              <ToggleSwitch v-model="form.active" input-id="subscriptionActive" />
              <label for="subscriptionActive" class="text-body">{{ subscriptionLabel }}</label>
            </div>
          </div>

          <div class="ui-dialog-section">
            <label class="ui-dialog-item-title">{{ $t('subscription.followReminder') }}</label>
            <div class="flex items-center gap-item mt-item">
              <ToggleSwitch v-model="form.followed" input-id="subscriptionFollowed" />
              <label for="subscriptionFollowed" class="text-body">{{ followLabel }}</label>
            </div>
          </div>
        </div>

        <div class="ui-dialog-section">
          <label class="ui-dialog-item-title">{{ $t('subscription.mode') }}</label>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-item">
            <div v-for="option in subscriptionModeOptions" :key="option.value" class="ui-radio-description-option">
              <RadioButton v-model="form.subscription_mode" :input-id="`subscriptionMode-${option.value}`" name="subscriptionMode" :value="option.value" />
              <label :for="`subscriptionMode-${option.value}`" class="ui-dialog-item-title cursor-pointer">{{ option.label }}</label>
              <span class="ui-radio-description-copy text-caption text-muted">{{ option.description }}</span>
            </div>
          </div>
        </div>

        <div class="ui-dialog-section">
          <label class="ui-dialog-item-title">{{ $t('subscription.directory') }}</label>
          <Dropdown v-model="form.directory_id" :options="directoryOptions" option-label="path" option-value="id" :placeholder="$t('subscription.selectDirectory')" class="w-full" :loading="loadingDirs" />
        </div>

        <div class="ui-dialog-section">
          <div class="flex items-center gap-item">
            <Checkbox v-model="runAfterSave" binary input-id="subscriptionRunAfterSave" :disabled="!canRunAfterSave" />
            <label for="subscriptionRunAfterSave" class="text-body">{{ $t('subscription.runAfterSave') }}</label>
          </div>
          <p class="text-caption text-muted m-none mt-inline">{{ $t('subscription.runAfterSaveHint') }}</p>
        </div>
      </div>

      <div v-else-if="activeTab === 'quality'" class="flex flex-col gap-block">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-container">
          <div class="ui-dialog-section">
            <label class="ui-dialog-item-title">{{ $t('subscription.siteScope') }}</label>
            <MultiSelect v-model="form.sites" :options="siteOptions" option-label="label" option-value="value" filter :placeholder="$t('subscription.allAvailableSites')" display="chip" class="w-full" />
          </div>

          <div class="ui-dialog-section">
            <label class="ui-dialog-item-title">{{ $t('subscription.qualityProfile') }}</label>
            <Dropdown
              v-model="qualityProfileSelection"
              :options="qualityProfileDropdownOptions"
              option-label="name"
              option-value="id"
              :placeholder="$t('subscription.followFilter')"
              class="w-full"
              @change="onQualityProfileChange"
            />
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-item">
          <div class="ui-dialog-section">
            <label class="ui-dialog-item-title">{{ $t('subscription.filterMethod') }}</label>
            <Dropdown
              v-model="filterMode"
              :options="filterModeOptions"
              option-label="label"
              option-value="value"
              :placeholder="$t('subscription.selectFilterMethod')"
              class="w-full"
              @change="onFilterModeChange"
            />
          </div>

          <div v-if="showBaseFilterPreset" class="ui-dialog-section">
            <label class="ui-dialog-item-title">{{ $t('subscription.basePreset') }}</label>
            <Dropdown
              v-model="form.filter_config_id"
              :options="filterOptions"
              option-label="name"
              option-value="id"
              :placeholder="$t('subscription.selectBasePreset')"
              class="w-full"
              show-clear
              @change="onFilterPresetSelectionChange"
            />
          </div>
        </div>

        <div v-if="showCustomFilters" class="ui-dialog-subsection">
          <label class="ui-dialog-item-title ui-dialog-subsection-title m-none">{{ $t('subscription.customFilterOverride') }}</label>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-item mt-item">
            <div class="ui-dialog-section">
              <label class="ui-dialog-item-title">{{ $t('subscription.resourceType') }}</label>
              <ResourceKindFormSelect v-model:resource-kind="form.filters.resource_kind" v-model:resource-form="form.filters.resource_form" />
            </div>

            <div class="ui-dialog-section">
              <label class="ui-dialog-item-title">{{ $t('subscription.resolution') }}</label>
              <MultiSelect v-model="form.filters.resolution" :options="resolutionOptions" filter :placeholder="$t('subscription.selectResolution')" display="chip" class="w-full" />
            </div>

            <div class="ui-dialog-section">
              <label class="ui-dialog-item-title">{{ $t('subscription.source') }}</label>
              <MultiSelect v-model="form.filters.source" :options="sourceOptions" filter :placeholder="$t('subscription.selectSource')" display="chip" class="w-full" />
            </div>

            <div class="ui-dialog-section">
              <label class="ui-dialog-item-title">{{ $t('subscription.codec') }}</label>
              <MultiSelect v-model="form.filters.codec" :options="codecOptions" filter :placeholder="$t('subscription.selectCodec')" display="chip" class="w-full" />
            </div>

            <div class="ui-dialog-section">
              <label class="ui-dialog-item-title">{{ $t('subscription.hdrType') }}</label>
              <MultiSelect v-model="form.filters.hdr_type" :options="hdrOptions" filter :placeholder="$t('subscription.selectHdr')" display="chip" class="w-full" />
            </div>

            <div class="ui-dialog-section">
              <label class="ui-dialog-item-title">{{ $t('subscription.audioCodec') }}</label>
              <MultiSelect v-model="form.filters.audio_codec" :options="audioCodecOptions" filter :placeholder="$t('subscription.selectAudioCodec')" display="chip" class="w-full" />
            </div>

            <div class="ui-dialog-section">
              <label class="ui-dialog-item-title">{{ $t('subscription.audioChannels') }}</label>
              <MultiSelect v-model="form.filters.audio_channels" :options="audioChannelOptions" filter :placeholder="$t('subscription.selectAudioChannels')" display="chip" class="w-full" />
            </div>

            <div class="ui-dialog-section">
              <label class="ui-dialog-item-title">{{ $t('subscription.colorDepth') }}</label>
              <MultiSelect v-model="form.filters.color_depth" :options="colorDepthOptions" filter :placeholder="$t('subscription.selectColorDepth')" display="chip" class="w-full" />
            </div>

            <div class="ui-dialog-section">
              <label class="ui-dialog-item-title">{{ $t('subscription.tags') }}</label>
              <MultiSelect v-model="form.filters.tags" :options="tagOptions" option-label="label" option-value="value" filter :placeholder="$t('subscription.selectTags')" display="chip" class="w-full" />
            </div>

            <div class="ui-dialog-section md:col-span-2">
              <label class="ui-dialog-item-title">{{ $t('subscription.includeKeywords') }}</label>
              <Chips v-model="form.filters.include_keywords" separator="," :placeholder="$t('subscription.keywordPlaceholder')" class="w-full" />
            </div>

            <div class="ui-dialog-section md:col-span-2">
              <label class="ui-dialog-item-title">{{ $t('subscription.excludeKeywords') }}</label>
              <Chips v-model="form.filters.exclude_keywords" separator="," :placeholder="$t('subscription.keywordPlaceholder')" class="w-full" />
            </div>
          </div>
        </div>
      </div>

      <div v-else-if="activeTab === 'upgrade'" class="flex flex-col gap-block">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-item">
          <div class="ui-dialog-section">
            <label class="ui-dialog-item-title">{{ $t('subscription.targetFilterMethod') }}</label>
            <Dropdown
              v-model="targetFilterMode"
              :options="filterModeOptions"
              option-label="label"
              option-value="value"
              :placeholder="$t('subscription.selectTargetFilterMethod')"
              class="w-full"
              @change="onTargetFilterModeChange"
            />
          </div>

          <div v-if="showTargetBasePreset" class="ui-dialog-section">
            <label class="ui-dialog-item-title">{{ $t('subscription.targetBasePreset') }}</label>
            <Dropdown
              v-model="targetFilterConfigId"
              :options="filterOptions"
              option-label="name"
              option-value="id"
              :placeholder="$t('subscription.selectTargetBasePreset')"
              class="w-full"
              show-clear
              @change="onTargetFilterPresetSelectionChange"
            />
          </div>
        </div>

        <div v-if="showAdvancedUpgradeSettings" class="flex flex-col gap-item">
          <div class="ui-dialog-section">
            <label class="ui-dialog-item-title">{{ $t('subscription.upgradeStrategy') }}</label>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-item mt-item">
              <div class="ui-radio-description-option min-w-0">
                <RadioButton v-model="upgradeMode" input-id="stateUpgradeTemp" name="stateUpgradeMode" value="consistent_allow_temp" @change="syncUpgradePolicyFromMode" />
                <label for="stateUpgradeTemp" class="ui-dialog-item-title cursor-pointer">{{ $t('subscription.upgradeTempFirst') }}</label>
                <span class="ui-radio-description-copy text-caption text-muted">{{ $t('subscription.upgradeTempFirstDescription') }}</span>
              </div>
              <div class="ui-radio-description-option min-w-0">
                <RadioButton v-model="upgradeMode" input-id="stateUpgradeStrict" name="stateUpgradeMode" value="consistent_skip_low" @change="syncUpgradePolicyFromMode" />
                <label for="stateUpgradeStrict" class="ui-dialog-item-title cursor-pointer">{{ $t('subscription.upgradeStrict') }}</label>
                <span class="ui-radio-description-copy text-caption text-muted">{{ $t('subscription.upgradeStrictDescription') }}</span>
              </div>
            </div>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-container">
            <div class="ui-dialog-section">
              <label class="ui-dialog-item-title">{{ $t('subscription.lockModeLabel') }}</label>
              <Dropdown v-model="form.upgrade_policy.lock_mode" :options="upgradeLockModeOptions" option-label="label" option-value="value" :placeholder="$t('subscription.selectLockMode')" class="w-full" />
            </div>
            <div class="ui-dialog-section">
              <label class="ui-dialog-item-title">{{ $t('subscription.minUpgradeDelta') }}</label>
              <InputNumber v-model="form.upgrade_policy.min_upgrade_score_delta" class="w-full" />
            </div>
          </div>
        </div>

        <div v-if="showCustomTargetFilters" class="ui-dialog-subsection">
          <label class="ui-dialog-item-title ui-dialog-subsection-title m-none">{{ $t('subscription.targetCustomFilters') }}</label>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-item mt-item">
            <div class="ui-dialog-section">
              <label class="ui-dialog-item-title">{{ $t('subscription.resourceType') }}</label>
              <ResourceKindFormSelect v-model:resource-kind="form.target_filters.resource_kind" v-model:resource-form="form.target_filters.resource_form" />
            </div>

            <div class="ui-dialog-section">
              <label class="ui-dialog-item-title">{{ $t('subscription.resolution') }}</label>
              <MultiSelect v-model="form.target_filters.resolution" :options="resolutionOptions" filter :placeholder="$t('subscription.selectResolution')" display="chip" class="w-full" />
            </div>

            <div class="ui-dialog-section">
              <label class="ui-dialog-item-title">{{ $t('subscription.source') }}</label>
              <MultiSelect v-model="form.target_filters.source" :options="sourceOptions" filter :placeholder="$t('subscription.selectSource')" display="chip" class="w-full" />
            </div>

            <div class="ui-dialog-section">
              <label class="ui-dialog-item-title">{{ $t('subscription.codec') }}</label>
              <MultiSelect v-model="form.target_filters.codec" :options="codecOptions" filter :placeholder="$t('subscription.selectCodec')" display="chip" class="w-full" />
            </div>

            <div class="ui-dialog-section">
              <label class="ui-dialog-item-title">{{ $t('subscription.hdrType') }}</label>
              <MultiSelect v-model="form.target_filters.hdr_type" :options="hdrOptions" filter :placeholder="$t('subscription.selectHdr')" display="chip" class="w-full" />
            </div>

            <div class="ui-dialog-section">
              <label class="ui-dialog-item-title">{{ $t('subscription.audioCodec') }}</label>
              <MultiSelect v-model="form.target_filters.audio_codec" :options="audioCodecOptions" filter :placeholder="$t('subscription.selectAudioCodec')" display="chip" class="w-full" />
            </div>

            <div class="ui-dialog-section">
              <label class="ui-dialog-item-title">{{ $t('subscription.audioChannels') }}</label>
              <MultiSelect v-model="form.target_filters.audio_channels" :options="audioChannelOptions" filter :placeholder="$t('subscription.selectAudioChannels')" display="chip" class="w-full" />
            </div>

            <div class="ui-dialog-section">
              <label class="ui-dialog-item-title">{{ $t('subscription.colorDepth') }}</label>
              <MultiSelect v-model="form.target_filters.color_depth" :options="colorDepthOptions" filter :placeholder="$t('subscription.selectColorDepth')" display="chip" class="w-full" />
            </div>

            <div class="ui-dialog-section">
              <label class="ui-dialog-item-title">{{ $t('subscription.tags') }}</label>
              <MultiSelect v-model="form.target_filters.tags" :options="tagOptions" option-label="label" option-value="value" filter :placeholder="$t('subscription.selectTags')" display="chip" class="w-full" />
            </div>

            <div class="ui-dialog-section md:col-span-2">
              <label class="ui-dialog-item-title">{{ $t('subscription.includeKeywords') }}</label>
              <Chips v-model="form.target_filters.include_keywords" separator="," :placeholder="$t('subscription.keywordPlaceholder')" class="w-full" />
            </div>

            <div class="ui-dialog-section md:col-span-2">
              <label class="ui-dialog-item-title">{{ $t('subscription.excludeKeywords') }}</label>
              <Chips v-model="form.target_filters.exclude_keywords" separator="," :placeholder="$t('subscription.keywordPlaceholder')" class="w-full" />
            </div>
          </div>
        </div>
      </div>

      <div v-else-if="activeTab === 'unmatched'" class="flex flex-col gap-item">
        <div class="ui-dialog-section">
          <label class="ui-dialog-item-title">{{ $t('subscription.unmatchedRules') }}</label>
          <p class="text-caption text-muted m-none mt-inline">{{ $t('subscription.unmatchedRulesHint') }}</p>
        </div>

        <div v-if="form.unmatched_rules.length === 0" class="mapping-empty-state">
          {{ $t('subscription.noUnmatchedRules') }}
        </div>
        <div v-for="(rule, index) in form.unmatched_rules" :key="index" class="ui-surface-item">
          <div class="grid grid-cols-1 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_auto] gap-item md:items-center">
            <div class="min-w-0">
              <MultiSelect v-model="rule.sites" :options="siteOptions" option-label="label" option-value="value" filter :placeholder="$t('subscription.ruleSitesPlaceholder')" display="comma" :max-selected-labels="1" :selected-items-label="$t('subscription.selectedSitesLabel')" class="w-full" />
            </div>
            <div class="min-w-0">
              <InputText v-model="rule.search_title" class="w-full" :placeholder="$t('subscription.ruleSearchTitlePlaceholder')" />
            </div>
            <div class="min-w-0">
              <InputText v-model="rule.pattern" class="w-full" :placeholder="$t('subscription.rulePatternPlaceholder')" />
            </div>
            <div class="flex justify-end">
              <Button icon="pi pi-trash" severity="danger" text rounded @click="removeUnmatchedRule(index)" />
            </div>
          </div>
        </div>
        <Button :label="$t('subscription.addRule')" icon="pi pi-plus" severity="primary" outlined class="w-full" @click="addUnmatchedRule" />
      </div>
    </template>

    <template #footer>
      <Button :label="$t('common.cancel')" severity="secondary" text @click="$emit('update:visible', false)" />
      <Button :label="primarySaveLabel" icon="pi pi-check" :loading="saving || loadingInitialData" :disabled="loadingInitialData" @click="save" />
    </template>
  </TabDialog>
</template>

<script setup>
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import Chips from 'primevue/chips'
import Dropdown from 'primevue/dropdown'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import MultiSelect from 'primevue/multiselect'
import RadioButton from 'primevue/radiobutton'
import ResourceKindFormSelect from '@/components/common/ResourceKindFormSelect.vue'
import TabDialog from '@/components/common/TabDialog.vue'
import ToggleSwitch from 'primevue/toggleswitch'
import { useSubscriptionDialog } from '@/composables/useSubscriptionDialog'

const props = defineProps({
  visible: Boolean,
  mediaId: String,
  seasonNumber: {
    type: Number,
    default: null,
  },
  detail: {
    type: Object,
    default: null,
  },
  initialState: {
    type: Object,
    default: null,
  },
  initialConfig: {
    type: Object,
    default: null,
  },
  catalogs: {
    type: Object,
    default: null,
  },
})

const emit = defineEmits(['update:visible', 'saved', 'command-submitted'])

const {
  saving,
  loadingInitialData,
  loadingDirs,
  directoryOptions,
  siteOptions,
  filterOptions,
  qualityProfileDropdownOptions,
  qualityProfileSelection,
  tagOptions,
  resolutionOptions,
  sourceOptions,
  codecOptions,
  hdrOptions,
  audioCodecOptions,
  audioChannelOptions,
  colorDepthOptions,
  upgradeLockModeOptions,
  form,
  filterMode,
  targetFilterMode,
  filterModeOptions,
  activeTab,
  subscriptionDialogTabs,
  runAfterSave,
  canRunAfterSave,
  primarySaveLabel,
  showBaseFilterPreset,
  showTargetBasePreset,
  showCustomFilters,
  showCustomTargetFilters,
  targetFilterConfigId,
  upgradeMode,
  subscriptionModeOptions,
  showAdvancedUpgradeSettings,
  subscriptionLabel,
  followLabel,
  onFilterModeChange,
  onFilterPresetSelectionChange,
  onTargetFilterModeChange,
  onTargetFilterPresetSelectionChange,
  onQualityProfileChange,
  syncUpgradePolicyFromMode,
  save,
  addUnmatchedRule,
  removeUnmatchedRule,
} = useSubscriptionDialog(props, emit)
</script>
