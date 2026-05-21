<template>
  <section class="ui-section w-full max-w-layout mx-auto">
    <div class="ui-page-header">
      <div class="ui-page-copy">
        <h1 class="text-heading font-semibold text-color">{{ $t('scheduler.title') }}</h1>
        <p class="text-muted text-caption">{{ $t('scheduler.description') }}</p>
      </div>
    </div>

    <section class="ui-panel p-container flex flex-col gap-item">
      <div class="text-title font-bold h-7 flex items-center">{{ $t('scheduler.jobList') }}</div>

      <div v-if="lastError" class="flex items-center gap-item px-item py-item border border-separator rounded-container text-status-error bg-surface">
        <i class="pi pi-exclamation-triangle text-caption" />
        <span class="text-caption">{{ lastError }}</span>
      </div>

      <div v-if="loading && !jobs.length" class="ui-tab-empty">
        <EmptyState :border="false" :description="$t('scheduler.loadingJobs')" image="pi pi-spin pi-spinner" />
      </div>

      <div v-else-if="!jobs.length" class="ui-tab-empty">
        <EmptyState :border="false" :description="$t('scheduler.noJobs')" image="pi pi-calendar-times" />
      </div>

      <div v-else class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-2 gap-container ui-settings-grid-regular">
        <article
          v-for="job in jobs"
          :key="job.id"
          class="ui-settings-card h-full"
        >
          <div class="ui-settings-card-header">
            <div class="ui-settings-card-copy">
              <div class="flex items-center gap-tight min-w-0">
                <h4 class="m-none text-body font-semibold text-color truncate">{{ formatJobName(job) }}</h4>
                <Button
                  v-tooltip.top="formatJobDescription(job)"
                  icon="pi pi-info-circle"
                  severity="secondary"
                  text
                  rounded
                  size="small"
                  class="shrink-0"
                  :aria-label="$t('scheduler.jobDescriptionAria', { name: formatJobName(job) })"
                />
              </div>
              <p class="m-none text-caption text-muted">{{ formatSourceLabel(job) }}</p>
            </div>
            <div class="ui-settings-card-meta">
              <AppTag :label="job.source_type === 'addon' ? $t('scheduler.addonJob') : $t('scheduler.systemJob')" :tone="job.source_type === 'addon' ? 'accent' : 'default'" />
              <AppTag :label="formatTriggerLabel(job)" tone="default" />
            </div>
          </div>

          <div class="ui-settings-card-body">
            <div class="flex flex-col gap-item text-caption text-muted">
              <p class="info-item m-none">
                <strong class="font-semibold">{{ $t('scheduler.nextRun') }}</strong>{{ formatDateTime(job.next_run_time) }}
              </p>
              <p class="info-item m-none">
                <strong class="font-semibold">{{ $t('scheduler.latestRun') }}</strong>
                <template v-if="job.latest_action">
                  <span v-tooltip.top="formatAbsoluteDateTime(job.latest_action.ts)">
                    {{ formatRelativeTime(job.latest_action.ts) }}
                  </span>
                  <span v-if="job.latest_action.duration_ms != null" class="ml-inline">
                    · {{ formatDuration(job.latest_action.duration_ms) }}
                  </span>
                </template>
                <template v-else>{{ $t('scheduler.noRunRecords') }}</template>
              </p>
              <p v-if="job.latest_action?.error" class="info-item m-none text-status-error break-words">
                <strong class="font-semibold">{{ $t('scheduler.error') }}</strong>{{ job.latest_action.error }}
              </p>
              <p v-if="job.config_scope === 'addon'" class="info-item m-none break-words">
                <strong class="font-semibold">{{ $t('scheduler.configSource') }}</strong>{{ formatConfigSource(job) }}
              </p>
            </div>
          </div>

          <div class="ui-settings-card-actions">
            <Button
              :label="$t('scheduler.triggerManually')"
              severity="secondary"
              outlined
              size="small"
              :loading="triggeringJobId === job.id"
              @click="triggerJob(job)"
            />
            <Button
              v-if="canOpenConfig(job)"
              :label="job.id === 'media_server_sync_incremental_sweep' ? $t('common.edit') : $t('scheduler.goToConfig')"
              severity="secondary"
              outlined
              size="small"
              @click="openConfig(job)"
            />
            <Button
              v-if="job.editable_in_scheduler"
              :label="$t('common.edit')"
              severity="secondary"
              outlined
              size="small"
              @click="openIntervalDialog(job)"
            />
            <Button
              :label="$t('scheduler.viewHistory')"
              severity="secondary"
              outlined
              size="small"
              @click="openHistoryDialog(job)"
            />
          </div>
        </article>
      </div>
    </section>

    <ConfigDialog
      v-model="intervalDialogVisible"
      :title="$t('common.edit')"
      size="sm"
    >
      <div class="ui-dialog-section">
        <label for="scheduler-interval-dialog" class="ui-dialog-item-title block">{{ $t('scheduler.intervalSeconds') }}</label>
        <InputNumber
          v-model="editingIntervalValue"
          input-id="scheduler-interval-dialog"
          class="w-full"
          :min="1"
          :use-grouping="false"
        />
      </div>
      <template #footer>
        <Button :label="$t('common.cancel')" severity="secondary" text @click="closeIntervalDialog" />
        <Button
          :label="$t('common.save')"
          icon="pi pi-save"
          :loading="savingJobId === editingIntervalJobId"
          :disabled="!canSaveEditingInterval"
          @click="saveEditingInterval"
        />
      </template>
    </ConfigDialog>

    <ConfigDialog
      v-model="historyDialogVisible"
      :title="historyDialogTitle"
      size="lg"
      :scroll="false"
    >
      <SchedulerJobHistoryList
        v-if="historyDialogJobId"
        :job-id="historyDialogJobId"
      />
    </ConfigDialog>
  </section>
</template>

<script setup>
import Button from 'primevue/button'
import InputNumber from 'primevue/inputnumber'
import AppTag from '@/components/common/AppTag.vue'
import ConfigDialog from '@/components/common/ConfigDialog.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import SchedulerJobHistoryList from '@/components/SchedulerJobHistoryList.vue'
import { formatAbsoluteDateTime, formatRelativeTime } from '@/utils/formatters'
import { useSchedulerJobsPage } from '@/composables/useSchedulerJobsPage'

const {
  loading,
  jobs,
  lastError,
  savingJobId,
  triggeringJobId,
  intervalDialogVisible,
  editingIntervalJobId,
  editingIntervalValue,
  historyDialogVisible,
  historyDialogJobId,
  formatJobName,
  formatJobDescription,
  formatSourceLabel,
  formatTriggerLabel,
  formatDateTime,
  formatDuration,
  formatConfigSource,
  canOpenConfig,
  openIntervalDialog,
  closeIntervalDialog,
  canSaveEditingInterval,
  historyDialogTitle,
  openHistoryDialog,
  openConfig,
  saveEditingInterval,
  triggerJob,
} = useSchedulerJobsPage()
</script>
