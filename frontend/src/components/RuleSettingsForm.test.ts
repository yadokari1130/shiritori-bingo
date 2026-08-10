import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { nextTick } from 'vue'
import RuleSettingsForm from './RuleSettingsForm.vue'
import { createDefaultSettings } from '../types'

describe('RuleSettingsForm', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('初期設定の各項目が正しく表示されること', () => {
    const settings = createDefaultSettings()
    const wrapper = mount(RuleSettingsForm, {
      props: {
        modelValue: settings,
        submitButtonText: 'ルームを作成',
      },
    })

    expect(wrapper.text()).toContain('モード設定')
    expect(wrapper.text()).toContain('対戦モード')
    expect(wrapper.text()).toContain('カード設定')
    expect(wrapper.text()).toContain('カードサイズ')
    expect(wrapper.text()).toContain('カードに含める文字カテゴリ')
    expect(wrapper.text()).toContain('濁音')
    expect(wrapper.text()).toContain('半濁音')
    expect(wrapper.text()).toContain('拗音')
    expect(wrapper.text()).toContain('促音')
    expect(wrapper.text()).toContain('伸ばし棒')
    expect(wrapper.text()).toContain('小さいあ行')
    expect(wrapper.text()).toContain('終了条件')
    expect(wrapper.text()).toContain('指定ターン数')
    expect(wrapper.text()).toContain('指定ビンゴ数')
    expect(wrapper.text()).toContain('時間設定')
    expect(wrapper.text()).toContain('制限時間（秒）')
    expect(wrapper.text()).toContain('初回エクストラ（秒）')
    expect(wrapper.text()).toContain('時間切れで強制スキップ')
    expect(wrapper.text()).toContain('無効入力の扱い')
    expect(wrapper.text()).toContain('ターンスキップ')
    expect(wrapper.text()).toContain('失格')
    expect(wrapper.text()).toContain('設定プリセット')
    expect(wrapper.text()).toContain('エクストラ設定')
    expect(wrapper.find('details.extra-settings').attributes('open')).toBeUndefined()
    expect(wrapper.find('.submit-settings-btn').text()).toBe('ルームを作成')
  })

  it('文字数制限を設定でき、範囲が逆なら送信を無効化すること', async () => {
    const wrapper = mount(RuleSettingsForm, {
      props: { modelValue: createDefaultSettings() },
    })
    const details = wrapper.find('details.extra-settings')
    await details.find('summary').trigger('click')
    await wrapper.find('#minWordLength').setValue('5')
    await wrapper.find('#maxWordLength').setValue('3')

    expect(wrapper.text()).toContain('最小文字数は最大文字数以下で指定してください')
    expect(wrapper.find('.submit-settings-btn').attributes('disabled')).toBeDefined()
  })

  it('文字数制限をクリアして制限なしへ戻せること', async () => {
    const settings = createDefaultSettings()
    settings.minWordLength = 2
    settings.maxWordLength = 6
    const wrapper = mount(RuleSettingsForm, {
      props: { modelValue: settings },
    })

    await wrapper.find('details.extra-settings summary').trigger('click')
    const clearButtons = wrapper.findAll('details.extra-settings .number-input-row button')
    await clearButtons[0].trigger('click')
    await clearButtons[1].trigger('click')

    expect(wrapper.emitted('update:modelValue')?.at(-1)?.[0]).toMatchObject({
      minWordLength: null,
      maxWordLength: null,
    })
  })

  it('プリセットの保存・一覧表示・読込・初期値復元が動作すること', async () => {
    const settings = createDefaultSettings()
    settings.cardSize = 7

    const wrapper = mount(RuleSettingsForm, {
      props: {
        modelValue: settings,
      },
    })

    // プリセット名を入力して保存
    const nameInput = wrapper.find('#presetName')
    await nameInput.setValue('テストプリセット')
    const saveBtn = wrapper.findAll('.preset-actions button')[0]
    await saveBtn.trigger('click')

    // 保存一覧ボタンを押す
    const listBtn = wrapper.findAll('.preset-actions button')[1]
    await listBtn.trigger('click')

    expect(wrapper.text()).toContain('テストプリセット')

    // 初期値ボタンを押す
    const resetBtn = wrapper.findAll('.preset-actions button')[2]
    await resetBtn.trigger('click')

    const emitted = wrapper.emitted('update:modelValue')
    expect(emitted).toBeTruthy()
    const lastEmitted = emitted![emitted!.length - 1][0] as typeof settings
    expect(lastEmitted.cardSize).toBe(5) // default is 5
  })

  it('バリデーションエラー時に送信ボタンが無効化されること', async () => {
    const settings = createDefaultSettings()
    settings.cardSize = 4 // 偶数は不正

    const wrapper = mount(RuleSettingsForm, {
      props: {
        modelValue: settings,
      },
    })
    await nextTick()

    expect(wrapper.text()).toContain('奇数を指定してください')
    const submitBtn = wrapper.find('.submit-settings-btn')
    expect(submitBtn.attributes('disabled')).toBeDefined()
  })
})
