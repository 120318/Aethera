<template>
  <div class="ui-settings-card h-full">
    <ConfirmDialog />
    <div class="ui-settings-card-header">
      <div class="ui-settings-card-copy">
        <h4 class="m-none text-body font-semibold text-color">{{ $t('settings.addons.notifications.title') }}</h4>
        <p class="m-none text-caption text-muted">{{ $t('settings.addons.notifications.description') }}</p>
      </div>
      <div class="ui-settings-card-meta">
        <ToggleSwitch
          :key="toggleKey"
          :model-value="notificationsConfig.enabled"
          input-id="ext-notifications-enabled"
          @update:model-value="handleCardToggle"
        />
      </div>
    </div>

    <div class="ui-settings-card-body">
      <p class="m-none text-caption text-muted">{{ $t('settings.addons.notifications.count', { count: enabledChannelCount }) }}</p>
    </div>

    <div class="ui-settings-card-actions">
      <Button :label="$t('common.edit')" severity="secondary" outlined size="small" @click="openDialog" />
    </div>

    <ConfigDialog
      v-model="dialogVisible"
      :title="$t('settings.addons.notifications.editTitle')"
      size="lg"
      :intro="$t('settings.addons.notifications.intro')"
    >
      <div class="grid grid-cols-1 md:grid-cols-2 gap-container ui-settings-grid-regular">
        <div v-for="channel in notificationsConfig.channels" :key="channel.id" class="ui-settings-card h-full">
          <div class="ui-settings-card-header">
            <div class="ui-settings-card-copy">
              <h4 class="m-none text-body font-semibold text-color">{{ channel.name || $t('settings.addons.notifications.unnamedChannel') }}</h4>
              <p class="m-none text-caption text-muted">{{ channel.type }}</p>
            </div>
            <div class="ui-settings-card-meta">
              <ToggleSwitch
                :model-value="channel.enabled"
                :input-id="`notification-channel-enabled-${channel.id}`"
                @update:model-value="updateChannelEnabled(channel, $event)"
              />
            </div>
          </div>

          <div class="ui-settings-card-body">
            <div class="flex flex-col gap-inline text-caption text-muted">
              <p class="m-none"><strong class="font-semibold">{{ $t('settings.addons.notifications.target') }}</strong> {{ channel.chat_id || $t('common.unset') }}</p>
              <p class="m-none"><strong class="font-semibold">{{ $t('settings.addons.notifications.eventPatterns') }}</strong> {{ formatNotificationItems(channel.event_patterns, $t('common.unset')) }}</p>
              <p class="m-none"><strong class="font-semibold">{{ $t('settings.addons.notifications.levels') }}</strong> {{ formatNotificationItems(channel.levels, $t('common.unset')) }}</p>
            </div>
          </div>

          <div class="ui-settings-card-actions">
            <Button :label="$t('common.edit')" severity="primary" size="small" @click="openChannelDialog(channel)" />
            <Button :label="$t('common.delete')" severity="secondary" outlined size="small" @click="confirmDeleteChannel(channel)" />
          </div>
        </div>

        <button type="button" class="ui-settings-add-card" @click="openChannelDialog()">
          <i class="pi pi-plus text-title" aria-hidden="true"></i>
          <span class="text-body font-medium">{{ $t('settings.addons.notifications.addChannel') }}</span>
        </button>
      </div>
    </ConfigDialog>

    <ConfigDialog
      v-model="channelDialogVisible"
      :title="editingChannelId ? $t('settings.addons.notifications.editChannel') : $t('settings.addons.notifications.addChannelTitle')"
      size="lg"
    >
      <div class="flex flex-col gap-container">
        <div class="ui-dialog-grid">
          <div class="ui-dialog-section">
            <label class="ui-dialog-item-title block">{{ $t('settings.addons.auth.name') }}</label>
            <InputText v-model="channelForm.name" class="w-full" :placeholder="$t('settings.addons.notifications.namePlaceholder')" />
          </div>
          <div class="ui-dialog-section">
            <label class="ui-dialog-item-title block">{{ $t('settings.addons.notifications.channelType') }}</label>
            <Select v-model="channelForm.type" :options="channelTypeOptions" option-label="label" option-value="value" class="w-full" />
          </div>
        </div>

        <template v-if="channelForm.type === 'telegram'">
          <div class="ui-dialog-grid">
            <div class="ui-dialog-section">
              <label class="ui-dialog-item-title block">{{ $t('settings.addons.notifications.chatId') }}</label>
              <InputText v-model="channelForm.chat_id" class="w-full" />
            </div>
            <div class="ui-dialog-section">
              <label class="ui-dialog-item-title block">{{ $t('settings.addons.notifications.botToken') }}</label>
              <SecretInput v-model="channelForm.bot_token" class="w-full" />
            </div>
          </div>
        </template>

        <div class="ui-dialog-grid">
          <div class="ui-dialog-section">
            <div class="flex items-center gap-micro mb-item">
              <label class="ui-dialog-item-title">{{ $t('settings.addons.notifications.eventRules') }}</label>
              <Button
                v-tooltip.top="$t('settings.addons.notifications.eventRulesHelp')"
                icon="pi pi-info-circle"
                severity="secondary"
                variant="text"
                size="small"
                :aria-label="$t('settings.addons.notifications.eventRulesHelpLabel')"
              />
            </div>
            <MultiSelect
              v-model="channelForm.event_patterns"
              :options="eventPatternOptions"
              option-label="label"
              option-value="value"
              display="chip"
              filter
              :max-selected-labels="3"
              class="w-full"
              :placeholder="$t('settings.addons.notifications.eventRulesPlaceholder')"
            />
          </div>

          <div class="ui-dialog-section">
            <label class="ui-dialog-item-title block">{{ $t('settings.addons.notifications.levelFilter') }}</label>
            <MultiSelect
              v-model="channelForm.levels"
              :options="levelOptions"
              option-label="label"
              option-value="value"
              display="chip"
              :placeholder="$t('settings.addons.notifications.emptyMeansNoFilter')"
              class="w-full"
            />
          </div>
        </div>
      </div>

      <template #footer>
        <Button
          v-if="channelForm.type === 'telegram'"
          :label="$t('settings.addons.notifications.sendTestMessage')"
          icon="pi pi-send"
          severity="secondary"
          outlined
          :loading="testingConnection"
          @click="testChannelConnection"
        />
        <Button :label="$t('common.cancel')" severity="secondary" outlined @click="closeChannelDialog" />
        <Button :label="$t('settings.addons.notifications.saveChannel')" severity="primary" @click="saveChannel" />
      </template>
    </ConfigDialog>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import Button from 'primevue/button'
