<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { usePresets } from '../composables/usePresets'
import { createDefaultSettings, type Settings } from '../types'
import { buildCardCharPool, maxCardSize } from '../utils/shiritori'

const props = withDefaults(
  defineProps<{
    modelValue: Settings
    submitButtonText?: string
    isSubmitting?: boolean
    submitDisabled?: boolean
  }>(),
  {
    submitButtonText: '設定を反映する',
    isSubmitting: false,
    submitDisabled: false,
  },
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: Settings): void
  (e: 'submit'): void
}>()

const presets = usePresets()

const presetName = ref('')
const selectedPresetId = ref<string | null>(null)
const showPresetMenu = ref(false)

const draft = ref<Settings>({
  ...props.modelValue,
  cardOptions: { ...props.modelValue.cardOptions },
})

watch(
  () => props.modelValue,
  (val) => {
    draft.value = {
      ...val,
      cardOptions: { ...val.cardOptions },
    }
  },
  { deep: true },
)

function updateDraft(): void {
  emit('update:modelValue', {
    ...draft.value,
    cardOptions: { ...draft.value.cardOptions },
  })
}

// カード候補文字プールと最大カードサイズ
const cardCharPool = computed(() => buildCardCharPool(draft.value.cardOptions))
const maxSize = computed(() => maxCardSize(cardCharPool.value))

// バリデーション
const cardSizeError = computed(() => {
  const s = draft.value.cardSize
  if (Number.isNaN(s) || s === null || s === undefined) return '数値を入力してください。'
  if (s < 3) return '3以上を指定してください。'
  if (s % 2 === 0) return '奇数を指定してください。'
  if (s > maxSize.value) return `最大${maxSize.value}までです（現在の候補文字数: ${cardCharPool.value.length}）。`
  return ''
})

const targetBingosError = computed(() => {
  if (draft.value.endCondition !== 'bingos') return ''
  const max = draft.value.cardSize * 2 + 2
  const b = draft.value.targetBingos
  if (Number.isNaN(b) || b < 1 || b > max) return `1〜${max}の範囲で指定してください。`
  return ''
})

const isInvalid = computed(() => {
  if (cardSizeError.value || targetBingosError.value) return true
  if (draft.value.endCondition === 'turns' && (Number.isNaN(draft.value.targetTurns) || draft.value.targetTurns < 1)) return true
  if (draft.value.mode === 'team' && (Number.isNaN(draft.value.teamCount) || draft.value.teamCount < 2)) return true
  if (Number.isNaN(draft.value.timeLimitSeconds) || draft.value.timeLimitSeconds < 1) return true
  if (Number.isNaN(draft.value.extraTimeSeconds) || draft.value.extraTimeSeconds < 0) return true
  return false
})

function onSubmit(): void {
  if (isInvalid.value || props.isSubmitting || props.submitDisabled) return
  emit('submit')
}

function applyPreset(presetId: string): void {
  const settings = presets.applyPreset(presetId)
  if (settings) {
    draft.value = {
      ...settings,
      cardOptions: { ...settings.cardOptions },
    }
    selectedPresetId.value = presetId
    showPresetMenu.value = false
    updateDraft()
  }
}

function onSavePreset(): void {
  const name = presetName.value.trim()
  if (!name) return
  if (selectedPresetId.value) {
    presets.updatePreset(selectedPresetId.value, name, {
      ...draft.value,
      cardOptions: { ...draft.value.cardOptions },
    })
  } else {
    const preset = presets.addPreset(name, {
      ...draft.value,
      cardOptions: { ...draft.value.cardOptions },
    })
    selectedPresetId.value = preset.id
  }
  presetName.value = ''
}

function onDeletePreset(presetId: string): void {
  presets.deletePreset(presetId)
  if (selectedPresetId.value === presetId) {
    selectedPresetId.value = null
  }
}

function onResetSettings(): void {
  draft.value = createDefaultSettings()
  selectedPresetId.value = null
  updateDraft()
}

