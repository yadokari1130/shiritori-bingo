<script setup lang="ts">
import { ref, watch } from 'vue'
import { useGameStore } from '../store/game'
import { usePresets } from '../composables/usePresets'
import { createDefaultSettings, type Settings } from '../types'

const store = useGameStore()
const presets = usePresets()

const isCreating = ref(false)
const presetName = ref('')
const selectedPresetId = ref<string | null>(null)
const showPresetMenu = ref(false)

const draft = ref<Settings>({ ...store.draftSettings })

watch(
  () => store.draftSettings,
  (s) => {
    draft.value = { ...s }
  },
  { immediate: true },
)

async function onCreateRoom(): Promise<void> {
  store.draftSettings = { ...draft.value }
  isCreating.value = true
  store.clearError()
  try {
    await store.createRoom()
  } finally {
    isCreating.value = false
  }
}

function applyPreset(presetId: string): void {
  const settings = presets.applyPreset(presetId)
  if (settings) {
    draft.value = settings
    selectedPresetId.value = presetId
    showPresetMenu.value = false
  }
}

function onSavePreset(): void {
  const name = presetName.value.trim()
  if (!name) return
  if (selectedPresetId.value) {
    presets.updatePreset(selectedPresetId.value, name, { ...draft.value })
  } else {
    const preset = presets.addPreset(name, { ...draft.value })
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
}

function onSelectPresetToEdit(presetId: string): void {
  const settings = presets.applyPreset(presetId)
  if (settings) {
    draft.value = settings
    selectedPresetId.value = presetId
    presetName.value = presets.presets.value.find((p) => p.id === presetId)?.name ?? ''
    showPresetMenu.value = false
  }
}
</script>

<template>
  <div class="top-rule-settings">
    <form class="settings-form" @submit.prevent="onCreateRoom">
      <!-- 参加者・モード設定 -->
      <fieldset class="panel-fieldset">
        <legend class="panel-legend">モード設定</legend>
        <div class="field-grid">
          <div class="field">
            <label for="gameMode" class="field-label">対戦モード</label>
            <select
              id="gameMode"
              v-model="draft.mode"
              class="text-input select-input"
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
            >
            <p class="field-note">3以上の奇数。中央がFREEマスになります。</p>
          </div>
        </div>

        <div class="field mt-3">
          <span class="field-label">カードに含める文字カテゴリ</span>
          <div class="options-grid">
            <label class="check-option">
              <input v-model="draft.cardOptions.dakuten" type="checkbox">
              <span class="option-copy">
                <strong>濁音</strong>
                <small>がぎぐげござじずぜぞ等</small>
              </span>
            </label>
            <label class="check-option">
              <input v-model="draft.cardOptions.handakuten" type="checkbox">
              <span class="option-copy">
                <strong>半濁音</strong>
                <small>ぱぴぷぺぽ</small>
              </span>
            </label>
            <label class="check-option">
              <input v-model="draft.cardOptions.yoon" type="checkbox">
              <span class="option-copy">
                <strong>拗音</strong>
                <small>ゃゅょ</small>
              </span>
            </label>
            <label class="check-option">
              <input v-model="draft.cardOptions.sokuon" type="checkbox">
              <span class="option-copy">
                <strong>促音</strong>
                <small>っ</small>
              </span>
            </label>
            <label class="check-option">
              <input v-model="draft.cardOptions.prolonged" type="checkbox">
              <span class="option-copy">
                <strong>伸ばし棒</strong>
                <small>ー</small>
              </span>
            </label>
            <label class="check-option">
              <input v-model="draft.cardOptions.smallA" type="checkbox">
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
                name="endCondition"
                value="turns"
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
            >
          </div>

          <div class="radio-row">
            <label class="radio-option">
              <input
                v-model="draft.endCondition"
                type="radio"
                name="endCondition"
                value="bingos"
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
            >
          </div>
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
            >
          </div>
        </div>
        <div class="field mt-3">
          <label class="check-option">
            <input v-model="draft.forceSkipOnTimeout" type="checkbox">
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
              name="invalidAction"
              value="skip"
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
              name="invalidAction"
              value="disqualify"
            >
            <span class="option-copy">
              <strong>失格</strong>
              <small>そのプレイヤーは以降の手番に参加できません</small>
            </span>
          </label>
        </div>
      </fieldset>

      <!-- エクストラルール -->
      <details class="extra-settings">
        <summary class="panel-fieldset panel-legend">エクストラルール</summary>
        <div class="extra-settings-body">
          <div class="field">
            <label class="check-option">
              <input v-model="draft.inputWordCheck" type="checkbox">
              <span class="option-copy">
                <strong>入力文字チェック</strong>
                <small>有効の場合、しりとり接続や文字数制限、既出単語などの無効な単語の送信を防ぎます</small>
              </span>
            </label>
          </div>
          <p class="fieldset-note mt-3">単語の文字数を制限できます。設定した範囲外の単語は無効入力として扱います。</p>
          <div class="field-grid mt-2">
            <div class="field">
              <label for="topMinWordLength" class="field-label">最小文字数</label>
              <div class="number-input-row">
                <input
                  id="topMinWordLength"
                  v-model.number="draft.minWordLength"
                  type="number"
                  min="1"
                  class="number-input"
                  placeholder="制限なし"
                >
                <button
                  type="button"
                  class="secondary-button btn-sm"
                  :disabled="draft.minWordLength === null"
                  @click="draft.minWordLength = null"
                >
                  クリア
                </button>
              </div>
            </div>
            <div class="field">
              <label for="topMaxWordLength" class="field-label">最大文字数</label>
              <div class="number-input-row">
                <input
                  id="topMaxWordLength"
                  v-model.number="draft.maxWordLength"
                  type="number"
                  min="1"
                  class="number-input"
                  placeholder="制限なし"
                >
                <button
                  type="button"
                  class="secondary-button btn-sm"
                  :disabled="draft.maxWordLength === null"
                  @click="draft.maxWordLength = null"
                >
                  クリア
                </button>
              </div>
            </div>
          </div>
        </div>
      </details>

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
          <button type="button" class="secondary-button btn-sm" @click="onResetSettings">
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

      <!-- ルーム作成アクション -->
      <div class="settings-actions mt-4">
        <button
          type="submit"
          class="primary-button create-room-btn"
          :disabled="isCreating"
        >
          {{ isCreating ? 'ルーム作成中…' : 'ルームを作成' }}
        </button>
      </div>
    </form>
  </div>
</template>

<style scoped>
.top-rule-settings {
  display: grid;
  gap: 16px;
}

.extra-settings {
  display: block;
}

.extra-settings > summary {
  cursor: pointer;
  list-style-position: inside;
}

.extra-settings-body {
  padding: 16px;
  border: 1px solid var(--line);
  border-top: none;
  background: #fffdfa;
}

.number-input-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.number-input-row .number-input {
  flex: 1;
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

.create-room-btn {
  width: 100%;
  font-size: 1.05rem;
  padding: 12px 24px;
}

.mt-2 { margin-top: 8px; }
.mt-3 { margin-top: 12px; }
.mt-4 { margin-top: 16px; }
.p-3 { padding: 12px; }
</style>
