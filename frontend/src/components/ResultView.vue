<script setup lang="ts">
import { computed, ref } from 'vue'
import { useConfirm } from '../composables/useConfirm'
import { useGameStore } from '../store/game'
import { buildCharOpenStateColumns, collectOpenedChars } from '../utils/bingo'
import { isSmallKana } from '../utils/shiritori'
import BingoCard from './BingoCard.vue'
import DisconnectedMark from './DisconnectedMark.vue'

const store = useGameStore()
const { showConfirm } = useConfirm()

const showCards = ref(true)
const showCharTable = ref(true)
const showHistory = ref(true)

const result = computed(() => store.gameState?.result)

const reasonText = computed(() => {
  const r = result.value
  if (!r)
    return ''
  switch (r.reason) {
    case 'turns':
      return `${r.endRound}ターンが終了しました。`
    case 'bingos':
      return `${r.endRound}ターンで指定ビンゴ数に到達しました。`
    case 'all_disqualified':
      return '全員が失格となったためゲームを終了しました。'
    default:
      return ''
  }
})

const snapshot = computed(() => result.value?.snapshot)
const settings = computed(() => snapshot.value?.settings ?? store.gameState?.settings)

const orderedResults = computed(() => {
  if (!snapshot.value)
    return []
  if (snapshot.value.settings.mode === 'individual') {
    return snapshot.value.players
      .filter((p): p is typeof p & { card: NonNullable<typeof p.card> } => Boolean(p.card))
      .map(p => ({
        id: p.playerId,
        title: p.isCpu ? `🤖 ${p.name}` : p.name,
        subtitle: p.teamId ? 'チーム所属' : undefined,
        members: [],
        disconnected: p.connectionStatus === 'disconnected',
        card: p.card,
        disqualified: p.status === 'disqualified',
      }))
  }
  return snapshot.value.teams
    .filter((t): t is typeof t & { card: NonNullable<typeof t.card> } => Boolean(t.card))
    .map((t, idx) => ({
      id: t.teamId,
      title: `チーム ${idx + 1}`,
      subtitle: undefined,
      disconnected: false,
      members: t.memberPlayerIds
        .map(id => snapshot.value!.players.find(p => p.playerId === id))
        .filter((player): player is NonNullable<typeof player> => Boolean(player))
        .map(player => ({
          name: player.isCpu ? `🤖 ${player.name}` : player.name,
          disconnected: player.connectionStatus === 'disconnected',
        })),
      card: t.card,
      disqualified: t.status === 'disqualified',
    }))
})

const charColumns = computed(() => {
  const s = settings.value
  if (!s)
    return []
  return buildCharOpenStateColumns(s.cardOptions)
})

const openedChars = computed(() => {
  if (!snapshot.value)
    return new Set<string>()
  const cards = snapshot.value.settings.mode === 'individual'
    ? snapshot.value.players.map(p => p.card).filter((card): card is NonNullable<typeof card> => card !== null)
    : snapshot.value.teams.map(t => t.card)
  return collectOpenedChars(cards)
})

const history = computed(() => snapshot.value?.wordHistory ?? [])

function isOpenedChar(char: string | null): boolean {
  if (!char)
    return false
  return openedChars.value.has(char)
}

function historyKey(entry: { word: string, playerId: string, round: number, sequence: number }, index: number): string {
  return `${entry.round}-${entry.sequence}-${index}`
}

async function onReturnToLobby(): Promise<void> {
  await store.returnToLobby()
}

async function onGoToTop(): Promise<void> {
  if (store.myPlayer) {
    const ok = await showConfirm({
      title: 'トップ画面へ戻る',
      message: 'トップ画面へ戻りますか？',
      confirmText: '戻る',
    })
    if (!ok)
      return
  }
  await store.leaveAndGoToTop()
}
</script>

