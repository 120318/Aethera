const TEXT_BUTTON_STATE_CLASS = 'hover:text-primary-emphasis active:text-primary-emphasis'
const ICON_BUTTON_STATE_CLASS = 'text-muted hover:text-primary-emphasis active:text-primary-emphasis'

function createBareButtonStyle({
  padding = '0',
  paddingInline,
  paddingBlock,
  minWidth = '0',
  minHeight = '0',
  width = 'auto',
  height = 'auto',
} = {}) {
  return Object.fromEntries(Object.entries({
    background: 'transparent',
    border: 'none',
    boxShadow: 'none',
    outline: 'none',
    padding,
    paddingInline,
    paddingBlock,
    minWidth,
    minHeight,
    width,
    height,
  }).filter(([, value]) => value !== undefined))
}

function createCompactButtonStyle() {
  return createBareButtonStyle({
    paddingInline: 'var(--spacing-inline)',
    paddingBlock: 'var(--spacing-tight)',
  })
}

function createIconOnlyButtonStyle() {
  return createBareButtonStyle({
    padding: 'var(--spacing-micro)',
  })
}

function createPaginatorControl() {
  return {
    class: ICON_BUTTON_STATE_CLASS,
    style: createCompactButtonStyle(),
  }
}

function createButtonRootPt(props) {
  const isTextVariant = props.text || props.variant === 'text'
  const isIconOnly = !props.label && props.icon

  if (isIconOnly) {
    return {
      class: `aspect-square ${ICON_BUTTON_STATE_CLASS}`,
      style: createIconOnlyButtonStyle(),
    }
  }

  if (isTextVariant) {
    return {
      class: TEXT_BUTTON_STATE_CLASS,
      style: createBareButtonStyle(),
    }
  }

  return {}
}

function createDialogPt() {
  return {
    root: {
      class: 'text-color',
    },
    header: {
      class: 'px-container pt-container pb-item',
    },
    content: {
      class: 'px-container pb-container',
    },
    footer: {
      class: 'px-container pt-item pb-container flex items-center justify-center gap-item flex-wrap',
    },
    pcCloseButton: {
      root: {
        class: 'aspect-square flex items-center justify-center text-muted hover:text-primary-emphasis active:text-primary-emphasis',
        style: createIconOnlyButtonStyle(),
      },
    },
  }
}

function createPaginatorPt() {
  return {
    root: {
      style: { padding: '0' },
    },
    page: ({ context }) => ({
      class: context.active
        ? 'text-primary-emphasis font-semibold'
        : ICON_BUTTON_STATE_CLASS,
      style: createCompactButtonStyle(),
    }),
    prev: createPaginatorControl(),
    next: createPaginatorControl(),
    first: createPaginatorControl(),
    last: createPaginatorControl(),
  }
}

export function createPrimeVuePt() {
  return {
    button: {
      root: ({ props }) => createButtonRootPt(props),
    },
    dialog: createDialogPt(),
    toast: {
      messageIcon: {
        class: 'hidden',
      },
    },
    card: {
      root: 'border-separator border rounded-container bg-surface',
      body: 'p-container',
      content: 'p-none',
    },
    paginator: createPaginatorPt(),
  }
}