function onSelectPresetToEdit(presetId: string): void {
  const settings = presets.applyPreset(presetId)
  if (settings) {
    draft.value = {
      ...settings,
      cardOptions: { ...settings.cardOptions },
    }
    selectedPresetId.value = presetId
    presetName.value = presets.presets.value.find((p) => p.id === presetId)?.name ?? ''
    showPresetMenu.value = false
    updateDraft()
  }
}
</script>

<template>
  <div class="rule-settings-form">
    <form class="settings-form" @submit.prevent="onSubmit">
      <!-- モード設定 -->
      <fieldset class="panel-fieldset">
        <legend class="panel-legend">モード設定</legend>
        <div class="field-grid">
          <div class="field">
            <label for="gameMode" class="field-label">対戦モード</label>
            <select
              id="gameMode"
              v-model="draft.mode"
              class="text-input select-input"
              @change="updateDraft"
            >
              <option value="individual">個人戦</option>
              <option value="team">チーム戦</option>
            </select>
          </div>
          <div v-if="draft.mode === 'team'" class="field">
            <label for="teamCount" class="field-label">チーム数</label>
            <input
              id="teamCount"
              v-model.number="draft.teamCount"
              type="number"
              min="2"
              class="number-input"
              @input="updateDraft"
            >
          </div>
        </div>
      </fieldset>

      <!-- カード設定 -->
      <fieldset class="panel-fieldset">
        <legend class="panel-legend">カード設定</legend>
        <div class="field-grid">
          <div class="field">
            <label for="cardSize" class="field-label">カードサイズ</label>
            <input
              id="cardSize"
              v-model.number="draft.cardSize"
              type="number"
              min="3"
              step="2"
              class="number-input"
              @input="updateDraft"
            >
            <p v-if="cardSizeError" class="notice error mt-1">{{ cardSizeError }}</p>
            <p v-else class="field-note">
              3以上の奇数。中央がFREEマスになります。（最大{{ maxSize }}マス / 候補文字数: {{ cardCharPool.length }}）
            </p>
          </div>
        </div>

        <div class="field mt-3">
          <span class="field-label">カードに含める文字カテゴリ</span>
          <div class="options-grid">
            <label class="check-option">
              <input
                v-model="draft.cardOptions.dakuten"
                type="checkbox"
                @change="updateDraft"
              >
              <span class="option-copy">
                <strong>濁音</strong>
                <small>がぎぐげござじずぜぞ等</small>
              </span>
            </label>
            <label class="check-option">
              <input
                v-model="draft.cardOptions.handakuten"
                type="checkbox"
                @change="updateDraft"
              >
              <span class="option-copy">
                <strong>半濁音</strong>
                <small>ぱぴぷぺぽ</small>
              </span>
            </label>
            <label class="check-option">
              <input
                v-model="draft.cardOptions.yoon"
                type="checkbox"
                @change="updateDraft"
              >
              <span class="option-copy">
                <strong>拗音</strong>
                <small>ゃゅょ</small>
              </span>
            </label>
            <label class="check-option">
              <input
                v-model="draft.cardOptions.sokuon"
                type="checkbox"
                @change="updateDraft"
              >
              <span class="option-copy">
                <strong>促音</strong>
                <small>っ</small>
              </span>
            </label>
            <label class="check-option">
              <input
                v-model="draft.cardOptions.prolonged"
                type="checkbox"
                @change="updateDraft"
              >
              <span class="option-copy">
                <strong>伸ばし棒</strong>
                <small>ー</small>
              </span>
            </label>
            <label class="check-option">
              <input
                v-model="draft.cardOptions.smallA"
                type="checkbox"
                @change="updateDraft"
              >
              <span class="option-copy">
                <strong>小さいあ行</strong>
                <small>ぁぃぅぇぉ</small>
              </span>
            </label>
          </div>
          <p class="help-note">基本の清音は常に含まれます。除外した文字も単語入力には使用できます。</p>
        </div>
      </fieldset>

      <!-- 終了条件 -->
      <fieldset class="panel-fieldset">
        <legend class="panel-legend">終了条件</legend>
        <p class="fieldset-note">選択した条件の目標値だけ入力できます。判定は現在のターンを終えてから行います。</p>
        <div class="radio-stack mt-2">
          <div class="radio-row">
            <label class="radio-option">
              <input
                v-model="draft.endCondition"
                type="radio"
                name="ruleEndCondition"
                value="turns"
                @change="updateDraft"
              >
              <span class="option-copy">
                <strong>指定ターン数</strong>
                <small>ターン終了後に結果発表へ進みます</small>
              </span>
            </label>
            <input
              id="targetTurns"
              v-model.number="draft.targetTurns"
              type="number"
              min="1"
              class="number-input"
              :disabled="draft.endCondition !== 'turns'"
              aria-label="ターン数の目標値"
              @input="updateDraft"
            >
          </div>

          <div class="radio-row">
            <label class="radio-option">
              <input
                v-model="draft.endCondition"
                type="radio"
                name="ruleEndCondition"
                value="bingos"
                @change="updateDraft"
              >
              <span class="option-copy">
                <strong>指定ビンゴ数</strong>
                <small>参加プレイヤーの達成をターン終了後に確認します</small>
              </span>
            </label>
            <input
              id="targetBingos"
              v-model.number="draft.targetBingos"
              type="number"
              min="1"
              class="number-input"
              :disabled="draft.endCondition !== 'bingos'"
              aria-label="ビンゴ数の目標値"
              @input="updateDraft"
            >
          </div>
          <p v-if="targetBingosError" class="notice error mt-1">{{ targetBingosError }}</p>
        </div>
      </fieldset>

      <!-- 時間設定 -->
      <fieldset class="panel-fieldset">
        <legend class="panel-legend">時間設定</legend>
        <div class="field-grid">
          <div class="field">
            <label for="timeLimitSeconds" class="field-label">制限時間（秒）</label>
            <input
              id="timeLimitSeconds"
              v-model.number="draft.timeLimitSeconds"
              type="number"
              min="1"
              class="number-input"
              @input="updateDraft"
            >
          </div>
          <div class="field">
            <label for="extraTimeSeconds" class="field-label">初回エクストラ（秒）</label>
            <input
              id="extraTimeSeconds"
              v-model.number="draft.extraTimeSeconds"
              type="number"
              min="0"
              class="number-input"
              @input="updateDraft"
            >
          </div>
        </div>
        <div class="field mt-3">
          <label class="check-option">
            <input
              v-model="draft.forceSkipOnTimeout"
              type="checkbox"
              @change="updateDraft"
            >
            <span class="option-copy">
              <strong>時間切れで強制スキップ</strong>
            </span>
          </label>
        </div>
      </fieldset>

      <!-- 無効入力の扱い -->
      <fieldset class="panel-fieldset">
        <legend class="panel-legend">無効入力の扱い</legend>
        <div class="field-grid">
          <label class="check-option">
            <input
              v-model="draft.invalidAction"
              type="radio"
              name="ruleInvalidAction"
              value="skip"
              @change="updateDraft"
            >
            <span class="option-copy">
              <strong>ターンスキップ</strong>
              <small>カードと開始文字を変えず手番のみ交代</small>
            </span>
          </label>
          <label class="check-option">
            <input
              v-model="draft.invalidAction"
              type="radio"
              name="ruleInvalidAction"
              value="disqualify"
              @change="updateDraft"
            >
            <span class="option-copy">
              <strong>失格</strong>
              <small>そのプレイヤーは以降の手番に参加できません</small>
            </span>
          </label>
        </div>
      </fieldset>

      <!-- プリセット管理 -->
      <fieldset class="panel-fieldset">
        <legend class="panel-legend">設定プリセット</legend>
        <div class="field">
          <label for="presetName" class="field-label">プリセット名</label>
          <input
            id="presetName"
            v-model="presetName"
            type="text"
            class="text-input"
            placeholder="例：3人標準ルール"
          >
        </div>
        <div class="preset-actions mt-3">
          <button
            type="button"
            class="secondary-button btn-sm"
            :disabled="!presetName.trim()"
            @click="onSavePreset"
          >
            {{ selectedPresetId ? '上書き保存' : '保存' }}
          </button>
          <button
            type="button"
            class="secondary-button btn-sm"
            @click="showPresetMenu = !showPresetMenu"
          >
            保存一覧 ({{ presets.presets.value.length }})
          </button>
          <button
            type="button"
            class="secondary-button btn-sm"
            @click="onResetSettings"
          >
            初期値
          </button>
        </div>

        <!-- プリセットドロップダウン/リスト -->
        <div v-if="showPresetMenu" class="preset-menu-box mt-3">
          <div v-if="presets.presets.value.length === 0" class="empty-text p-3">
            保存済みのプリセットはありません。
          </div>
          <ul v-else class="preset-items-list">
            <li
              v-for="preset in presets.presets.value"
              :key="preset.id"
              class="preset-item-row"
            >
              <div class="preset-item-info">
                <strong>{{ preset.name }}</strong>
                <small>{{ new Date(preset.updatedAt).toLocaleDateString() }}</small>
              </div>
              <div class="preset-item-btns">
                <button
                  type="button"
                  class="secondary-button btn-xs"
                  @click="applyPreset(preset.id)"
                >
                  読込
                </button>
                <button
                  type="button"
                  class="secondary-button btn-xs"
                  @click="onSelectPresetToEdit(preset.id)"
                >
                  編集
                </button>
                <button
                  type="button"
                  class="danger-button btn-xs"
                  @click="onDeletePreset(preset.id)"
                >
                  削除
                </button>
              </div>
            </li>
          </ul>
        </div>
      </fieldset>

      <slot />

      <!-- 送信アクションボタン -->
      <div class="settings-actions mt-4">
        <button
          type="submit"
          class="primary-button submit-settings-btn"
          :disabled="isSubmitting || submitDisabled || isInvalid"
        >
          {{ isSubmitting ? '処理中…' : submitButtonText }}
        </button>
      </div>
    </form>
  </div>
