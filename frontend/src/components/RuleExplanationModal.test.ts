import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import RuleExplanationModal from './RuleExplanationModal.vue'
import { createDefaultSettings } from '../types'

describe('RuleExplanationModal', () => {
  it('modelValueがfalseの時は非表示である', () => {
    const wrapper = mount(RuleExplanationModal, {
      props: {
        modelValue: false,
        settings: createDefaultSettings(),
        disableTeleport: true,
      },
    })
    expect(wrapper.find('.rule-modal-backdrop').exists()).toBe(false)
  })

  it('modelValueがtrueの時は表示され、閉じるボタンでupdate:modelValueが発火する', async () => {
    const wrapper = mount(RuleExplanationModal, {
      props: {
        modelValue: true,
        settings: createDefaultSettings(),
        disableTeleport: true,
      },
    })
    expect(wrapper.find('.rule-modal-backdrop').exists()).toBe(true)

    // ヘッダーの閉じるボタン
    await wrapper.find('.modal-close-icon').trigger('click')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([false])

    // フッターの閉じるボタン
    await wrapper.find('.modal-btn').trigger('click')
    expect(wrapper.emitted('update:modelValue')?.[1]).toEqual([false])
  })

  it('背景クリックでモーダルが閉じる', async () => {
    const wrapper = mount(RuleExplanationModal, {
      props: {
        modelValue: true,
        settings: createDefaultSettings(),
        disableTeleport: true,
      },
    })
    await wrapper.find('.rule-modal-backdrop').trigger('click')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([false])
  })

  it('Escapeキー押下でモーダルが閉じる', async () => {
    const wrapper = mount(RuleExplanationModal, {
      props: {
        modelValue: true,
        settings: createDefaultSettings(),
        disableTeleport: true,
      },
    })
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([false])
  })

  it('個人戦とチーム戦で説明が動的に変化する', async () => {
    const defaultSettings = createDefaultSettings()
    const wrapper = mount(RuleExplanationModal, {
      props: {
        modelValue: true,
        settings: {
          ...defaultSettings,
          mode: 'individual',
        },
        disableTeleport: true,
      },
    })
    expect(wrapper.text()).toContain('個人戦')
    expect(wrapper.text()).toContain('プレイヤー各自に専用のビンゴカード')

    await wrapper.setProps({
      settings: {
        ...defaultSettings,
        mode: 'team',
        teamCount: 3,
      },
    })
    expect(wrapper.text()).toContain('チーム戦 (3チーム)')
    expect(wrapper.text()).toContain('チームの所属者なら誰でも')
  })

  it('終了条件（ターン数 vs ビンゴ数）で説明が動的に変化する', async () => {
    const defaultSettings = createDefaultSettings()
    const wrapper = mount(RuleExplanationModal, {
      props: {
        modelValue: true,
        settings: {
          ...defaultSettings,
          endCondition: 'turns',
          targetTurns: 5,
        },
        disableTeleport: true,
      },
    })
    expect(wrapper.text()).toContain('指定ターン数 (5ターン)')
    expect(wrapper.text()).toContain('指定ターン数（5ターン）が終了した時点で')

    await wrapper.setProps({
      settings: {
        ...defaultSettings,
        endCondition: 'bingos',
        targetBingos: 4,
      },
    })
    expect(wrapper.text()).toContain('指定ビンゴ数 (4本達成)')
    expect(wrapper.text()).toContain('4本ビンゴを達成したターン')
  })

  it('強制スキップ設定で説明が動的に変化する', async () => {
    const defaultSettings = createDefaultSettings()
    const wrapper = mount(RuleExplanationModal, {
      props: {
        modelValue: true,
        settings: {
          ...defaultSettings,
          forceSkipOnTimeout: false,
        },
        disableTeleport: true,
      },
    })
    expect(wrapper.text()).toContain('「強制スキップなし」')

    await wrapper.setProps({
      settings: {
        ...defaultSettings,
        forceSkipOnTimeout: true,
      },
    })
    expect(wrapper.text()).toContain('「強制スキップあり」')
  })

  it('無効入力ペナルティ設定（スキップ vs 失格）で説明が動的に変化する', async () => {
    const defaultSettings = createDefaultSettings()
    const wrapper = mount(RuleExplanationModal, {
      props: {
        modelValue: true,
        settings: {
          ...defaultSettings,
          invalidAction: 'skip',
        },
        disableTeleport: true,
      },
    })
    expect(wrapper.text()).toContain('無効時: ターンスキップ')
    expect(wrapper.text()).toContain('【ターンスキップ】')

    await wrapper.setProps({
      settings: {
        ...defaultSettings,
        invalidAction: 'disqualify',
      },
    })
    expect(wrapper.text()).toContain('無効時: 失格')
    expect(wrapper.text()).toContain('【失格】')
  })

  it('入力文字チェック設定および文字数制限で説明が動的に変化する', async () => {
    const defaultSettings = createDefaultSettings()
    const wrapper = mount(RuleExplanationModal, {
      props: {
        modelValue: true,
        settings: {
          ...defaultSettings,
          inputWordCheck: true,
          minWordLength: 3,
          maxWordLength: 6,
        },
        disableTeleport: true,
      },
    })
    expect(wrapper.text()).toContain('送信前チェック: あり')
    expect(wrapper.text()).toContain('3文字以上 6文字以下')

    await wrapper.setProps({
      settings: {
        ...defaultSettings,
        inputWordCheck: false,
        minWordLength: 4,
        maxWordLength: null,
      },
    })
    expect(wrapper.text()).toContain('送信前チェック: なし（即ペナルティ）')
    expect(wrapper.text()).toContain('4文字以上')
  })
})
