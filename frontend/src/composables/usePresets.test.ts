import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { createDefaultSettings } from '../types'
import { sanitizeSettings, usePresets } from './usePresets'

describe('usePresets', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    localStorage.clear()
  })

  it('初期状態ではプリセットが空', () => {
    const { presets } = usePresets()
    expect(presets.value).toEqual([])
  })

  it('プリセットを追加して読み込める', () => {
    const { presets, addPreset, applyPreset } = usePresets()
    const settings = createDefaultSettings()
    settings.cardSize = 7
    const preset = addPreset('7x7設定', settings)
    expect(presets.value.length).toBe(1)

    const loaded = applyPreset(preset.id)
    expect(loaded).not.toBeNull()
    expect(loaded!.cardSize).toBe(7)
  })

  it('プリセットを上書き保存できる', () => {
    const { addPreset, updatePreset, applyPreset } = usePresets()
    const preset = addPreset('初期設定', createDefaultSettings())
    const newSettings = createDefaultSettings()
    newSettings.cardSize = 9
    const ok = updatePreset(preset.id, '更新設定', newSettings)
    expect(ok).toBe(true)

    const loaded = applyPreset(preset.id)
    expect(loaded!.cardSize).toBe(9)
  })

  it('プリセットを削除できる', () => {
    const { presets, addPreset, deletePreset } = usePresets()
    const preset = addPreset('削除対象', createDefaultSettings())
    expect(presets.value.length).toBe(1)

    const ok = deletePreset(preset.id)
    expect(ok).toBe(true)
    expect(presets.value.length).toBe(0)
  })

  it('localStorage に永続化される', () => {
    const { addPreset } = usePresets()
    addPreset('永続化テスト', createDefaultSettings())

    const { presets } = usePresets()
    expect(presets.value.length).toBe(1)
    expect(presets.value[0].name).toBe('永続化テスト')
  })

  it('壊れた localStorage は読み込まない', () => {
    localStorage.setItem('shiritori-bingo-presets', 'not-json')
    const { presets, loadError } = usePresets()
    expect(presets.value).toEqual([])
    expect(loadError.value).not.toBeNull()
  })
})

describe('sanitizeSettings', () => {
  it('不正な値は初期値で補完される', () => {
    const result = sanitizeSettings({ cardSize: 'big' })
    expect(typeof result.cardSize).toBe('number')
    expect(result.cardSize).toBeGreaterThanOrEqual(3)
  })

  it('mode は individual か team のみ', () => {
    const result = sanitizeSettings({ mode: 'invalid' as never })
    expect(result.mode).toBe('individual')
  })
})
