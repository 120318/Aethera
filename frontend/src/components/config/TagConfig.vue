<template>
  <div class="pb-container">
    <!-- Tag list -->
    <div
      v-if="tags && tags.length > 0"
      class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-container ui-settings-grid-regular"
    >
      <div v-for="tag in tags" :key="tag.id" class="ui-settings-card h-full">
        <div class="ui-settings-card-header">
          <div class="ui-settings-card-copy">
            <h4 class="m-none text-body font-semibold text-color truncate">{{ tag.name || $t('settings.tag.unnamed') }}</h4>
          </div>
          <div class="ui-settings-card-meta">
            <AppTag :value="$t('settings.tag.tag')" tone="accent" />
          </div>
        </div>

        <div class="ui-settings-card-body">
          <div class="flex flex-col gap-inline text-caption text-muted">
            <p v-if="tag.include_keywords?.length" class="m-none">
              <strong class="font-semibold">{{ $t('settings.tag.include') }}</strong> {{ tag.include_keywords.join(', ') }}
            </p>
            <p v-if="tag.exclude_keywords?.length" class="m-none">
              <strong class="font-semibold">{{ $t('settings.tag.exclude') }}</strong> {{ tag.exclude_keywords.join(', ') }}
            </p>
            <p v-if="tag.regex" class="m-none">
              <strong class="font-semibold">{{ $t('settings.tag.regex') }}</strong> <code class="bg-emphasis p-inline rounded">{{ tag.regex }}</code>
            </p>
            <p
              v-if="!tag.include_keywords?.length && !tag.exclude_keywords?.length && !tag.regex"
              class="m-none"
            >
              <strong class="font-semibold">{{ $t('settings.tag.rules') }}</strong> {{ $t('settings.tag.noRules') }}
            </p>
          </div>
        </div>

        <div class="ui-settings-card-actions">
          <Button :label="$t('common.edit')" severity="secondary" outlined size="small" @click="editTag(tag)" />
          <Button :label="$t('common.delete')" severity="secondary" outlined size="small" @click="confirmDelete(tag)" />
        </div>
      </div>

      <button type="button" class="ui-settings-add-card" @click="addTag">
        <i class="pi pi-plus text-title" aria-hidden="true"></i>
        <span class="text-body font-medium">{{ $t('common.add') }}</span>
      </button>
    </div>

    <!-- Empty state -->
    <div
      v-else
      class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-container ui-settings-grid-regular"
    >
      <button type="button" class="ui-settings-add-card" @click="addTag">
        <i class="pi pi-plus text-title" aria-hidden="true"></i>
        <span class="text-body font-medium">{{ $t('common.add') }}</span>
      </button>
    </div>

    <!-- Tag editor dialog -->
    <ConfigDialog
      v-model:visible="dialogVisible"
      :title="dialogTitle"
      size="md"
      :intro="$t('settings.tag.intro')"
    >
      <!-- Basic information -->
      <div class="ui-dialog-section">
        <label for="tag-name" class="ui-dialog-item-title block">{{ $t('settings.tag.name') }}</label>
        <InputText id="tag-name" v-model="currentTag.name" :placeholder="$t('settings.tag.namePlaceholder')" class="w-full" />
      </div>

      <div class="ui-dialog-section">
        <label class="ui-dialog-item-title block">{{ $t('settings.tag.includeKeywords') }}</label>
        <Chips
          v-model="currentTag.include_keywords"
          separator=","
          add-on-blur
          :placeholder="$t('settings.tag.includePlaceholder')"
          class="w-full"
        />
        <small class="ui-dialog-help">{{ $t('settings.tag.includeHelp') }}</small>
      </div>

      <div class="ui-dialog-section">
        <label class="ui-dialog-item-title block">{{ $t('settings.tag.excludeKeywords') }}</label>
        <Chips
          v-model="currentTag.exclude_keywords"
          separator=","
          add-on-blur
          :placeholder="$t('settings.tag.excludePlaceholder')"
          class="w-full"
        />
        <small class="ui-dialog-help">{{ $t('settings.tag.excludeHelp') }}</small>
      </div>

      <div class="ui-dialog-section">
        <label for="tag-regex" class="ui-dialog-item-title block">{{ $t('settings.tag.regexLabel') }}</label>
        <InputText id="tag-regex" v-model="currentTag.regex" :placeholder="$t('settings.tag.regexPlaceholder')" class="w-full" />
        <small class="ui-dialog-help">{{ $t('settings.tag.regexHelp') }}</small>
      </div>
      <template #footer>
        <Button :label="$t('common.cancel')" severity="secondary" text @click="dialogVisible = false" />
        <Button :label="$t('common.save')" severity="primary" :loading="saving" @click="saveTag" />
      </template>
    </ConfigDialog>

    <ConfirmDialog />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import Button from 'primevue/button';
