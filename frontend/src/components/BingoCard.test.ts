import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import BingoCard from './BingoCard.vue'
import type { BingoCard as BingoCardType } from '../types'

describe('BingoCard コンポーネント', () => {
  it('小文字（拗音・促音・小あ行）の文字には is-small-char クラスが付与される', () => {
    const card: BingoCardType = {
      size: 3,
      freeChar: 'か',
      cells: [
        { index: 0, row: 0, column: 0, char: 'あ', isOpen: false, isFree: false },
        { index: 1, row: 0, column: 1, char: 'っ', isOpen: false, isFree: false },
        { index: 2, row: 0, column: 2, char: 'ゃ', isOpen: false, isFree: false },
        { index: 3, row: 1, column: 0, char: 'い', isOpen: false, isFree: false },
        { index: 4, row: 1, column: 1, char: 'か', isOpen: true, isFree: true },
        { index: 5, row: 1, column: 2, char: 'ぁ', isOpen: false, isFree: false },
        { index: 6, row: 2, column: 0, char: 'つ', isOpen: false, isFree: false },
        { index: 7, row: 2, column: 1, char: 'や', isOpen: false, isFree: false },
        { index: 8, row: 2, column: 2, char: 'ー', isOpen: false, isFree: false },
      ],
    }

    const wrapper = mount(BingoCard, {
      props: {
        card,
        title: 'テストプレイヤー',
        disconnected: true,
        members: [{ name: 'メンバー', disconnected: true }],
      },
    })

    const charSpans = wrapper.findAll('.cell-character')
    expect(charSpans).toHaveLength(9)

    // 通常文字（あ: index 0, い: index 3, か: index 4, つ: index 6, や: index 7, ー: index 8）
    expect(charSpans[0].classes()).not.toContain('is-small-char')
    expect(charSpans[3].classes()).not.toContain('is-small-char')
    expect(charSpans[4].classes()).not.toContain('is-small-char')
    expect(charSpans[6].classes()).not.toContain('is-small-char')
    expect(charSpans[7].classes()).not.toContain('is-small-char')
    expect(charSpans[8].classes()).not.toContain('is-small-char')

    // 小文字（っ: index 1, ゃ: index 2, ぁ: index 5）
    expect(charSpans[1].classes()).toContain('is-small-char')
    expect(charSpans[2].classes()).toContain('is-small-char')
    expect(charSpans[5].classes()).toContain('is-small-char')
    expect(wrapper.findAll('.disconnected-mark')).toHaveLength(2)
    expect(wrapper.find('.disconnected-mark').attributes('aria-label')).toBe('切断中')
  })
})
