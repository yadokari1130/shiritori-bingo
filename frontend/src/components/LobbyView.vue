<script setup lang="ts">
import type { Settings } from '../types'
import { computed, ref, watch } from 'vue'
import { useConfirm } from '../composables/useConfirm'
import { useGameStore } from '../store/game'
import { buildCardCharPool, maxCardSize } from '../utils/shiritori'
import DisconnectedMark from './DisconnectedMark.vue'
import RuleExplanationModal from './RuleExplanationModal.vue'
import RuleSettingsForm from './RuleSettingsForm.vue'

const store = useGameStore()
const { showConfirm } = useConfirm()

const editingName = ref('')
const editNameError = ref('')
const editSettings = ref<Settings>({ ...store.draftSettings })
const isUpdating = ref(false)
const copied = ref(false)
const showRuleModal = ref(false)

let lastSyncedSettingsJson = ''
watch(
  () => store.settings,
  (s) => {
    const sJson = JSON.stringify(s)
    if (sJson !== lastSyncedSettingsJson) {
      lastSyncedSettingsJson = sJson
      editSettings.value = {
        ...s,
        cardOptions: { ...s.cardOptions },
      }
    }
  },
  { immediate: true, deep: true },
)

let lastSyncedPlayerName = ''
watch(
  () => store.myPlayer?.name,
  (name) => {
    if (name && name !== lastSyncedPlayerName) {
      lastSyncedPlayerName = name
      editingName.value = name
    }
  },
  { immediate: true },
)

const roomUrl = computed(() => {
  if (!store.roomId)
    return ''
  return `${window.location.origin}/game/${store.roomId}`
})

const MAX_PLAYERS_PER_ROOM = 20
const MAX_CPUS_PER_ROOM = 10

const isAddingCpu = ref(false)
const isDeletingCpus = ref(false)
const cpuCount = computed(() => store.players.filter(p => p.isCpu).length)
const canAddCpu = computed(() => cpuCount.value < MAX_CPUS_PER_ROOM && store.players.length < MAX_PLAYERS_PER_ROOM)
const isCpuLimitReached = computed(() => cpuCount.value >= MAX_CPUS_PER_ROOM)
const isRoomFull = computed(() => store.players.length >= MAX_PLAYERS_PER_ROOM)

async function onAddCpu(): Promise<void> {
  if (!canAddCpu.value)
    return
  isAddingCpu.value = true
  try {
    await store.addCpu()
  }
  finally {
    isAddingCpu.value = false
  }
}

async function onDeleteAllCpus(): Promise<void> {
  const count = cpuCount.value
  if (count === 0)
    return
  const confirmed = await showConfirm({
    title: 'CPUの一括削除',
    message: `すべてのCPUプレイヤー（${count}体）を一括削除しますか？`,
    confirmText: '一括削除する',
    danger: true,
  })
  if (!confirmed)
    return

  isDeletingCpus.value = true
  try {
    await store.deleteAllCpus()
  }
  finally {
    isDeletingCpus.value = false
  }
}

const canStart = computed(() => {
  const state = store.gameState
  if (!state)
    return false
  if (!store.isHost)
    return false
  if (state.players.length < 2)
    return false
  const humanPlayers = state.players.filter(p => !p.isCpu)
  if (humanPlayers.length < 1)
    return false

  const s = editSettings.value
  const pool = buildCardCharPool(s.cardOptions)
  const max = maxCardSize(pool)
  if (s.cardSize < 3 || s.cardSize % 2 === 0 || s.cardSize > max)
    return false

  if (s.endCondition === 'turns' && s.targetTurns <= 0)
    return false
  if (s.endCondition === 'bingos' && (s.targetBingos < 1 || s.targetBingos > s.cardSize * 2 + 2))
    return false

  if (s.mode === 'team') {
    if (s.teamCount > state.players.length)
      return false
    const teamIds = new Set<string>()
    for (const p of state.players) {
      if (p.teamId)
        teamIds.add(p.teamId)
    }
    if (teamIds.size < s.teamCount)
      return false
  }

  return true
})

function copyUrl(): void {
  if (!roomUrl.value)
    return
  navigator.clipboard.writeText(roomUrl.value).then(() => {
    copied.value = true
    setTimeout(() => (copied.value = false), 2000)
  })
}

const isSubmittingName = ref(false)
const joinPassword = ref(store.lastCreatedPassword || '')
const showJoinPassword = ref(false)

