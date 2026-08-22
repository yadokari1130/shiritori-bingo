<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useGameStore } from '../store/game'
import { validateWordForFrontend } from '../utils/shiritori'
import BingoCard from './BingoCard.vue'
import DisconnectedMark from './DisconnectedMark.vue'
import RuleExplanationModal from './RuleExplanationModal.vue'

const store = useGameStore()

const inputWord = ref('')
const inputError = ref('')
const inputRef = ref<HTMLInputElement | null>(null)
const isSubmitting = ref(false)
const showRuleModal = ref(false)

const isFirstWord = computed(() => (store.gameState?.wordHistory.length ?? 0) === 0)
const requiredStartChar = computed(() => store.gameState?.requiredStartChar ?? '')

const now = ref(Date.now())
let timerInterval: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  now.value = Date.now()
  timerInterval = setInterval(() => {
    now.value = Date.now()
  }, 100)
})

onUnmounted(() => {
  if (timerInterval) {
    clearInterval(timerInterval)
    timerInterval = null
  }
})

const previewChars = computed(() => {
  const word = inputWord.value.trim()
  if (!word)
    return []
  const chars: string[] = []
  for (const ch of word) {
    if (!chars.includes(ch))
      chars.push(ch)
  }
  return chars
})

const remainingMs = computed(() => {
  const state = store.gameState
  if (!state || state.phase !== 'playing')
    return 0

  if (state.turnStartedAt !== null && state.turnStartedAt !== undefined && state.currentTurnTimeLimitMs > 0) {
    const serverNow = now.value + store.serverTimeOffset
    const elapsed = Math.max(0, serverNow - state.turnStartedAt)
    return Math.max(0, state.currentTurnTimeLimitMs - elapsed)
  }

  return state.remainingTimeMs ?? 0
})

const remainingSeconds = computed(() => {
  return Math.max(0, Math.ceil(remainingMs.value / 1000))
})

const timerWarning = computed(() => {
  return remainingSeconds.value === 0 && !store.gameState?.settings.forceSkipOnTimeout
})

const timerExpired = computed(() => {
  return remainingSeconds.value === 0 && Boolean(store.gameState?.settings.forceSkipOnTimeout)
})

watch(timerExpired, (expired) => {
  if (expired) {
    inputWord.value = ''
    inputError.value = ''
  }
})

const currentPlayerName = computed(() => {
  if (!store.gameState)
    return ''
  if (store.gameState.settings.mode === 'individual') {
    const p = store.gameState.players.find(pl => pl.id === store.gameState!.currentPlayerId)
    return p?.name ?? ''
  }
  const idx = store.gameState.teams.findIndex(t => t.id === store.gameState!.currentTeamId)
  return idx >= 0 ? `チーム ${idx + 1}` : ''
})

const currentSubjectId = computed(() => {
  if (!store.gameState)
    return null
  if (store.gameState.settings.mode === 'individual') {
    return store.gameState.currentPlayerId
  }
  return store.gameState.currentTeamId
})

const orderedCards = computed(() => {
  if (!store.gameState)
    return []
  if (store.gameState.settings.mode === 'individual') {
    return store.orderedPlayers
      .filter(p => Boolean(p.card))
      .map(p => ({
        id: p.id,
        title: p.isCpu ? `🤖 ${p.name}` : p.name,
        subtitle: undefined,
        members: [],
        disconnected: p.connectionStatus === 'disconnected',
        card: p.card!,
        disqualified: p.status === 'disqualified',
      }))
  }
  return store.orderedTeams
    .filter(t => Boolean(t.card))
    .map((t, idx) => ({
      id: t.id,
      title: `チーム ${idx + 1}`,
      subtitle: undefined,
      disconnected: false,
      members: t.memberPlayerIds
        .map(id => store.gameState!.players.find(p => p.id === id))
        .filter((player): player is NonNullable<typeof player> => Boolean(player))
        .map(player => ({
          name: player.isCpu ? `🤖 ${player.name}` : player.name,
          disconnected: player.connectionStatus === 'disconnected',
        })),
      card: t.card!,
      disqualified: t.status === 'disqualified',
    }))
})

const turnProgress = computed(() => {
  const state = store.gameState
  if (!state)
    return ''
  const total = state.roundRoster.length
  const current = Math.min(state.orderIndex + 1, total)
  return `${state.round}ターン目 ${current}/${total}手番`
})

