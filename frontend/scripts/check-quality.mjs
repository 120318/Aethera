import fs from 'node:fs'
import path from 'node:path'

const repoRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..')
const srcRoot = path.join(repoRoot, 'src')
const localeRoot = path.join(srcRoot, 'i18n', 'locales')
const presetRoot = path.join(srcRoot, 'presets')

const componentMaxLines = 850
const composableMaxLines = 700
const sourceExtensions = ['.js', '.vue']

function walk(dir, extensions) {
  const result = []
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      result.push(...walk(full, extensions))
      continue
    }
    if (extensions.has(path.extname(entry.name))) {
      result.push(full)
    }
  }
  return result
}

function rel(file) {
  return `frontend/${path.relative(repoRoot, file).replaceAll(path.sep, '/')}`
}

function lineCount(file) {
  return fs.readFileSync(file, 'utf8').split('\n').length
}

function lineNumberAt(sample, index) {
  return sample.slice(0, index).split('\n').length
}

function isInsideDir(file, dir) {
  const relative = path.relative(dir, file)
  return relative && !relative.startsWith('..') && !path.isAbsolute(relative)
}

function frontendSourceFiles() {
  return walk(srcRoot, new Set(['.vue', '.js']))
}

function i18nCheckedSourceFiles() {
  return frontendSourceFiles().filter((file) => (
    !isInsideDir(file, localeRoot)
    && !isInsideDir(file, presetRoot)
  ))
}

function checkLineLimits(findings) {
  for (const file of walk(path.join(srcRoot, 'components'), new Set(['.vue']))) {
    const relative = rel(file)
    const lines = lineCount(file)
    if (lines > componentMaxLines) {
      findings.push(`${relative}: component has ${lines} lines, exceeding ${componentMaxLines}`)
    }
  }
  for (const file of walk(path.join(srcRoot, 'composables'), new Set(['.js']))) {
    const relative = rel(file)
    const lines = lineCount(file)
    if (lines > composableMaxLines) {
      findings.push(`${relative}: composable ${lines} sample，exceeding ${composableMaxLines}`)
    }
  }
}

function checkScriptSetup(findings) {
  for (const file of walk(path.join(srcRoot, 'components'), new Set(['.vue']))) {
    const relative = rel(file)
    const sample = fs.readFileSync(file, 'utf8')
    if (sample.includes('<script') && !sample.includes('<script setup>')) {
      findings.push(`${relative}: sample <script setup>`)
    }
  }
}

function checkToastUsage(findings) {
  const toastPattern = /useToast/
  for (const file of walk(srcRoot, new Set(['.vue', '.js']))) {
    const relative = rel(file)
    const sample = fs.readFileSync(file, 'utf8')
    if (!toastPattern.test(sample)) {
      continue
    }
    if (relative !== 'frontend/src/App.vue') {
      findings.push(`${relative}: Do not use useToast directly; use useNotificationStore`)
    }
  }
}

function checkDefineImports(findings) {
  const importPattern = /import\s*\{[^}]*\bdefineProps\b|import\s*\{[^}]*\bdefineEmits\b/
  for (const file of walk(srcRoot, new Set(['.vue']))) {
    const relative = rel(file)
    const sample = fs.readFileSync(file, 'utf8')
    if (importPattern.test(sample)) {
      findings.push(`${relative}: Do not explicitly import defineProps or defineEmits`)
    }
  }
}

