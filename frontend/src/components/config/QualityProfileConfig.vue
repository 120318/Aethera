<template>
  <div class="pb-container">
    <div
      v-if="profiles.length > 0"
      class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-container ui-settings-grid-tall"
    >
      <div v-for="profile in profiles" :key="profile.id" class="ui-settings-card h-full">
        <div class="ui-settings-card-header">
          <div class="ui-settings-card-copy">
            <h4 class="m-none text-body font-semibold text-color">{{ profile.name || $t('settings.quality.unnamedProfile') }}</h4>
          </div>
          <div class="ui-settings-card-meta">
            <AppTag v-if="profile.active_default" :value="$t('settings.quality.default')" tone="accent" />
          </div>
        </div>

        <div class="ui-settings-card-body">
          <div class="flex flex-col gap-inline text-caption text-muted">
            <p class="m-none">
              <strong class="font-semibold">{{ $t('settings.quality.priority') }}</strong>
              {{ formatDimensionSummary(profile.ranking?.dimension_order) }}
            </p>
            <p class="m-none">
              <strong class="font-semibold">{{ $t('settings.quality.topPreference') }}</strong>
              {{ formatTopValues(profile.ranking) }}
            </p>
            <p class="m-none">
              <strong class="font-semibold">{{ $t('settings.quality.customScores') }}</strong>
              {{ formatTagScoreSummary(profile.tag_scores) }}
            </p>
            <p class="m-none">
              <strong class="font-semibold">{{ $t('settings.quality.minimumScore') }}</strong>
              {{ profile.min_score === 0 || profile.min_score ? profile.min_score : $t('settings.quality.unlimited') }}
            </p>
          </div>
        </div>

        <div class="ui-settings-card-actions">
          <Button :label="$t('common.edit')" severity="secondary" outlined size="small" @click="editProfile(profile)" />
          <Button :label="$t('common.delete')" severity="secondary" outlined size="small" @click="confirmDelete(profile)" />
        </div>
      </div>

      <button type="button" class="ui-settings-add-card" @click="addProfile">
        <i class="pi pi-plus text-title" aria-hidden="true"></i>
        <span class="text-body font-medium">{{ $t('settings.quality.add') }}</span>
      </button>
    </div>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-container ui-settings-grid-tall">
      <button type="button" class="ui-settings-add-card" @click="addProfile">
        <i class="pi pi-plus text-title" aria-hidden="true"></i>
        <span class="text-body font-medium">{{ $t('settings.quality.add') }}</span>
      </button>
    </div>

    <ConfigDialog v-model:visible="dialogVisible" :title="dialogTitle" size="xl" :intro="$t('settings.quality.intro')">
      <QualityProfileEditor
        v-model="currentProfile"
        :tag-options="tagOptions"
        :disabled="saving"
      />

      <template #footer>
        <Button :label="$t('common.cancel')" severity="secondary" text @click="dialogVisible = false" />
        <Button :label="$t('common.save')" severity="primary" :loading="saving" @click="saveProfile" />
      </template>
    </ConfigDialog>

    <ConfirmDialog />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import Button from 'primevue/button'
import ConfirmDialog from 'primevue/confirmdialog'
import { useConfirm } from 'primevue/useconfirm'
import AppTag from '@/components/common/AppTag.vue'
import ConfigDialog from '@/components/common/ConfigDialog.vue'
import QualityProfileEditor from '@/components/common/QualityProfileEditor.vue'
import { getTags } from '@/api/tags'
import {
  createQualityProfile,
  deleteQualityProfile,
  getQualityProfiles,
  updateQualityProfile,
} from '@/api/quality_profiles'
import { useNotificationStore } from '@/stores/notification'
import { createEmptyQualityProfile, normalizeQualityProfile } from '@/composables/qualityProfileSupport'
import { buildQualityRankingDimensionOptions } from '@/composables/qualityRankingSupport'

const confirm = useConfirm()
const notification = useNotificationStore()
const { t } = useI18n()

const profiles = ref([])
const tags = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('')
const dialogMode = ref('add')
const saving = ref(false)
const currentProfile = ref(createEmptyQualityProfile())

const tagOptions = computed(() => (
  tags.value.map((tag) => ({ label: tag.name, value: tag.id }))
))
const qualityRankingDimensionOptions = computed(() => buildQualityRankingDimensionOptions(t))

onMounted(async () => {
  await Promise.all([loadProfiles(), loadTags()])
})

async function loadProfiles() {
  try {
    profiles.value = (await getQualityProfiles()) || []
  } catch (error) {
    notification.error(t('settings.quality.loadFailed'))
    console.error(t('settings.quality.loadFailed'), error)
  }
}

async function loadTags() {
  try {
    tags.value = (await getTags()) || []
  } catch (error) {
    console.error(t('settings.quality.loadTagsFailed'), error)
  }
}

function addProfile() {
  dialogMode.value = 'add'
  dialogTitle.value = t('settings.quality.addTitle')
  currentProfile.value = createEmptyQualityProfile()
  dialogVisible.value = true
}

function editProfile(profile) {
  dialogMode.value = 'edit'
  dialogTitle.value = t('settings.quality.editTitle')
  currentProfile.value = normalizeQualityProfile(profile)
  dialogVisible.value = true
}

async function saveProfile() {
  if (!currentProfile.value.name?.trim()) {
    notification.warn(t('settings.quality.nameRequired'))
    return
  }
  saving.value = true
  try {
    const payload = normalizeQualityProfile(currentProfile.value)
    if (dialogMode.value === 'add') {
      await createQualityProfile(payload)
      notification.success(t('settings.quality.added'))
    } else {
      await updateQualityProfile(payload.id, payload)
      notification.success(t('settings.quality.updated'))
    }
    dialogVisible.value = false
    await loadProfiles()
  } catch (error) {
    notification.error(t('settings.quality.saveFailed'))
    console.error(t('settings.quality.saveFailed'), error)
  } finally {
    saving.value = false
  }
}

function confirmDelete(profile) {
  confirm.require({
    message: t('settings.quality.deleteMessage', { name: profile.name || t('settings.quality.unnamedProfile') }),
    header: t('settings.quality.deleteHeader'),
    acceptLabel: t('common.delete'),
    rejectLabel: t('common.cancel'),
    rejectProps: {
      severity: 'secondary',
      outlined: true,
    },
    acceptProps: {
      severity: 'primary',
    },
    accept: async () => {
      try {
        await deleteQualityProfile(profile.id)
        notification.success(t('settings.quality.deleted'))
        await loadProfiles()
      } catch (error) {
        notification.error(t('settings.quality.deleteFailed'))
        console.error(t('settings.quality.deleteFailed'), error)
      }
    },
  })
}

function formatDimensionSummary(order) {
  return (order || []).map((key) => qualityRankingDimensionOptions.value.find((item) => item.key === key)?.label || key).join(' > ')
}

function formatTopValues(ranking) {
  if (!ranking) return t('settings.quality.notConfigured')
  return [
    ranking.resolution?.[0],
    ranking.source?.[0],
    ranking.hdr_type?.[0],
  ].filter(Boolean).join(' / ')
}

function formatTagScoreSummary(tagScores) {
  const entries = Object.entries(tagScores || {})
  if (entries.length === 0) return t('settings.quality.none')
  return t('settings.quality.ruleCount', { count: entries.length })
}
</script>
