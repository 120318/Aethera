<template>
  <div class="file-structure-tree">
    <div v-if="rows.length === 0" class="text-caption text-muted">{{ emptyText }}</div>
    <div v-else class="file-structure-tree__rows">
      <div
        v-for="row in rows"
        :key="row.node.key"
        class="file-structure-tree__row text-caption"
        :class="row.node.type === 'directory' ? 'file-structure-tree__row--directory' : 'file-structure-tree__row--file'"
        :style="{ '--file-tree-offset': `calc(${row.level} * var(--file-tree-indent))` }"
        :role="row.node.type === 'directory' ? 'button' : undefined"
        :tabindex="row.node.type === 'directory' ? 0 : undefined"
        :aria-expanded="row.node.type === 'directory' ? isExpanded(row.node.key) : undefined"
        @click="row.node.type === 'directory' && toggle(row.node.key)"
        @keydown.enter.prevent="row.node.type === 'directory' && toggle(row.node.key)"
        @keydown.space.prevent="row.node.type === 'directory' && toggle(row.node.key)"
      >
        <div class="file-structure-tree__content">
          <i
            class="file-structure-tree__icon"
            :class="row.node.type === 'directory' ? 'pi pi-folder text-primary' : 'pi pi-file text-muted'"
          ></i>
          <span
            class="file-structure-tree__name break-all"
          >
            {{ row.node.name }}
          </span>
        </div>
        <span
          v-if="row.node.type === 'directory'"
          class="file-structure-tree__meta text-muted"
        >
          {{ t('libraryFileDetail.fileCount', { count: row.node.fileCount }) }}
        </span>
        <span v-else class="file-structure-tree__meta text-muted">
          {{ formatSizeBytes(row.node.size || 0) }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { formatSizeBytes } from '@/utils/formatters'

const props = defineProps({
  files: {
    type: Array,
    default: () => [],
  },
  rootName: {
    type: String,
    default: '',
  },
  emptyText: {
    type: String,
    default: '',
  },
})

const { t } = useI18n()
const expandedKeys = ref(new Set())
const emptyText = computed(() => props.emptyText || t('libraryFileDetail.noFiles'))

const normalizedFiles = computed(() => (
  props.files
    .map((file, index) => normalizeFile(file, index))
    .filter((file) => file.path)
))

const tree = computed(() => buildTree(normalizedFiles.value))
const rows = computed(() => {
  const result = []
  appendVisibleRows(tree.value.children, 0, result, expandedKeys.value)
  return result
})

const fileSignature = computed(() => normalizedFiles.value.map((file) => file.path).join('\n'))

watch(fileSignature, () => {
  const nextExpanded = new Set()
  nextExpanded.add('')
  tree.value.children.forEach((node) => {
    if (node.type === 'directory') nextExpanded.add(node.key)
  })
  expandedKeys.value = nextExpanded
}, { immediate: true })

function normalizeFile(file, fallbackIndex) {
  const rawPath = normalizePath(
    file?.relative_path
    || file?.filename
    || file?.name
    || file?.file_name
    || joinPath(file?.path, file?.file_name)
  )
  const rootName = normalizePath(props.rootName)
  const path = rootName && rawPath && !rawPath.startsWith(`${rootName}/`) && rawPath !== rootName
    ? `${rootName}/${rawPath}`
    : rawPath
  return {
    path,
    size: Number(file?.file_size ?? file?.size ?? 0),
    index: Number(file?.file_index ?? file?.index ?? fallbackIndex),
  }
}

function joinPath(path, fileName) {
  if (!path && !fileName) return ''
  if (!path) return fileName || ''
  if (!fileName) return path || ''
  return `${path}/${fileName}`
}

function normalizePath(value) {
  return String(value || '').replace(/\\/g, '/').replace(/^\/+/, '').replace(/\/+$/, '')
}

function createDirectoryNode(key, name) {
  return {
    type: 'directory',
    key,
    name,
    children: [],
    childMap: new Map(),
    fileCount: 0,
    totalSize: 0,
  }
}

function createFileNode(file, name, key) {
  return {
    type: 'file',
    key,
    name,
    size: file.size,
    index: file.index,
  }
}

function buildTree(files) {
  const root = createDirectoryNode('', '')
  files.forEach((file) => {
    const parts = file.path.split('/').filter(Boolean)
    if (parts.length === 0) return

    let current = root
    current.fileCount += 1
    current.totalSize += file.size

    parts.slice(0, -1).forEach((part, index) => {
      const key = parts.slice(0, index + 1).join('/')
      if (!current.childMap.has(part)) {
        const node = createDirectoryNode(key, part)
        current.childMap.set(part, node)
        current.children.push(node)
      }
      current = current.childMap.get(part)
      current.fileCount += 1
      current.totalSize += file.size
    })

    const fileName = parts[parts.length - 1]
    current.children.push(createFileNode(file, fileName, `${file.path}:${file.index}`))
  })
  sortChildren(root)
  return root
}

function sortChildren(node) {
  node.children.sort((left, right) => {
    if (left.type !== right.type) return left.type === 'directory' ? -1 : 1
    return left.name.localeCompare(right.name)
  })
  node.children.forEach((child) => {
    if (child.type === 'directory') sortChildren(child)
  })
}

function appendVisibleRows(nodes, level, result, expanded) {
  nodes.forEach((node) => {
    result.push({ node, level })
    if (node.type === 'directory' && expanded.has(node.key)) {
      appendVisibleRows(node.children, level + 1, result, expanded)
    }
  })
}

function isExpanded(key) {
  return expandedKeys.value.has(key)
}

function toggle(key) {
  const nextExpanded = new Set(expandedKeys.value)
  if (nextExpanded.has(key)) {
    nextExpanded.delete(key)
  } else {
    nextExpanded.add(key)
  }
  expandedKeys.value = nextExpanded
}
</script>

<style scoped>
.file-structure-tree {
  min-width: 0;
  --file-tree-indent: 1rem;
  --file-tree-offset: 0px;
}

.file-structure-tree__rows {
  display: flex;
  flex-direction: column;
  border-top: 1px solid var(--color-border-subtle, var(--p-content-border-color));
}

.file-structure-tree__row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: start;
  column-gap: var(--spacing-item);
  min-height: 2rem;
  border-bottom: 1px solid var(--color-border-subtle, var(--p-content-border-color));
  padding-inline-start: var(--file-tree-offset);
  padding-top: var(--spacing-inline);
  padding-bottom: var(--spacing-inline);
}

.file-structure-tree__row--directory {
  cursor: pointer;
}

.file-structure-tree__row--directory:hover .file-structure-tree__content,
.file-structure-tree__row--directory:focus-visible .file-structure-tree__content {
  color: var(--accent-primary);
}

.file-structure-tree__row--directory:focus-visible {
  outline: 2px solid var(--accent-primary);
  outline-offset: -2px;
}

.file-structure-tree__content {
  display: inline-flex;
  align-items: flex-start;
  gap: var(--spacing-inline);
  min-width: 0;
}

.file-structure-tree__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 1em;
  width: 1em;
  line-height: 1;
  transform: translateY(0.0625rem);
}

.file-structure-tree__name {
  min-width: 0;
}

.file-structure-tree__meta {
  white-space: nowrap;
}
</style>