watch(
  () => store.lastCreatedPassword,
  (pwd) => {
    if (pwd && !joinPassword.value) {
      joinPassword.value = pwd
    }
  },
  { immediate: true },
)

async function onSubmitName(): Promise<void> {
  const name = editingName.value.trim()
  if (!name) {
    editNameError.value = '名前を入力してください。'
    return
  }
  if (!store.roomId)
    return

  editNameError.value = ''
  isSubmittingName.value = true
  try {
    if (!store.myPlayer) {
      await store.joinRoom(store.roomId, name, joinPassword.value || null)
    }
    else {
      await store.updateName(name)
    }
  }
  catch {
    // エラーはストアに格納済み
  }
  finally {
    isSubmittingName.value = false
  }
}

async function onUpdateSettings(): Promise<void> {
  isUpdating.value = true
  try {
    await store.updateSettings({ ...editSettings.value })
  }
  finally {
    isUpdating.value = false
  }
}

async function onStartGame(): Promise<void> {
  await store.startGame(editSettings.value)
}

async function onChangeHost(playerId: string, playerName: string): Promise<void> {
  const ok = await showConfirm({
    title: '親（ホスト）の変更',
    message: `${playerName} さんを親（ホスト）に変更しますか？`,
    confirmText: '変更する',
  })
  if (!ok)
    return
  await store.changeHost(playerId)
}

async function onKickPlayer(playerId: string, playerName: string): Promise<void> {
  const ok = await showConfirm({
    title: '参加者の強制退出',
    message: `${playerName} さんを強制退出させますか？`,
    confirmText: '退出させる',
    danger: true,
  })
  if (!ok)
    return
  await store.kickPlayer(playerId)
}

async function onSelectTeam(teamId: string | null): Promise<void> {
  await store.selectTeam(teamId)
}

async function onRandomizeTeams(): Promise<void> {
  await store.randomizeTeams()
}

function teamLabel(index: number): string {
  return `チーム ${index + 1}`
}

function teamMemberNames(teamId: string): string {
  if (!store.gameState)
    return ''
  return store.gameState.players
    .filter((p: { teamId: string | null, name: string }) => p.teamId === teamId)
    .map((p: { teamId: string | null, name: string }) => p.name)
    .join('、')
}

function formatWordLengthLimit(settings: Settings): string {
  const min = settings.minWordLength
  const max = settings.maxWordLength
  if (min !== null && max !== null) {
    return `${min}〜${max}文字`
  }
  if (min !== null) {
    return `${min}文字以上`
  }
  if (max !== null) {
    return `${max}文字以下`
  }
  return '制限なし'
}

async function onGoToTop(): Promise<void> {
  if (store.myPlayer) {
    const ok = await showConfirm({
      title: '部屋を抜ける',
      message: '部屋から抜けてトップ画面へ戻りますか？',
      confirmText: '抜ける',
    })
    if (!ok)
      return
  }
  await store.leaveAndGoToTop()
}

async function onDissolveRoom(): Promise<void> {
  const ok = await showConfirm({
    title: '部屋の解散',
    message: '部屋を解散しますか？\n部屋は削除され、参加者全員が退出となります。',
    confirmText: '解散する',
    danger: true,
  })
  if (!ok)
    return
  await store.dissolveRoom()
}
</script>