<template>
  <div class="result-screen">
    <!-- スクリーンヘッダー -->
    <header class="screen-header">
      <div>
        <h1>しりとりビンゴ 結果発表</h1>
        <p>対戦結果と各プレイヤーのビンゴ達成状況を確認します。</p>
      </div>
      <div class="header-actions">
        <button
          type="button"
          class="secondary-button header-btn"
          @click="onGoToTop"
        >
          トップに戻る
        </button>
        <div class="header-mark">
          結果
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

    <!-- 結果サマリー -->
    <section class="panel summary-panel">
      <div class="summary-content">
        <div class="summary-badge">
          GAME SET
        </div>
        <p class="summary-reason">
          {{ reasonText }}
        </p>
        <p class="summary-sub">
          終了ターン: {{ result?.endRound ?? 0 }}ターン目
        </p>
      </div>
    </section>

    <!-- 順位セクション -->
    <section class="panel result-section">
      <div class="section-heading">
        <h2>順位</h2>
        <p>ビンゴ成立本数 → 開放マス数の順で判定</p>
      </div>

      <div class="ranking-table-wrap">
        <table class="ranking-table">
          <thead>
            <tr>
              <th>順位</th>
              <th>プレイヤー名</th>
              <th>ビンゴ数</th>
              <th>開いたマス数</th>
              <th>状態</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="ranking in result?.rankings ?? []"
              :key="ranking.subjectId"
              :class="{ 'disqualified-row': ranking.status === 'disqualified' }"
            >
              <td>
                <strong v-if="ranking.rank !== null">{{ ranking.rank }}位</strong>
                <span v-else class="text-danger">失格</span>
              </td>
              <td>
                <strong>
                  {{
                    snapshot?.players.find((p) => p.playerId === ranking.subjectId)?.name
                      ?? (snapshot?.teams.find((t) => t.teamId === ranking.subjectId)
                        ? `チーム ${(snapshot?.teams.findIndex((t) => t.teamId === ranking.subjectId) ?? 0) + 1}`
                        : '')
                  }}
                  <span v-if="snapshot?.players.find((p) => p.playerId === ranking.subjectId)?.isCpu" class="tag-badge cpu-badge ml-1">🤖 CPU</span>
                  <DisconnectedMark
                    v-if="ranking.subjectType === 'player' && snapshot?.players.find((p) => p.playerId === ranking.subjectId)?.connectionStatus === 'disconnected'"
                  />
                </strong>
              </td>
              <td>{{ ranking.bingoCount }}本</td>
              <td>{{ ranking.openedCellCount }}マス</td>
              <td>
                <span
                  class="status-chip"
                  :class="ranking.status === 'disqualified' ? 'is-disqualified' : 'is-active'"
                >
                  {{ ranking.status === 'disqualified' ? '失格' : '有効' }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- 全員のカードセクション -->
    <section class="panel result-section">
      <div class="section-header-toggle" @click="showCards = !showCards">
        <div class="section-heading">
          <h2>全員のビンゴカード</h2>
          <p>最終結果の盤面</p>
        </div>
        <button type="button" class="toggle-btn" :aria-expanded="showCards">
          {{ showCards ? '▲ 閉じる' : '▼ 開く' }}
        </button>
      </div>

      <div v-show="showCards" class="card-grid mt-3">
        <BingoCard
          v-for="item in orderedResults"
          :key="item.id"
          :card="item.card"
          :title="item.title"
          :subtitle="item.subtitle"
          :disqualified="item.disqualified"
          :disconnected="item.disconnected"
          :members="item.members"
        />
      </div>
    </section>

    <!-- 開放文字一覧（あいうえお表） -->
    <section class="panel result-section">
      <div class="section-header-toggle" @click="showCharTable = !showCharTable">
        <div class="section-heading">
          <h2>開放文字一覧</h2>
          <p>全員のカードで開いた文字（緑色）</p>
        </div>
        <button type="button" class="toggle-btn" :aria-expanded="showCharTable">
          {{ showCharTable ? '▲ 閉じる' : '▼ 開く' }}
        </button>
      </div>

      <div v-show="showCharTable" class="char-table-wrap mt-3">
        <div class="char-table-grid">
          <div
            v-for="(col, colIdx) in charColumns"
            :key="colIdx"
            class="kana-col"
          >
            <div class="kana-col-header">
              {{ col.header }}
            </div>
            <div
              v-for="(char, rowIdx) in col.chars"
              :key="rowIdx"
              class="kana-cell"
              :class="{
                'is-open': char ? isOpenedChar(char) : false,
                'is-closed': char ? !isOpenedChar(char) : false,
                'is-blank': !char,
                'is-small': char ? isSmallKana(char) : false,
              }"
            >
              {{ char ?? '' }}
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 単語履歴一覧 -->
    <section class="panel result-section">
      <div class="section-header-toggle" @click="showHistory = !showHistory">
        <div class="section-heading">
          <h2>使用単語履歴 (全{{ history.length }}単語)</h2>
          <p>入力順</p>
        </div>
        <button type="button" class="toggle-btn" :aria-expanded="showHistory">
          {{ showHistory ? '▲ 閉じる' : '▼ 開く' }}
        </button>
      </div>

      <div v-show="showHistory" class="history-table-wrap mt-3">
        <div v-if="history.length === 0" class="empty-text">
          単語履歴はありません。
        </div>
        <table v-else class="history-table">
          <thead>
            <tr>
              <th>#</th>
              <th>単語</th>
              <th>入力者</th>
              <th>ターン</th>
              <th>開いた文字</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(entry, idx) in history"
              :key="historyKey(entry, idx)"
            >
              <td>{{ entry.sequence }}</td>
              <td><strong class="history-word-cell">{{ entry.word }}</strong></td>
              <td>{{ snapshot?.players.find((p) => p.playerId === entry.playerId)?.name ?? '' }}</td>
              <td>{{ entry.round }}</td>
              <td>
                <span v-if="entry.openedChars.length === 0" class="text-muted">なし</span>
                <span v-else class="opened-chars-tag">
                  {{ entry.openedChars.join('、') }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- アクションボタン -->
    <div class="result-actions">
      <button
        v-if="store.isHost"
        type="button"
        class="primary-button btn-lg"
        @click="onReturnToLobby"
      >
        ロビーに戻る（親のみ）
      </button>
      <button
        type="button"
        class="secondary-button btn-lg"
        @click="onGoToTop"
      >
        トップに戻る
      </button>
    </div>
  </div>
</template>

<style scoped>
.result-screen {
  max-width: 1100px;
  margin: 0 auto;
  padding: 1.5rem 1rem 3rem;
}

.screen-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.screen-header h1 {
  font-size: 1.6rem;
  font-weight: 800;
  margin: 0 0 0.25rem;
}

.screen-header p {
  color: var(--color-text-secondary, #64748b);
  margin: 0;
  font-size: 0.9rem;
}

.header-mark {
  background: #f1f5f9;
  color: #475569;
  font-weight: 700;
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.85rem;
}

.summary-panel {
  text-align: center;
  padding: 2rem 1.5rem;
  margin-bottom: 1.5rem;
}

.summary-badge {
  display: inline-block;
  background: var(--color-primary-subtle, #e0f2fe);
  color: var(--color-primary, #0284c7);
  font-weight: 800;
  font-size: 0.85rem;
  letter-spacing: 0.1em;
  padding: 0.3rem 0.9rem;
  border-radius: 9999px;
  margin-bottom: 0.75rem;
}

.summary-reason {
  font-size: 1.4rem;
  font-weight: 800;
  margin: 0 0 0.5rem;
}

.summary-sub {
  color: var(--color-text-secondary, #64748b);
  font-size: 0.95rem;
  margin: 0;
}

.result-section {
  margin-bottom: 1.5rem;
  padding: 1.25rem;
}

.section-heading h2 {
  font-size: 1.15rem;
  font-weight: 700;
  margin: 0 0 0.2rem;
}

.section-heading p {
  color: var(--color-text-secondary, #64748b);
  font-size: 0.825rem;
  margin: 0;
}

.section-header-toggle {
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  user-select: none;
}

.toggle-btn {
  background: none;
  border: none;
  color: var(--color-primary, #0284c7);
  font-weight: 600;
  font-size: 0.85rem;
  cursor: pointer;
}

.ranking-table-wrap,
.history-table-wrap {
  overflow-x: auto;
  margin-top: 1rem;
}

.ranking-table,
.history-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.ranking-table th,
.ranking-table td,
.history-table th,
.history-table td {
  padding: 0.65rem 0.85rem;
  text-align: left;
  border-bottom: 1px solid var(--color-border, #e2e8f0);
}

.ranking-table th,
.history-table th {
  font-weight: 700;
  background: var(--color-bg-subtle, #f8fafc);
  color: var(--color-text-secondary, #475569);
}

.disqualified-row td {
  opacity: 0.6;
  text-decoration: line-through;
}

.status-chip {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 700;
}

.status-chip.is-active {
  background: #dcfce7;
  color: #15803d;
}

.status-chip.is-disqualified {
  background: #fee2e2;
  color: #b91c1c;
}

.cpu-badge {
  background: #e0e7ff;
  color: #3730a3;
  font-size: 0.75rem;
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 1rem;
}

.char-table-wrap {
  overflow-x: auto;
  padding: 0.5rem 0;
}

.char-table-grid {
  display: flex;
  gap: 0.35rem;
}

.kana-col {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  align-items: center;
}

.kana-col-header {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--color-text-secondary, #64748b);
  margin-bottom: 0.15rem;
}

.kana-cell {
  width: 2rem;
  height: 2rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  background: var(--color-bg-subtle, #f1f5f9);
  color: var(--color-text-secondary, #64748b);
  font-size: 0.85rem;
  font-weight: 600;
}

.kana-cell.is-open {
  background: #22c55e;
  color: white;
  font-weight: 800;
}

.kana-cell.is-closed {
  background: var(--color-bg-subtle, #f1f5f9);
  color: var(--color-text-secondary, #64748b);
}

.kana-cell.is-blank {
  background: transparent;
  visibility: hidden;
}

.kana-cell.is-small {
  font-size: 0.7rem;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.header-btn {
  padding: 8px 16px;
  font-size: 0.9rem;
  font-weight: 600;
  white-space: nowrap;
}

.result-actions {
  display: flex;
  justify-content: center;
  gap: 1rem;
  flex-wrap: wrap;
  margin-top: 2rem;
}
</style>
