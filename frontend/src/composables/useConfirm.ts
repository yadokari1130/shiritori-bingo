import { ref } from 'vue'

export interface ConfirmOptions {
  title?: string
  message: string
  confirmText?: string
  cancelText?: string
  danger?: boolean
}

interface ConfirmState extends ConfirmOptions {
  isOpen: boolean
}

const state = ref<ConfirmState>({
  isOpen: false,
  message: '',
  title: '確認',
  confirmText: '実行する',
  cancelText: 'キャンセル',
  danger: false,
})

let resolveFn: ((value: boolean) => void) | null = null

export function useConfirm() {
  function showConfirm(options: ConfirmOptions | string): Promise<boolean> {
    const opts: ConfirmOptions = typeof options === 'string' ? { message: options } : options
    state.value = {
      isOpen: true,
      title: opts.title ?? '確認',
      message: opts.message,
      confirmText: opts.confirmText ?? '実行する',
      cancelText: opts.cancelText ?? 'キャンセル',
      danger: opts.danger ?? false,
    }
    return new Promise<boolean>((resolve) => {
      resolveFn = resolve
    })
  }

  function handleConfirm(): void {
    state.value.isOpen = false
    if (resolveFn) {
      resolveFn(true)
      resolveFn = null
    }
  }

  function handleCancel(): void {
    state.value.isOpen = false
    if (resolveFn) {
      resolveFn(false)
      resolveFn = null
    }
  }

  return {
    state,
    showConfirm,
    handleConfirm,
    handleCancel,
  }
}