<template>
  <div class="lobby-view">
    <header class="screen-header">
      <div class="header-left">
        <h1>しりとりビンゴ ロビー</h1>
        <p>参加者が集まるまで待機してください。親（ホスト）が設定を確認してゲームを開始します。</p>
      </div>
      <div class="header-actions">
        <button
          type="button"
          class="secondary-button header-btn"
          @click="showRuleModal = true"
        >
          📖 ルール説明
        </button>
        <button
          type="button"
          class="secondary-button header-btn"
          @click="onGoToTop"
        >
          部屋を抜ける
        </button>
        <button
          v-if="store.isHost"
          type="button"
          class="danger-button header-btn"
          @click="onDissolveRoom"
        >
          部屋を解散する
        </button>
      </div>
    </header>

    <p v-if="store.errorMessage" class="notice error mb-4">
      {{ store.errorMessage }}
    </p>

    <div class="lobby-grid">
      <!-- 左列：ルーム情報・参加者一覧・操作 -->
      <div class="lobby-grid-main">
        <div class="lobby-main-col">
          <!-- 招待URL -->
          <section class="panel setup-panel mb-4">
            <div class="section-heading">
              <div class="heading-with-badge">
                <h2>参加用URL</h2>
                <span v-if="store.hasPassword" class="tag-badge password-badge">🔒 パスワード設定あり</span>
                <span v-else class="tag-badge public-badge">🔓 パスワードなし</span>
              </div>
              <p>このURLを他のプレイヤーに共有して招待します<span v-if="store.hasPassword">（参加時に合言葉が必要です）</span></p>
            </div>
            <div class="url-row">
              <input
                :value="roomUrl"
                type="text"
                class="text-input"
                readonly
              >
              <button
                type="button"
                class="secondary-button"
                @click="copyUrl"
              >
                {{ copied ? 'コピー完了！' : 'URLをコピー' }}
              </button>
            </div>
          </section>

          <!-- 参加者一覧 -->
          <section class="panel setup-panel mb-4">
            <div class="section-heading">
              <h2>参加プレイヤー ({{ store.players.length }}人)</h2>
              <p>2人以上で対戦を開始できます</p>
            </div>

            <ul class="players-list">
              <li
                v-for="player in store.players"
                :key="player.id"
                class="player-item"
                :class="{ 'is-me': player.id === store.myPlayerId }"
              >
                <div class="player-info">
                  <strong>{{ player.name }}<DisconnectedMark v-if="player.connectionStatus === 'disconnected'" /></strong>
                  <span v-if="player.id === store.myPlayerId" class="tag-badge current-badge">あなた</span>
                  <span v-if="player.isCpu" class="tag-badge cpu-badge">🤖 CPU</span>
                </div>
                <div class="player-right">
                  <div class="player-badges">
                    <span v-if="player.id === store.gameState?.hostPlayerId && !player.isCpu" class="status-badge">
                      親（ホスト）
                    </span>
                  </div>
                  <div v-if="store.isHost && player.id !== store.myPlayerId" class="player-actions">
                    <button
                      v-if="!player.isCpu"
                      type="button"
                      class="secondary-button btn-xs"
                      @click="onChangeHost(player.id, player.name)"
                    >
                      親にする
                    </button>
                    <button
                      type="button"
                      class="danger-button btn-xs"
                      @click="onKickPlayer(player.id, player.name)"
                    >
                      {{ player.isCpu ? '削除' : '退出' }}
                    </button>
                  </div>
                </div>
              </li>
            </ul>

            <div v-if="store.isHost" class="cpu-actions-container mt-3">
              <button
                type="button"
                class="secondary-button"
                :disabled="isAddingCpu || isDeletingCpus || !canAddCpu"
                @click="onAddCpu"
              >
                {{ isAddingCpu ? '追加中...' : '🤖 CPUプレイヤーを追加' }}
              </button>
              <button
                v-if="cpuCount > 0"
                type="button"
                class="danger-button"
                :disabled="isAddingCpu || isDeletingCpus"
                @click="onDeleteAllCpus"
              >
                {{ isDeletingCpus ? '削除中...' : '🗑️ CPUを一括削除' }}
              </button>
              <p v-if="isRoomFull" class="notice warning mt-1">
                部屋の定員（{{ MAX_PLAYERS_PER_ROOM }}名）に達しているため、これ以上追加できません。
              </p>
              <p v-else-if="isCpuLimitReached" class="notice warning mt-1">
                CPUプレイヤーは最大{{ MAX_CPUS_PER_ROOM }}体まで追加できます。
              </p>
            </div>

            <div class="name-edit-box mt-4">
              <label for="editMyName" class="field-label">
                {{ store.myPlayer ? '名前を変更する' : '名前を入力して参加' }}
              </label>
              <div v-if="!store.myPlayer && store.hasPassword && !store.isCreator" class="password-field mb-2">
                <label for="lobbyJoinPassword" class="field-label password-sublabel">合言葉・パスワード</label>
                <div class="password-input-wrap">
                  <input
                    id="lobbyJoinPassword"
                    v-model="joinPassword"
                    :type="showJoinPassword ? 'text' : 'password'"
                    class="text-input"
                    placeholder="パスワードを入力"
                    @keydown.enter="onSubmitName"
                  >
                  <button
                    type="button"
                    class="toggle-pwd-btn"
                    :aria-label="showJoinPassword ? 'パスワードを隠す' : 'パスワードを表示'"
                    @click="showJoinPassword = !showJoinPassword"
                  >
                    {{ showJoinPassword ? '非表示' : '表示' }}
                  </button>
                </div>
              </div>
              <div class="name-input-row">
                <input
                  id="editMyName"
                  v-model="editingName"
                  type="text"
                  class="text-input"
                  :placeholder="store.myPlayer ? '新しい名前' : '名前を入力'"
                  @keydown.enter="onSubmitName"
                >
                <button
                  type="button"
                  class="secondary-button"
                  :disabled="isSubmittingName || !editingName.trim()"
                  @click="onSubmitName"
                >
                  {{ isSubmittingName ? '更新中…' : (store.myPlayer ? '名前変更' : '参加する') }}
                </button>
              </div>
              <p v-if="editNameError" class="notice error mt-2">
                {{ editNameError }}
              </p>
            </div>
          </section>

          <!-- チーム分け（チーム戦時） -->
          <section v-if="store.gameState?.settings.mode === 'team'" class="panel setup-panel mb-4">
            <div class="section-heading">
              <h2>チーム編成</h2>
              <p>所属するチームを選択してください</p>
            </div>

            <div class="teams-grid">
              <div
                v-for="team in store.teams"
                :key="team.id"
                class="team-box"
                :class="{ 'is-my-team': team.id === store.myPlayer?.teamId }"
              >
                <div class="team-title-row">
                  <strong>{{ teamLabel(store.teams.indexOf(team)) }}</strong>
                  <span v-if="team.id === store.myPlayer?.teamId" class="status-badge">所属中</span>
                </div>
                <p class="team-members">
                  {{ teamMemberNames(team.id) || '（未所属）' }}
                </p>
                <div class="team-action">
                  <button
                    v-if="team.id !== store.myPlayer?.teamId"
                    type="button"
                    class="secondary-button btn-sm"
                    @click="onSelectTeam(team.id)"
                  >
                    このチームに入る
                  </button>
                  <button
                    v-else
                    type="button"
                    class="danger-button btn-sm"
                    @click="onSelectTeam(null)"
                  >
                    抜ける
                  </button>
                </div>
              </div>
            </div>

            <div v-if="store.isHost" class="mt-3">
              <button
                type="button"
                class="secondary-button btn-sm"
                @click="onRandomizeTeams"
              >
                未所属者を均等に振り分ける
              </button>
            </div>
          </section>

          <!-- 親の操作（開始・解散） -->
          <section v-if="store.isHost" class="panel setup-panel mb-4 host-action-panel">
            <div class="section-heading">
              <h2>親の操作</h2>
              <p>全員が揃ったらゲームを開始してください</p>
            </div>

            <div class="host-action-buttons">
              <button
                type="button"
                class="primary-button start-game-btn"
                :disabled="!canStart"
                @click="onStartGame"
              >
                ゲームを開始する
              </button>
              <button
                type="button"
                class="danger-button dissolve-room-btn"
                @click="onDissolveRoom"
              >
                部屋を解散する
              </button>
            </div>
            <p v-if="!canStart" class="help-note mt-2 text-danger">
              ※2人以上の参加、正しいルール設定、チーム戦では各チームに最低1人の所属が必要です。
            </p>
          </section>

          <section v-else class="panel setup-panel mb-4">
            <p class="notice info">
              親（ホスト）がゲームを開始するのを待機しています…
            </p>
          </section>
        </div>
      </div>

      <!-- 右列：ルール設定プレビュー／編集（親のみ編集可能） -->
      <div class="lobby-grid-side">
        <div class="lobby-side-col">
          <section class="panel setup-panel">
            <div class="section-heading">
              <h2>{{ store.isHost ? 'ルール設定の変更' : 'ルール設定' }}</h2>
              <p>{{ store.isHost ? '変更後に「設定を反映」を押してください' : '現在のゲーム設定' }}</p>
            </div>

            <RuleSettingsForm
              v-if="store.isHost"
              v-model="editSettings"
              submit-button-text="設定を反映する"
              :is-submitting="isUpdating"
              @submit="onUpdateSettings"
            />

            <!-- 参加者視点（設定プレビューのみ） -->
            <div v-else class="settings-preview">
              <p><strong>モード:</strong> {{ store.settings.mode === 'team' ? `チーム戦 (${store.settings.teamCount}チーム)` : '個人戦' }}</p>
              <p><strong>カード:</strong> {{ store.settings.cardSize }}×{{ store.settings.cardSize }} マス</p>
              <p>
                <strong>終了条件:</strong>
                {{ store.settings.endCondition === 'turns' ? `指定ターン数 (${store.settings.targetTurns}ターン)` : `指定ビンゴ数 (${store.settings.targetBingos}本達成)` }}
              </p>
              <p>
                <strong>時間設定:</strong>
                制限時間 {{ store.settings.timeLimitSeconds }}秒 / 初回エクストラ {{ store.settings.extraTimeSeconds }}秒{{ store.settings.forceSkipOnTimeout ? '（時間切れで強制スキップ）' : '' }}
              </p>
              <p><strong>無効入力の扱い:</strong> {{ store.settings.invalidAction === 'disqualify' ? '失格' : 'ターンスキップ' }}</p>
              <p>
                <strong>エクストラルール:</strong>
                入力文字チェック: {{ store.settings.inputWordCheck ? '有効' : '無効' }} /
                文字数制限: {{ formatWordLengthLimit(store.settings) }}
              </p>
            </div>
          </section>
        </div>
      </div>
    </div>

    <!-- ルール説明モーダル -->
    <RuleExplanationModal
      v-model="showRuleModal"
      :settings="store.isHost ? editSettings : store.settings"
    />
  </div>