import ConfirmDialog from 'primevue/confirmdialog'
import InputText from 'primevue/inputtext'
import MultiSelect from 'primevue/multiselect'
import Select from 'primevue/select'
import ToggleSwitch from 'primevue/toggleswitch'
import { useConfirm } from 'primevue/useconfirm'

import { saveAddons, testServiceConnection } from '@/api/config'
import ConfigDialog from '@/components/common/ConfigDialog.vue'
import SecretInput from '@/components/common/SecretInput.vue'
import { EVENT_TYPE_MAP, resolveEventTypeMeta } from '@/constants/eventTypes'
import {
  assignNotificationChannelForm,
  cloneNotificationChannel,
  cloneNotificationChannels,
  createEmptyNotificationChannel,
  DEFAULT_NOTIFICATION_EVENT_PATTERNS,
  formatNotificationItems,
} from '@/components/config/addons/notificationChannelsSupport'
import { useNotificationStore } from '@/stores/notification'

const props = defineProps({
  config: {
    type: Object,
    required: true,
  },
})

const notification = useNotificationStore()
const confirm = useConfirm()
const { t } = useI18n()
const dialogVisible = ref(false)
const channelDialogVisible = ref(false)
const editingChannelId = ref('')
const toggleKey = ref(0)
const testingConnection = ref(false)

const channelTypeOptions = computed(() => [
  { label: t('settings.addons.notifications.telegram'), value: 'telegram' },
])

const levelOptions = computed(() => [
  { label: t('backendLogs.levels.info'), value: 'info' },
  { label: t('backendLogs.levels.warning'), value: 'warning' },
  { label: t('backendLogs.levels.error'), value: 'error' },
])

const channelForm = reactive(createEmptyNotificationChannel())