const wordHistoryForDisplay = computed(() => {
  return (store.gameState?.wordHistory ?? []).slice().reverse()
})

watch(
  () => [
    store.gameState?.currentPlayerId,
    store.gameState?.currentTeamId,
    store.gameState?.round,
    store.gameState?.orderIndex,
  ],
  () => {
    inputWord.value = ''
    inputError.value = ''
    store.setAssistMode(false)
    nextTick(() => {
      if (store.canInput && inputRef.value) {
        inputRef.value.focus()
      }
    })
  },
)

function validateInput(): boolean {
  const result = validateWordForFrontend(inputWord.value, {
    inputWordCheck: store.settings.inputWordCheck,
    requiredStartChar: requiredStartChar.value,
    isFirstWord: isFirstWord.value,
    usedWords: store.gameState?.usedWords ?? [],
    minWordLength: store.settings.minWordLength,
    maxWordLength: store.settings.maxWordLength,
  })
  if (!result.valid) {
    inputError.value = result.reason ?? ''
    return false
  }
  inputError.value = ''
  return true
}

async function onSubmitWord(): Promise<void> {
  if (!store.canInput || timerExpired.value)
    return
  if (!validateInput())
    return
  isSubmitting.value = true
  try {
    await store.submitWord(inputWord.value)
    inputWord.value = ''
    inputError.value = ''
  }
  finally {
    isSubmitting.value = false
  }
}

async function onUndo(): Promise<void> {
  if (!store.canUndo)
    return
  await store.submitUndo()
}

async function onSkip(): Promise<void> {
  const id = currentSubjectId.value
  if (!id || !store.isHost)
    return
  await store.submitSkip(id)
}

async function onDisqualify(): Promise<void> {
  const id = currentSubjectId.value
  if (!id || !store.isHost)
    return
  await store.submitDisqualify(id)
}

function onSelectSuggestion(word: string): void {
  inputWord.value = word
  validateInput()
  if (inputRef.value) {
    inputRef.value.focus()
  }
}

function toggleAssistMode(): void {
  store.setAssistMode(!store.assistMode)
}

function formatTime(seconds: number): string {
  return `${seconds}秒`
}

function isCurrentCard(id: string): boolean {
  if (!store.gameState)
    return false
  if (store.gameState.settings.mode === 'individual') {
    return store.gameState.currentPlayerId === id
  }
  return store.gameState.currentTeamId === id
}

function historyKey(entry: { word: string, playerId: string, round: number, sequence: number }, index: number): string {
  return `${entry.round}-${entry.sequence}-${index}`
}
</script>