import InputText from 'primevue/inputtext';
import Chips from 'primevue/chips';
import ConfirmDialog from 'primevue/confirmdialog';
import { useConfirm } from 'primevue/useconfirm';
import { useNotificationStore } from '@/stores/notification';
import { getTags, createTag, updateTag, deleteTag } from '@/api/tags';
import AppTag from '@/components/common/AppTag.vue';
import ConfigDialog from '@/components/common/ConfigDialog.vue';

const confirm = useConfirm()
const notification = useNotificationStore()
const { t } = useI18n()

const tags = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('')
const dialogMode = ref('add')
const saving = ref(false)
const currentTag = ref(createEmptyTag())

onMounted(loadTags)

function createEmptyTag() {
  return {
    name: '',
    include_keywords: [],
    exclude_keywords: [],
    regex: ''
  }
}

function normalizeTag(tag) {
  return {
    ...createEmptyTag(),
    ...(tag || {}),
    include_keywords: tag?.include_keywords || [],
    exclude_keywords: tag?.exclude_keywords || [],
    regex: tag?.regex || ''
  }
}

async function loadTags() {
  try {
    tags.value = await getTags()
  } catch (error) {
    notification.error(t('settings.tag.loadFailed'))
    console.error(t('settings.tag.loadFailed'), error)
  }
}

function addTag() {
  dialogVisible.value = true
  dialogTitle.value = t('settings.tag.addTitle')
  dialogMode.value = 'add'
  currentTag.value = createEmptyTag()
}

function editTag(tag) {
  dialogVisible.value = true
  dialogTitle.value = t('settings.tag.editTitle')
  dialogMode.value = 'edit'
  currentTag.value = normalizeTag(JSON.parse(JSON.stringify(tag)))
}

async function saveTag() {
  if (!currentTag.value.name) {
    notification.warn(t('settings.tag.nameRequired'))
    return
  }
  saving.value = true
  try {
    if (dialogMode.value === 'add') {
      await createTag(currentTag.value)
      notification.success(t('settings.tag.added'))
    } else {
      await updateTag(currentTag.value.id, currentTag.value)
      notification.success(t('settings.tag.updated'))
    }
    dialogVisible.value = false
    await loadTags()
  } catch (error) {
    notification.error(t('settings.tag.saveFailed'))
    console.error(t('settings.tag.saveFailed'), error)
  } finally {
    saving.value = false
  }
}

function confirmDelete(tag) {
  confirm.require({
    message: t('settings.tag.deleteMessage', { name: tag.name || t('settings.tag.unnamed') }),
    header: t('settings.quality.deleteHeader'),
    icon: 'pi pi-exclamation-triangle',
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
        await deleteTag(tag.id)
        notification.success(t('settings.tag.deleted'))
        await loadTags()
      } catch (error) {
        notification.error(t('settings.tag.deleteFailed'))
        console.error(t('settings.tag.deleteFailed'), error)
      }
    }
  })
}
</script>