const eventPatternOptions = computed(() => {
  const options = [
    ...eventPatternScopeOptions(),
    ...eventTypeOptions(),
  ]
  const knownValues = new Set(options.map((option) => option.value))
  const customOptions = channelForm.event_patterns
    .filter((value) => value && !knownValues.has(value))
    .map((value) => ({ label: `${t('settings.addons.notifications.customEventRule')} · ${value}`, value }))
  return [...options, ...customOptions]
})

function ensureNotificationsConfig() {
  if (!props.config.addons.notifications) {
    props.config.addons.notifications = {
      enabled: false,
      channels: [],
    }
  }
  if (!Array.isArray(props.config.addons.notifications.channels)) {
    props.config.addons.notifications.channels = []
  }
}

ensureNotificationsConfig()

const notificationsConfig = computed(() => props.config.addons.notifications)

const enabledChannelCount = computed(() => notificationsConfig.value.channels.filter((channel) => channel.enabled).length)

function resetChannelForm() {
  assignNotificationChannelForm(channelForm, createEmptyNotificationChannel())
}

function openDialog() {
  dialogVisible.value = true
}

function openChannelDialog(channel = null) {
  if (channel) {
    editingChannelId.value = channel.id
    assignNotificationChannelForm(channelForm, channel)
  } else {
    editingChannelId.value = ''
    resetChannelForm()
  }
  channelDialogVisible.value = true
}

function closeChannelDialog() {
  channelDialogVisible.value = false
}

async function persistAddons() {
  const savedAddons = await saveAddons(props.config.addons)
  if (savedAddons?.notifications) {
    props.config.addons.notifications = savedAddons.notifications
  }
}

async function handleCardToggle(enabled) {
  const previous = notificationsConfig.value.enabled
  notificationsConfig.value.enabled = !!enabled
  try {
    await persistAddons()
    notification.success(enabled ? t('settings.addons.notifications.enabled') : t('settings.addons.notifications.disabled'))
    if (enabled) {
      openDialog()
    }
  } catch {
    notificationsConfig.value.enabled = previous
    toggleKey.value += 1
    notification.error(t('settings.addons.notifications.saveFailed'))
  }
}

async function updateChannelEnabled(channel, enabled) {
  const channelIndex = notificationsConfig.value.channels.findIndex((item) => item.id === channel.id)
  if (channelIndex < 0) {
    return
  }

  const previousChannel = cloneNotificationChannel(notificationsConfig.value.channels[channelIndex])

  notificationsConfig.value.channels.splice(channelIndex, 1, {
    ...notificationsConfig.value.channels[channelIndex],
    enabled,
  })

  try {
    await persistAddons()
    notification.success(enabled ? t('settings.addons.notifications.channelEnabled') : t('settings.addons.notifications.channelDisabled'))
  } catch {
    notificationsConfig.value.channels.splice(channelIndex, 1, previousChannel)
    notification.error(t('settings.addons.notifications.channelStatusSaveFailed'))
  }
}

async function saveChannel() {
  const nextChannel = {
    id: channelForm.id || createEmptyNotificationChannel().id,
    type: channelForm.type,
    name: channelForm.name.trim(),
    enabled: channelForm.enabled,
    event_patterns: [...channelForm.event_patterns].filter(Boolean),
    levels: [...channelForm.levels],
    bot_token: channelForm.bot_token.trim(),
    chat_id: channelForm.chat_id.trim(),
  }

  if (!nextChannel.name) {
    notification.warn(t('settings.addons.notifications.channelNameRequired'))
    return
  }
  if (nextChannel.type === 'telegram' && (!nextChannel.bot_token || !nextChannel.chat_id)) {
    notification.warn(t('settings.addons.notifications.telegramRequired'))
    return
  }
  if (!nextChannel.event_patterns.length) {
    nextChannel.event_patterns = [...DEFAULT_NOTIFICATION_EVENT_PATTERNS]
  }

  const channelIndex = notificationsConfig.value.channels.findIndex((item) => item.id === editingChannelId.value)
  const previousChannels = cloneNotificationChannels(notificationsConfig.value.channels)

  if (channelIndex >= 0) {
    notificationsConfig.value.channels.splice(channelIndex, 1, nextChannel)
  } else {
    notificationsConfig.value.channels.push(nextChannel)
  }

  try {
    await persistAddons()
    notification.success(editingChannelId.value ? t('settings.addons.notifications.channelUpdated') : t('settings.addons.notifications.channelAdded'))
    closeChannelDialog()
  } catch {
    notificationsConfig.value.channels.splice(0, notificationsConfig.value.channels.length, ...previousChannels)
    notification.error(t('settings.addons.notifications.channelSaveFailed'))
  }
}

