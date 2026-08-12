/**
 * 名前付き設定プリセットの localStorage 管理
 *
 * 仕様書 5.8, 9.1, 12.3 に基づく。
 */

import { ref } from 'vue'
import type { Preset, Settings } from '../types'
import { createDefaultSettings } from '../types'

const STORAGE_KEY = 'shiritori-bingo-presets'

export function usePresets() {
  const presets = ref<Preset[]>([])
  const loadError = ref<string | null>(null)
  const saveError = ref<string | null>(null)

  /** 保存済みプリセットを読み込む */
  function loadPresets(): void {
    loadError.value = null
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (!raw) {
        presets.value = []
        return
      }
      const parsed = JSON.parse(raw) as unknown
      if (!Array.isArray(parsed)) {
        presets.value = []
        return
      }
      const valid = parsed.filter(isValidPreset)
      presets.value = valid
    } catch {
      loadError.value = 'プリセットの読み込みに失敗しました。'
      presets.value = []
    }
  }

  /** プリセットとして正しい形状か簡易検証する */
  function isValidPreset(value: unknown): value is Preset {
    if (typeof value !== 'object' || value === null) return false
    const p = value as Record<string, unknown>
    return (
      typeof p.id === 'string' &&
      typeof p.name === 'string' &&
      typeof p.createdAt === 'number' &&
      typeof p.updatedAt === 'number' &&
      typeof p.settings === 'object' &&
      p.settings !== null
    )
  }

  /** プリセットを保存する */
  function savePresets(): boolean {
    saveError.value = null
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(presets.value))
      return true
    } catch {
      saveError.value = 'プリセットを保存できませんでした。現在のゲームでは利用できます。'
      return false
    }
  }

  /** 新しいプリセットを追加する */
  function addPreset(name: string, settings: Settings): Preset {
    const now = Date.now()
    const preset: Preset = {
      id: generateId(),
      name: name.trim(),
      settings,
      createdAt: now,
      updatedAt: now,
    }
    presets.value.push(preset)
    savePresets()
    return preset
  }

  /** 既存プリセットを上書き保存する */
  function updatePreset(presetId: string, name: string, settings: Settings): boolean {
    const index = presets.value.findIndex((p) => p.id === presetId)
    if (index === -1) return false
    presets.value[index] = {
      ...presets.value[index],
      name: name.trim(),
      settings,
      updatedAt: Date.now(),
    }
    savePresets()
    return true
  }

  /** プリセットを削除する */
  function deletePreset(presetId: string): boolean {
    const before = presets.value.length
    presets.value = presets.value.filter((p) => p.id !== presetId)
    if (presets.value.length === before) return false
    savePresets()
    return true
  }

  /** プリセットを設定に適用する */
  function applyPreset(presetId: string): Settings | null {
    const preset = presets.value.find((p) => p.id === presetId)
    return preset ? { ...preset.settings } : null
  }

  /** 現在の設定を複製して新しいプリセット名を提案する */
  function suggestPresetName(base = '新しいプリセット'): string {
    const existing = presets.value.filter((p) => p.name.startsWith(base))
    if (existing.length === 0) return base
    return `${base} (${existing.length + 1})`
  }

  function generateId(): string {
    return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
  }

  // 初期化
  loadPresets()

  return {
    presets,
    loadError,
    saveError,
    loadPresets,
    savePresets,
    addPreset,
    updatePreset,
    deletePreset,
    applyPreset,
    suggestPresetName,
  }
}

/**
 * 設定が最低限の型を満たしているか確認する。
 * 壊れた localStorage 値からの復帰用。
 */
export function sanitizeSettings(value: unknown): Settings {
  const defaults = createDefaultSettings()
  if (typeof value !== 'object' || value === null) return defaults
  const s = value as Partial<Settings>

  return {
    cardSize: typeof s.cardSize === 'number' && s.cardSize >= 3 ? s.cardSize : defaults.cardSize,
    mode: s.mode === 'team' ? 'team' : 'individual',
    teamCount: typeof s.teamCount === 'number' && s.teamCount >= 2 ? s.teamCount : defaults.teamCount,
    cardOptions: {
      yoon: Boolean(s.cardOptions?.yoon),
      sokuon: Boolean(s.cardOptions?.sokuon),
      prolonged: Boolean(s.cardOptions?.prolonged),
      smallA: Boolean(s.cardOptions?.smallA),
      dakuten: Boolean(s.cardOptions?.dakuten),
      handakuten: Boolean(s.cardOptions?.handakuten),
    },
    endCondition: s.endCondition === 'bingos' ? 'bingos' : 'turns',
    targetTurns: typeof s.targetTurns === 'number' && s.targetTurns > 0 ? s.targetTurns : defaults.targetTurns,
    targetBingos: typeof s.targetBingos === 'number' && s.targetBingos > 0 ? s.targetBingos : defaults.targetBingos,
    timeLimitSeconds: typeof s.timeLimitSeconds === 'number' && s.timeLimitSeconds > 0 ? s.timeLimitSeconds : defaults.timeLimitSeconds,
    extraTimeSeconds: typeof s.extraTimeSeconds === 'number' && s.extraTimeSeconds >= 0 ? s.extraTimeSeconds : defaults.extraTimeSeconds,
    forceSkipOnTimeout: Boolean(s.forceSkipOnTimeout),
    invalidAction: s.invalidAction === 'disqualify' ? 'disqualify' : 'skip',
    inputWordCheck: typeof s.inputWordCheck === 'boolean' ? s.inputWordCheck : defaults.inputWordCheck,
    minWordLength: typeof s.minWordLength === 'number' && s.minWordLength >= 1 ? s.minWordLength : null,
    maxWordLength: typeof s.maxWordLength === 'number' && s.maxWordLength >= 1 ? s.maxWordLength : null,
  }
}
