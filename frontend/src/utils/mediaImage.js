import { useMediaImageSettingsStore } from '@/stores/media-image-settings'

const DOUBAN_IMAGE_HOSTS = new Set([
  'qnmob1.doubanio.com',
  'qnmob2.doubanio.com',
  'qnmob3.doubanio.com',
  'img1.doubanio.com',
  'img2.doubanio.com',
  'img3.doubanio.com',
  'img9.doubanio.com',
])

const TMDB_IMAGE_HOST = 'image.tmdb.org'

function normalizeMediaImageUrl(url) {
  if (!url) return ''
  return String(url).startsWith('/')
    ? `https://image.tmdb.org/t/p/original${url}`
    : String(url)
}

function shouldProxyMediaImage(url) {
  try {
    const settings = useMediaImageSettingsStore()
    const parsed = new URL(url)
    const hostname = parsed.hostname.toLowerCase()
    if (hostname === TMDB_IMAGE_HOST) return settings.tmdbProxyImages
    if (DOUBAN_IMAGE_HOSTS.has(hostname)) return settings.doubanProxyImages
    return false
  } catch {
    return false
  }
}

export function resolveMediaImageUrl(url) {
  const normalizedUrl = normalizeMediaImageUrl(url)
  if (!normalizedUrl) return ''
  if (!shouldProxyMediaImage(normalizedUrl)) return normalizedUrl
  return `/api/v1/media/image?url=${encodeURIComponent(normalizedUrl)}`
}
