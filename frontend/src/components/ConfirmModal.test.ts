import { describe, expect, it, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ConfirmModal from './ConfirmModal.vue'
import { useConfirm } from '../composables/useConfirm'

describe('ConfirmModal', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('初期状態ではモーダルが表示されない', () => {
    const wrapper = mount(ConfirmModal)
    expect(wrapper.find('.confirm-modal-backdrop').exists()).toBe(false)
    wrapper.unmount()
  })

  it('showConfirm呼び出しでモーダルが表示され、確定でtrueを返す', async () => {
    const { showConfirm } = useConfirm()
    const wrapper = mount(ConfirmModal, { attachTo: document.body })

    const confirmPromise = showConfirm({
      title: 'テスト確認',
      message: '本当に実行しますか？',
      confirmText: 'はい',
      cancelText: 'いいえ',
    })

    await wrapper.vm.$nextTick()
    const backdrop = document.body.querySelector('.confirm-modal-backdrop')
    expect(backdrop).not.toBeNull()
    expect(document.body.querySelector('.confirm-modal-title')?.textContent).toBe('テスト確認')
    expect(document.body.querySelector('.confirm-modal-message')?.textContent).toBe('本当に実行しますか？')

    const confirmBtn = document.body.querySelector('.modal-confirm-button') as HTMLButtonElement
    expect(confirmBtn.textContent?.trim()).toBe('はい')
    confirmBtn.click()

    const result = await confirmPromise
    expect(result).toBe(true)
    await wrapper.vm.$nextTick()
    expect(document.body.querySelector('.confirm-modal-backdrop')).toBeNull()

    wrapper.unmount()
  })

  it('キャンセルボタンをクリックするとfalseを返す', async () => {
    const { showConfirm } = useConfirm()
    const wrapper = mount(ConfirmModal, { attachTo: document.body })

    const confirmPromise = showConfirm({
      title: '解散確認',
      message: '解散しますか？',
      danger: true,
    })

    await wrapper.vm.$nextTick()
    const cancelBtn = document.body.querySelector('.modal-cancel-button') as HTMLButtonElement
    expect(cancelBtn).not.toBeNull()
    cancelBtn.click()

    const result = await confirmPromise
    expect(result).toBe(false)
    await wrapper.vm.$nextTick()
    expect(document.body.querySelector('.confirm-modal-backdrop')).toBeNull()

    wrapper.unmount()
  })

  it('Escapeキー押下でキャンセルされfalseを返す', async () => {
    const { showConfirm } = useConfirm()
    const wrapper = mount(ConfirmModal, { attachTo: document.body })

    const confirmPromise = showConfirm('メッセージのみ')

    await wrapper.vm.$nextTick()
    expect(document.body.querySelector('.confirm-modal-backdrop')).not.toBeNull()

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))

    const result = await confirmPromise
    expect(result).toBe(false)
    await wrapper.vm.$nextTick()
    expect(document.body.querySelector('.confirm-modal-backdrop')).toBeNull()

    wrapper.unmount()
  })
})