<template>
  <div class="game-screen">
    <!-- スクリーンヘッダー -->
    <header class="screen-header">
      <div>
        <h1>しりとりビンゴ 対戦中</h1>
      </div>
      <div class="header-actions">
        <button
          type="button"
          class="secondary-button header-btn"
          @click="showRuleModal = true"
        >
          📖 ルール説明
        </button>
        <div class="header-mark">
          対戦
        </div>
      </div>
    </header>

    <!-- エラー・通知表示 -->
    <p v-if="store.errorMessage" class="notice error mb-3">
      {{ store.errorMessage }}
    </p>
    <p v-if="store.noticeMessage" class="notice success mb-3">
      {{ store.noticeMessage }}
    </p>

    <!-- ゲームサマリー（4枚のカード） -->
    <div class="summary-cards-grid">
      <div class="summary-card-item">
        <div class="summary-card">
          <span class="summary-label">現在の手番</span>
          <strong class="summary-value">{{ currentPlayerName || 'なし' }}</strong>
        </div>
      </div>
      <div class="summary-card-item">
        <div class="summary-card">
          <span class="summary-label">現在の開始文字</span>
          <span class="start-letter">{{ requiredStartChar || '—' }}</span>
        </div>
      </div>
      <div class="summary-card-item">
        <div class="summary-card">
          <span class="summary-label">ターン / 終了条件</span>
          <strong class="summary-value">{{ turnProgress }}</strong>
        </div>
      </div>
      <div class="summary-card-item">
        <div
          class="summary-card timer-card"
          :class="{
            'is-expired': timerExpired || (remainingSeconds === 0 && store.gameState?.settings.forceSkipOnTimeout),
            'is-warning': timerWarning,
          }"
        >
          <span class="summary-label">残り制限時間</span>
          <strong class="summary-value time-value">{{ formatTime(remainingSeconds) }}</strong>
          <span v-if="timerExpired" class="timer-status">時間切れ</span>
          <p class="time-note">
            {{ store.gameState?.settings.forceSkipOnTimeout ? '時間切れで強制スキップ' : '時間切れ後も入力できます' }}
          </p>
        </div>
      </div>
    </div>

    <!-- 入力コントロールパネル -->
    <section class="panel control-panel">
      <form class="word-form" @submit.prevent="onSubmitWord">
        <div class="input-field-group">
          <label for="wordInput" class="field-label">しりとりの単語（ひらがな）</label>
          <div class="input-row">
            <input
              id="wordInput"
              ref="inputRef"
              v-model="inputWord"
              type="text"
              class="word-input"
              placeholder="ひらがなで単語を入力"
              autocomplete="off"
              spellcheck="false"
              :disabled="store.canInput && timerExpired"
              @input="validateInput"
            >
            <button
              type="submit"
              class="primary-button"
              :disabled="!store.canInput || timerExpired || isSubmitting"
            >
              {{ isSubmitting ? '送信中…' : '確定' }}
            </button>
            <button
              v-if="store.canUndo"
              type="button"
              class="secondary-button"
              @click="onUndo"
            >
              直前をundo
            </button>
          </div>
        </div>

        <div class="assist-mode-row mt-2 d-flex justify-space-between align-center">
          <div class="assist-toggle">
            <button
              type="button"
              class="assist-toggle-btn"
              :class="{ 'is-active': store.assistMode }"
              @click="toggleAssistMode"
            >
              <span class="assist-icon">💡</span>
              補助モード: {{ store.assistMode ? 'ON' : 'OFF' }}
            </button>
            <span class="assist-description">（有効な単語候補を提案します）</span>
          </div>
          <p class="word-length-counter" aria-live="polite">
            文字数: {{ inputWord.length }}文字
          </p>
        </div>

        <!-- 補助モードの推薦単語チップ -->
        <div v-if="store.assistMode && store.wordSuggestions.length > 0" class="assist-suggestions-box mt-3">
          <span class="assist-suggestions-label">💡 おすすめ単語:</span>
          <div class="assist-chips">
            <button
              v-for="word in store.wordSuggestions"
              :key="word"
              type="button"
              class="assist-chip"
              @click="onSelectSuggestion(word)"
            >
              {{ word }}
            </button>
          </div>
        </div>

        <p v-if="inputError" class="notice error mt-2">
          {{ inputError }}
        </p>
        <p v-else-if="store.isCurrentSubjectCpu" class="help-note cpu-thinking mt-2">
          🤖 CPUが思考中です... 次の手番までお待ちください。
        </p>
        <p v-else-if="!store.canInput" class="help-note mt-2">
          ※他のプレイヤーの手番中です。自分の手番になるまでお待ちください。
        </p>
        <p v-else class="help-note mt-2">
          入力はひらがなと伸ばし棒のみ送信できます。
        </p>

        <!-- ホスト用緊急アクション -->
        <div v-if="store.isHost" class="host-actions mt-3">
          <button
            type="button"
            class="secondary-button btn-sm"
            :disabled="!currentSubjectId"
            @click="onSkip"
          >
            手番をスキップ
          </button>
          <button
            type="button"
            class="danger-button btn-sm ml-2"
            :disabled="!currentSubjectId"
            @click="onDisqualify"
          >
            この手番を失格にする
          </button>
        </div>
      </form>
    </section>

    <!-- メインコンテンツ（ビンゴカードグリッド + サイドパネル） -->
    <div class="playing-content">
      <!-- 左：ビンゴカード一覧 -->
      <section class="panel cards-panel">
        <div class="section-heading">
          <h2>全員のビンゴカード</h2>
        </div>

        <div class="card-grid">
          <BingoCard
            v-for="item in orderedCards"
            :key="item.id"
            :card="item.card"
            :title="item.title"
            :subtitle="item.subtitle"
            :disqualified="item.disqualified"
            :disconnected="item.disconnected"
            :members="item.members"
            :preview-chars="previewChars"
            :is-current="isCurrentCard(item.id)"
          />
        </div>
      </section>

      <!-- 右：サイドパネル（手番順・履歴） -->
      <aside class="panel side-panel">
        <!-- しりとり順 -->
        <section class="side-block">
          <div class="section-heading">
            <h3>しりとり順</h3>
            <p>ゲーム中は固定</p>
          </div>
          <ol class="order-list">
            <li
              v-for="item in orderedCards"
              :key="item.id"
              :class="{
                'is-current': isCurrentCard(item.id),
                'is-disqualified': item.disqualified,
              }"
            >
              <span>{{ item.title }}<DisconnectedMark v-if="item.disconnected" /></span>
              <span class="order-status">
                {{ item.disqualified ? '失格' : (isCurrentCard(item.id) ? '入力中' : '参加中') }}
              </span>
            </li>
          </ol>
        </section>

        <!-- 単語履歴 -->
        <section class="side-block">
          <div class="section-heading">
            <h3>有効単語履歴</h3>
            <p>入力順</p>
          </div>
          <div v-if="wordHistoryForDisplay.length === 0" class="empty-text">
            まだ有効な単語はありません。
          </div>
          <ol v-else class="history-list" reversed>
            <li
              v-for="(entry, idx) in wordHistoryForDisplay"
              :key="historyKey(entry, idx)"
              :value="entry.sequence"
            >
              <span class="history-word">{{ entry.word }}</span>
              <span class="history-meta">
                {{ store.gameState?.players.find((p) => p.id === entry.playerId)?.name ?? '' }}・{{ entry.round }}ターン目
              </span>
            </li>
          </ol>
        </section>
      </aside>
    </div>

    <!-- ルール説明モーダル -->
    <RuleExplanationModal
      v-model="showRuleModal"
      :settings="store.settings"
    />
  </div>
