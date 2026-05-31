const platformAliases = new Map([
  ['qq', 'tencent'],
  ['tencent', 'tencent'],
  ['txvideo', 'tencent'],
  ['腾讯视频', 'tencent'],
  ['腾讯视频平台', 'tencent'],
  ['tencent video', 'tencent'],
  ['tencent video platform', 'tencent'],
  ['iqiyi', 'iqiyi'],
  ['爱奇艺', 'iqiyi'],
  ['youku', 'youku'],
  ['优酷', 'youku'],
  ['优酷视频', 'youku'],
  ['bilibili', 'bilibili'],
  ['哔哩哔哩', 'bilibili'],
  ['mgtv', 'mgtv'],
  ['mango tv', 'mgtv'],
  ['芒果tv', 'mgtv'],
  ['amazon prime video', 'amazon_prime_video'],
  ['amazon prime video with ads', 'amazon_prime_video'],
  ['amazon prime video free with ads', 'amazon_prime_video'],
  ['prime video', 'amazon_prime_video'],
])

const platformDisplayNames = new Map([
  ['amazon_prime_video', 'Prime Video'],
])

function normalizePlatformToken(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[·•|/\\_-]+/g, ' ')
    .replace(/\s+/g, ' ')
}

function compactPlatformToken(value) {
  return normalizePlatformToken(value).replace(/\s+/g, '')
}

export function platformCanonicalKey(platform) {
  const values = [platform?.id, platform?.name]
  for (const value of values) {
    const normalized = normalizePlatformToken(value)
    if (!normalized) continue
    if (platformAliases.has(normalized)) return platformAliases.get(normalized)
    const compact = compactPlatformToken(value)
    if (platformAliases.has(compact)) return platformAliases.get(compact)
  }
  const fallback = values.map((value) => normalizePlatformToken(value)).find(Boolean)
  return fallback || ''
}

export function dedupePlatforms(platforms, limit = Infinity) {
  if (!Array.isArray(platforms)) return []
  const seen = new Set()
  const deduped = []
  for (const platform of platforms) {
    const key = platformCanonicalKey(platform)
    if (!key || seen.has(key)) continue
    seen.add(key)
    deduped.push(platform)
    if (deduped.length >= limit) break
  }
  return deduped
}

export function platformDisplayName(platform) {
  const key = platformCanonicalKey(platform)
  return platformDisplayNames.get(key) || platform?.name || ''
}
