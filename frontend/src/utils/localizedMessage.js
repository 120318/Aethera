import { t } from '@/i18n'

const RAW_PARAM_TRANSLATION_KEYS = {
  error: {
    'duration mismatch': 'runtimeReasons.danmuDurationMismatch',
    'no danmu comments returned': 'runtimeReasons.danmuNotFound',
  },
}

function nestedParamsFor(params, name) {
  const targetName = name.slice(0, -4)
  const raw = params?.[`${targetName}_params`]
  if (raw && typeof raw === 'object' && !Array.isArray(raw)) return raw
  if (typeof raw !== 'string' || !raw.trim()) return {}
  try {
    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {}
  } catch {
    return {}
  }
}

export function normalizeMessageParams(params = {}) {
  const normalized = { ...params }
  Object.entries(RAW_PARAM_TRANSLATION_KEYS).forEach(([name, valueMap]) => {
    const raw = normalized[name]
    if (typeof raw !== 'string') return
    const key = valueMap[raw]
    if (!key) return
    const translated = t(key)
    if (translated && translated !== key) normalized[name] = translated
  })
  Object.entries(params || {}).forEach(([name, value]) => {
    if (!name.endsWith('_key') || typeof value !== 'string') return
    const translated = t(value, normalizeMessageParams(nestedParamsFor(params, name)))
    if (!translated || translated === value) return
    const targetName = name.slice(0, -4)
    if (!(targetName in normalized) || normalized[targetName] === '') {
      normalized[targetName] = translated
    }
  })
  return normalized
}

export function resolveLocalizedRecordMessage(record, fallback = '') {
  if (record?.status === 'failed' && record?.error_key) {
    const translated = t(record.error_key, normalizeMessageParams(record.error_params))
    if (translated && translated !== record.error_key) return translated
  }
  if (record?.message_key) {
    const translated = t(record.message_key, normalizeMessageParams(record.message_params))
    if (translated && translated !== record.message_key) return translated
  }
  return fallback
}