function checkComponentHttpImports(findings) {
  const importPattern = /import\s+http\s+from\s+['"]@\/utils\/http['"]/
  for (const file of walk(path.join(srcRoot, 'components'), new Set(['.vue']))) {
    const relative = rel(file)
    const sample = fs.readFileSync(file, 'utf8')
    if (importPattern.test(sample)) {
      findings.push(`${relative}: sample http，sample composable sample api sample`)
    }
  }
}

function checkNonApiHttpImports(findings) {
  const importPattern = /import\s+http\s+from\s+['"]@\/utils\/http['"]/
  const targets = [
    ...walk(path.join(srcRoot, 'components'), new Set(['.vue'])),
    ...walk(path.join(srcRoot, 'composables'), new Set(['.js']))
  ]
  for (const file of targets) {
    const relative = rel(file)
    const sample = fs.readFileSync(file, 'utf8')
    if (importPattern.test(sample)) {
      findings.push(`${relative}: Non-API modules must not import the raw HTTP client; use an API or composable boundary`)
    }
  }
}

function checkInlineStyles(findings) {
  const stylePattern = /(?<!:)style="/
  for (const file of walk(path.join(srcRoot, 'components'), new Set(['.vue']))) {
    const relative = rel(file)
    const sample = fs.readFileSync(file, 'utf8')
    if (stylePattern.test(sample)) {
      findings.push(`${relative}: sample style，sample token,class sample`)
    }
  }
}

function checkArbitraryVisualValues(findings) {
  const arbitraryPattern = /\[[^\]]*(?:px|rem|vh|vw|%)\]/
  for (const file of walk(path.join(srcRoot, 'components'), new Set(['.vue']))) {
    const relative = rel(file)
    const sample = fs.readFileSync(file, 'utf8')
    if (arbitraryPattern.test(sample)) {
      findings.push(`${relative}: Do not add arbitrary Tailwind visual values; add a design token first`)
    }
  }
}

function checkEventBusPatterns(findings) {
  const forbiddenPatterns = [
    /new\s+CustomEvent\s*\(/,
    /\.dispatchEvent\s*\(/,
    /document\.addEventListener\s*\(\s*['"](?!visibilitychange['"])/
  ]
  for (const file of walk(srcRoot, new Set(['.vue', '.js']))) {
    const relative = rel(file)
    const sample = fs.readFileSync(file, 'utf8')
    if (forbiddenPatterns.some((pattern) => pattern.test(sample))) {
      findings.push(`${relative}: Do not use DOM events for cross-component communication; use a Pinia store`)
    }
  }
}

function checkMediaActionFallbacks(findings) {
  const targets = [
    path.join(srcRoot, 'composables', 'useMediaDetailSubscription.js'),
    path.join(srcRoot, 'composables', 'mediaManagementActionSupport.js'),
    path.join(srcRoot, 'composables', 'useResourceSearch.js'),
  ]
  const forbiddenPatterns = [
    { pattern: /detail\?\.title\s*\|\|\s*detail\?\.name/, message: 'sample/sample detail.title || detail.name sample' },
    { pattern: /media_year\s*:\s*.*\?\?\s*null/, message: 'sample/sample/sample year ?? null sample' },
    { pattern: /media_title\s*:\s*.*\|\|\s*['"]['"]/, message: 'sample/sample/sample' },
    { pattern: /media_title\s*:/, message: 'Media actions must send the unified media object instead of media_title' },
    { pattern: /media_year\s*:/, message: 'Media actions must send the unified media object instead of media_year' },
  ]
  for (const file of targets) {
    const relative = rel(file)
    const sample = fs.readFileSync(file, 'utf8')
    for (const { pattern, message } of forbiddenPatterns) {
      if (pattern.test(sample)) {
        findings.push(`${relative}: ${message}`)
      }
    }
  }
}

function checkMediaSeasonContracts(findings) {
  const targetFiles = [
    path.join(srcRoot, 'composables', 'useMediaDetailSubscription.js'),
    path.join(srcRoot, 'composables', 'useMediaDetailCommands.js'),
    path.join(srcRoot, 'composables', 'useSubscriptionConfigDialog.js'),
    path.join(srcRoot, 'components', 'ResourceActionTabs.vue'),
  ]
  const forbiddenPatterns = [
    { pattern: /mediaType\s*===\s*['"]movie['"][\s\S]{0,120}season_number\s*[:=]\s*(?:0|1)\b/, message: 'sample season_number=0/1 sample' },
    { pattern: /tmdb:tv:\$\{[^}]+\}:\$\{[^}]+\}/, message: 'sample TV sample media_id；sample season_number' },
    { pattern: /tmdb:tv:[^'"]+:\d+/, message: 'sample TV media_id；sample season_number' },
  ]
  for (const file of targetFiles) {
    if (!fs.existsSync(file)) {
      continue
    }
    const relative = rel(file)
    const sample = fs.readFileSync(file, 'utf8')
    for (const { pattern, message } of forbiddenPatterns) {
      if (pattern.test(sample)) {
        findings.push(`${relative}: ${message}`)
      }
    }
  }
}

async function checkI18nKeyCompleteness(findings) {
  const zh = (await import(path.join(localeRoot, 'zh-CN.js'))).default
  const en = (await import(path.join(localeRoot, 'en-US.js'))).default
  const keys = new Set()
  const patterns = [
    /\$t\(\s*['"]([^'"]+)['"]/g,
    /\bt\(\s*['"]([^'"]+)['"]/g,
  ]

  for (const file of i18nCheckedSourceFiles()) {
    const sample = fs.readFileSync(file, 'utf8')
    for (const pattern of patterns) {
      for (const match of sample.matchAll(pattern)) {
        keys.add(match[1])
      }
    }
  }

  const hasKey = (messages, key) => key.split('.').every((part) => {
    if (!messages || !Object.prototype.hasOwnProperty.call(messages, part)) {
      return false
    }
    messages = messages[part]
    return true
  })

  for (const key of [...keys].sort()) {
    if (!hasKey(zh, key)) {
      findings.push(`frontend/src/i18n/locales/zh-CN.js: sample i18n key: ${key}`)
    }
    if (!hasKey(en, key)) {
      findings.push(`frontend/src/i18n/locales/en-US.js: sample i18n key: ${key}`)
    }
  }
}

function checkI18nHardcodedStaticText(findings) {
  const brandWhitelist = new Set(['Aethera'])
  const objectLiteralWhitelist = new Set([
    'media-season-select-label',
    'disable_title',
  ])
  const staticTemplateTextPattern = />[ \t]*([A-Za-z][A-Za-z0-9 ,.:;!?()/#&+-]*)[ \t]*</g
  const objectTextPattern = /\b(label|placeholder|title|desc):\s*['"]([^'"]*[A-Za-z][^'"]*)['"]/g

  for (const file of i18nCheckedSourceFiles()) {
    const sample = fs.readFileSync(file, 'utf8')
    for (const match of sample.matchAll(staticTemplateTextPattern)) {
      const value = match[1].trim()
      if (!value || brandWhitelist.has(value)) {
        continue
      }
      findings.push(`${rel(file)}:${lineNumberAt(sample, match.index)}: sample "${value}" sample i18n`)
    }
    for (const match of sample.matchAll(objectTextPattern)) {
      const value = match[2].trim()
      if (!value || objectLiteralWhitelist.has(value)) {
        continue
      }
      findings.push(`${rel(file)}:${lineNumberAt(sample, match.index)}: ${match[1]} sample "${value}" sample i18n sample`)
    }
  }
}

function stripQuery(specifier) {
  return specifier.split('?')[0]
}

function resolveSourceSpecifier(specifier, fromFile) {
  const clean = stripQuery(specifier)
  let base = null
  if (clean.startsWith('@/')) {
    base = path.join(srcRoot, clean.slice(2))
  } else if (clean.startsWith('./') || clean.startsWith('../')) {
    base = path.resolve(path.dirname(fromFile), clean)
  } else {
    return null
  }

  const candidates = []
  if (sourceExtensions.includes(path.extname(base))) {
    candidates.push(base)
  } else {
    for (const ext of sourceExtensions) {
      candidates.push(`${base}${ext}`)
    }
    for (const ext of sourceExtensions) {
      candidates.push(path.join(base, `index${ext}`))
    }
  }

  return candidates.find((candidate) => fs.existsSync(candidate)) ?? null
}

function referencedSourceFiles(file) {
  const sample = fs.readFileSync(file, 'utf8')
  const patterns = [
    /import\s+(?:[^'"]*?\s+from\s+)?['"]([^'"]+)['"]/g,
    /import\s*\(\s*['"]([^'"]+)['"]\s*\)/g,
    /export\s+(?:\*|\{[^}]*\})\s+from\s+['"]([^'"]+)['"]/g,
  ]
  const references = []
  for (const pattern of patterns) {
    for (const match of sample.matchAll(pattern)) {
      const resolved = resolveSourceSpecifier(match[1], file)
      if (resolved) {
        references.push(resolved)
      }
    }
  }
  return references
}

function checkUnusedSourceFiles(findings) {
  const trackedDirs = ['api', 'components', 'composables', 'constants', 'stores', 'utils']
  const sourceFiles = new Set(
    trackedDirs.flatMap((dir) => walk(path.join(srcRoot, dir), new Set(sourceExtensions)))
  )
  const entryFiles = [
    path.join(srcRoot, 'main.js'),
    path.join(srcRoot, 'App.vue'),
    path.join(srcRoot, 'router', 'index.js'),
    path.join(srcRoot, 'components', 'common', 'index.js'),
    path.join(srcRoot, 'composables', 'index.js'),
  ].filter((file) => fs.existsSync(file))

  const reachable = new Set()
  const queue = [...entryFiles]
  while (queue.length > 0) {
    const file = queue.pop()
    if (reachable.has(file)) {
      continue
    }
    reachable.add(file)
    for (const referenced of referencedSourceFiles(file)) {
      queue.push(referenced)
    }
  }

  for (const file of sourceFiles) {
    if (!reachable.has(file)) {
      findings.push(`${rel(file)}: Source file is not reachable from the static frontend entry graph; delete it or wire it explicitly`)
    }
  }
}

const findings = []
checkLineLimits(findings)
checkScriptSetup(findings)
checkToastUsage(findings)
checkDefineImports(findings)
checkComponentHttpImports(findings)
checkNonApiHttpImports(findings)
checkInlineStyles(findings)
checkArbitraryVisualValues(findings)
checkEventBusPatterns(findings)
checkMediaActionFallbacks(findings)
checkMediaSeasonContracts(findings)
await checkI18nKeyCompleteness(findings)
checkI18nHardcodedStaticText(findings)
checkUnusedSourceFiles(findings)

if (findings.length > 0) {
  console.error('Frontend quality checks failed:')
  for (const finding of findings) {
    console.error(`- ${finding}`)
  }
  process.exit(1)
}

console.log('Frontend quality checks passed.')