</template>

<style scoped>
.game-screen {
  display: grid;
  gap: 20px;
}

.summary-cards-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  align-items: stretch;
}

@media (max-width: 960px) {
  .summary-cards-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

.summary-card-item {
  display: flex;
  flex-direction: column;
}

.summary-card-item .summary-card {
  height: 100%;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-btn {
  padding: 8px 16px;
  font-size: 0.9rem;
  font-weight: 600;
  white-space: nowrap;
}

.word-form {
  display: grid;
  gap: 8px;
}

.word-length-counter {
  color: var(--muted);
  font-size: 0.85rem;
}

.input-row {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-top: 4px;
}

.input-row .word-input {
  flex: 1;
}

.host-actions {
  display: flex;
  align-items: center;
  padding-top: 10px;
  border-top: 1px solid var(--line);
}

.order-status {
  display: block;
  color: var(--muted);
  font-size: 0.76rem;
}

.order-list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.btn-sm {
  min-height: 34px;
  padding: 4px 12px;
  font-size: 0.82rem;
}

.ml-2 {
  margin-left: 8px;
}
.mt-2 {
  margin-top: 8px;
}
.assist-mode-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.assist-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
}

.assist-toggle-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 9999px;
  font-size: 0.85rem;
  font-weight: 700;
  border: 1px solid var(--line, #cbd5e1);
  background: var(--surface, #f8fafc);
  color: var(--color-text-secondary, #64748b);
  cursor: pointer;
  transition: all 0.2s ease;
}

.assist-toggle-btn.is-active {
  background: #fef3c7;
  color: #b45309;
  border-color: #fcd34d;
}

.assist-description {
  font-size: 0.78rem;
  color: var(--color-text-secondary, #64748b);
}

.assist-suggestions-box {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  background: #fffbeb;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid #fef3c7;
}

.assist-suggestions-label {
  font-size: 0.85rem;
  font-weight: 700;
  color: #92400e;
}

.assist-chips {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.assist-chip {
  padding: 4px 12px;
  border-radius: 16px;
  background: #ffffff;
  border: 1px solid #fde68a;
  color: #b45309;
  font-weight: 700;
  font-size: 0.9rem;
  cursor: pointer;
  transition:
    transform 0.1s ease,
    box-shadow 0.1s ease;
}

.assist-chip:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.06);
  background: #fffdf5;
}

.cpu-thinking {
  color: #6366f1;
  font-weight: 600;
  animation: pulse 1.5s infinite ease-in-out;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.6;
  }
}

@media (max-width: 600px) {
  .input-row {
    flex-wrap: wrap;
  }
  .input-row .word-input {
    width: 100%;
  }
}
</style>