</template>

<style scoped>
.rule-settings-form {
  display: grid;
  gap: 16px;
}

.select-input {
  min-height: 42px;
  padding: 8px 12px;
  border: 1px solid #b9b0a4;
  border-radius: 10px;
  background: #fffefa;
  width: 100%;
}

.preset-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.preset-menu-box {
  border: 1px solid var(--line);
  border-radius: 12px;
  background: #fffdfa;
  overflow: hidden;
}

.preset-items-list {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 220px;
  overflow-y: auto;
}

.preset-item-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-bottom: 1px solid var(--line);
  gap: 8px;
}

.preset-item-row:last-child {
  border-bottom: none;
}

.preset-item-info {
  display: grid;
  gap: 2px;
  font-size: 0.9rem;
}

.preset-item-info small {
  color: var(--muted);
  font-size: 0.75rem;
}

.preset-item-btns {
  display: flex;
  gap: 4px;
}

.btn-sm {
  min-height: 32px;
  padding: 4px 10px;
  font-size: 0.82rem;
}

.btn-xs {
  min-height: 26px;
  padding: 2px 8px;
  font-size: 0.75rem;
  border-radius: 6px;
}

.submit-settings-btn {
  width: 100%;
  font-size: 1.05rem;
  padding: 12px 24px;
}

.mt-1 { margin-top: 4px; }
.mt-2 { margin-top: 8px; }
.mt-3 { margin-top: 12px; }
.mt-4 { margin-top: 16px; }
.p-3 { padding: 12px; }
</style>