</template>

<style scoped>
.lobby-view {
  display: grid;
  gap: 20px;
}

.lobby-grid {
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 20px;
  align-items: start;
}

@media (max-width: 1024px) {
  .lobby-grid {
    grid-template-columns: 1fr;
  }
}

.url-row {
  display: flex;
  gap: 10px;
  align-items: center;
}

.players-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 8px;
}

.player-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid var(--line);
  background: #fffefa;
}

.player-item.is-me {
  border-color: var(--teal);
  background: var(--teal-pale);
}

.player-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.cpu-actions-container {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.cpu-actions-container button {
  flex: 1 1 auto;
}

.name-input-row {
  display: flex;
  gap: 10px;
  align-items: center;
}

.teams-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

.team-box {
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: #fffefa;
  display: grid;
  gap: 6px;
}

.team-box.is-my-team {
  border: 2px solid var(--coral);
  background: #fff5f2;
}

.team-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.team-members {
  margin: 0;
  font-size: 0.85rem;
  color: var(--muted);
  min-height: 1.4em;
}

.start-game-btn {
  width: 100%;
  font-size: 1.1rem;
  padding: 12px 20px;
}

.player-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.player-actions {
  display: flex;
  align-items: center;
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

.settings-preview p {
  margin: 8px 0;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--line);
  font-size: 0.95rem;
}

.text-danger {
  color: var(--danger);
}

.mt-2 {
  margin-top: 8px;
}
.mt-3 {
  margin-top: 12px;
}
.mt-4 {
  margin-top: 16px;
}
.mb-4 {
  margin-bottom: 16px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.header-btn {
  padding: 8px 16px;
  font-size: 0.9rem;
  font-weight: 600;
  white-space: nowrap;
}

.host-action-buttons {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 10px;
}

.dissolve-room-btn {
  padding: 12px 18px;
  font-size: 0.95rem;
  white-space: nowrap;
}

@media (max-width: 600px) {
  .host-action-buttons {
    grid-template-columns: 1fr;
  }
}

.heading-with-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.password-badge {
  background: var(--coral-pale, #fff0eb);
  color: var(--coral, #d9534f);
  border: 1px solid var(--coral);
  font-size: 0.78rem;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 999px;
}

.public-badge {
  background: #f0fdf4;
  color: #15803d;
  border: 1px solid #86efac;
  font-size: 0.78rem;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 999px;
}

.password-sublabel {
  font-size: 0.85rem;
  color: var(--muted);
  margin-bottom: 4px;
}

.password-input-wrap {
  position: relative;
  display: flex;
  align-items: center;
}

.password-input-wrap .text-input {
  padding-right: 64px;
}

.toggle-pwd-btn {
  position: absolute;
  right: 8px;
  padding: 4px 8px;
  font-size: 0.78rem;
  background: var(--bg-card);
  border: 1px solid var(--line);
  border-radius: 6px;
  color: var(--muted);
  cursor: pointer;
  transition: all 0.15s ease;
}

.toggle-pwd-btn:hover {
  background: var(--bg-hover, #f0ebe1);
  color: var(--fg-main);
}

.mb-2 {
  margin-bottom: 8px;
}
</style>