function eventPatternScopeOptions() {
  return [
    { value: 'follow.*', label: t('settings.addons.notifications.eventScopeFollow') },
    { value: 'download.*', label: t('settings.addons.notifications.eventScopeDownload') },
    { value: 'media.*', label: t('settings.addons.notifications.eventScopeMedia') },
    { value: 'subscription.ended.*', label: t('settings.addons.notifications.eventScopeSubscriptionEnded') },
    { value: 'media_server_sync.*', label: t('settings.addons.notifications.eventScopeMediaServerSync') },
    { value: 'danmu.*', label: t('settings.addons.notifications.eventScopeDanmu') },
    { value: 'library.*', label: t('settings.addons.notifications.eventScopeLibrary') },
  ].map((option) => ({
    ...option,
    label: `${t('settings.addons.notifications.eventScopeGroup')} · ${option.label}`,
  }))
}

function eventTypeOptions() {
  return Object.entries(EVENT_TYPE_MAP)
    .filter(([domain]) => !['addon', 'notification'].includes(domain))
    .flatMap(([domain, actions]) => Object.keys(actions).map((action) => `${domain}.${action}`))
    .map((value) => ({
      label: `${t('settings.addons.notifications.eventTypeGroup')} · ${eventTypeLabel(value)}`,
      value,
    }))
}

function eventTypeLabel(value) {
  const eventMeta = resolveEventTypeMeta(value)
  if (!eventMeta) return value
  const subject = eventMeta.subjectKey ? t(eventMeta.subjectKey) : ''
  const action = eventMeta.actionKey ? t(eventMeta.actionKey) : ''
  return `${subject} ${action}`.trim() || value
}

async function testChannelConnection() {
  const botToken = channelForm.bot_token.trim()
  const chatId = channelForm.chat_id.trim()
  if (!botToken || !chatId) {
    notification.warn(t('settings.addons.notifications.telegramRequired'))
    return
  }

  testingConnection.value = true
  try {
    await testServiceConnection(
      {
        type: 'telegram',
        config: {
          type: 'telegram',
          bot_token: botToken,
          chat_id: chatId,
        },
      },
      { suppressErrorNotification: true },
    )
    notification.success(t('settings.addons.notifications.testMessageSent'))
  } catch (error) {
    console.error(t('settings.addons.notifications.testMessageFailed'), error)
    notification.error(error?.message || t('settings.addons.notifications.testMessageFailed'))
  } finally {
    testingConnection.value = false
  }
}

function confirmDeleteChannel(channel) {
  confirm.require({
    message: t('settings.addons.notifications.deleteMessage', { name: channel.name || t('settings.addons.notifications.unnamedChannel') }),
    header: t('settings.downloader.deleteHeader'),
    acceptLabel: t('settings.downloader.confirmDelete'),
    rejectLabel: t('common.cancel'),
    rejectProps: {
      severity: 'secondary',
      outlined: true,
    },
    acceptProps: {
      severity: 'primary',
    },
    accept: async () => {
      await deleteChannel(channel)
    },
  })
}

async function deleteChannel(channel) {
  const previousChannels = cloneNotificationChannels(notificationsConfig.value.channels)

  notificationsConfig.value.channels.splice(
    0,
    notificationsConfig.value.channels.length,
    ...notificationsConfig.value.channels.filter((item) => item.id !== channel.id)
  )

  try {
    await persistAddons()
    if (editingChannelId.value === channel.id) {
      closeChannelDialog()
    }
    notification.success(t('settings.addons.notifications.channelDeleted'))
  } catch {
    notificationsConfig.value.channels.splice(0, notificationsConfig.value.channels.length, ...previousChannels)
    notification.error(t('settings.addons.notifications.channelDeleteFailed'))
  }
}
</script>
