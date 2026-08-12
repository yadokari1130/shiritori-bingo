<script setup lang="ts">
import { computed, ref } from 'vue'
import { useGameStore } from '../store/game'
import BingoCard from './BingoCard.vue'
import DisconnectedMark from './DisconnectedMark.vue'
import { buildCharOpenStateColumns, collectOpenedChars } from '../utils/bingo'
import { isSmallKana } from '../utils/shiritori'

const store = useGameStore()

const showCards = ref(true)
const showCharTable = ref(true)
const showHistory = ref(true)

const result = computed(() => store.gameState?.result)

const reasonText = computed(() => {
  const r = result.value
  if (!r) return ''
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
  if (!snapshot.value) return []
  if (snapshot.value.settings.mode === 'individual') {
    return snapshot.value.players.map((p) => ({
      id: p.playerId,
       title: p.name,
       subtitle: p.teamId ? 'チーム所属' : undefined,
       members: [],
       disconnected: p.connectionStatus === 'disconnected',
      card: p.card,
      disqualified: p.status === 'disqualified',
    }))
  }
  return snapshot.value.teams.map((t, idx) => ({
     id: t.teamId,
     title: `チーム ${idx + 1}`,
     subtitle: undefined,
     disconnected: false,
     members: t.memberPlayerIds
       .map((id) => snapshot.value!.players.find((p) => p.playerId === id))
       .filter((player): player is NonNullable<typeof player> => Boolean(player))
       .map((player) => ({ name: player.name, disconnected: player.connectionStatus === 'disconnected' })),
    card: t.card,
    disqualified: t.status === 'disqualified',
  }))
})

const charColumns = computed(() => {
  const s = settings.value
  if (!s) return []
  return buildCharOpenStateColumns(s.cardOptions)
})

const openedChars = computed(() => {
  if (!snapshot.value) return new Set<string>()
  const cards = snapshot.value.settings.mode === 'individual'
    ? snapshot.value.players.map((p) => p.card).filter((card): card is NonNullable<typeof card> => card !== null)
    : snapshot.value.teams.map((t) => t.card)
  return collectOpenedChars(cards)
})

const history = computed(() => snapshot.value?.wordHistory ?? [])

function isOpenedChar(char: string | null): boolean {
  if (!char) return false
  return openedChars.value.has(char)
}

function historyKey(entry: { word: string; playerId: string; round: number; sequence: number }, index: number): string {
  return `${entry.round}-${entry.sequence}-${index}`
}

async function onReturnToLobby(): Promise<void> {
  await store.returnToLobby()
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
      <div class="header-mark">結果</div>
    </header>

    <!-- エラー通知 -->
    <p v-if="store.errorMessage" class="notice error mb-3">
      {{ store.errorMessage }}
    </p>

    <!-- 終了理由バナー -->
    <div class="result-reason">
      <p>
        <strong>{{ reasonText }}</strong>
        <span>（終了ターン: {{ result?.endRound ?? '-' }}ターン目）</span>
      </p>
    </div>

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
                    snapshot?.players.find((p) => p.playerId === ranking.subjectId)?.name ??
                    (snapshot?.teams.find((t) => t.teamId === ranking.subjectId)
                      ? `チーム ${(snapshot?.teams.findIndex((t) => t.teamId === ranking.subjectId) ?? 0) + 1}`
                      : '')
                   }}
                   <DisconnectedMark
                     v-if="ranking.subjectType === 'player' && snapshot?.players.find((p) => p.playerId === ranking.subjectId)?.connectionStatus === 'disconnected'"
                   />
                </strong>
              </td>
              <td>{{ ranking.bingoCount }}本</td>
              <td>{{ ranking.openedCellCount }}マス</td>
              <td>
                <span
                  class="status-badge"
                  :class="{ disqualified: ranking.status === 'disqualified' }"
                >
                  {{ ranking.status === 'disqualified' ? '失格' : '完走' }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- 全員の最終ビンゴカード一覧 -->
    <section class="panel result-section">
      <div class="section-heading">
        <h2>全員のビンゴカード</h2>
        <button
          type="button"
          class="secondary-button btn-sm"
          :aria-label="showCards ? '折りたたむ' : '展開する'"
          @click="showCards = !showCards"
        >
          {{ showCards ? '非表示にする' : '表示する' }}
        </button>
      </div>

      <div v-show="showCards" class="card-grid mt-3">
        <BingoCard
          v-for="item in orderedResults"
          :key="item.id"
          :card="item.card!"
          :title="item.title"
           :subtitle="item.subtitle"
           :disconnected="item.disconnected"
           :members="item.members"
          :disqualified="item.disqualified"
        />
      </div>
    </section>

    <!-- 文字開放状態表（五十音表） -->
    <section class="panel result-section">
      <div class="section-heading">
        <h2>文字開放状態表</h2>
        <button
          type="button"
          class="secondary-button btn-sm"
          :aria-label="showCharTable ? '折りたたむ' : '展開する'"
          @click="showCharTable = !showCharTable"
        >
          {{ showCharTable ? '非表示にする' : '表示する' }}
        </button>
      </div>

      <div v-show="showCharTable" class="kana-chart-wrapper mt-3">
        <div class="kana-legend">
          <span class="kana-legend-item">
            <span class="kana-legend-mark is-open" /> 開放済み
          </span>
          <span class="kana-legend-item">
            <span class="kana-legend-mark is-closed" /> 未開放
          </span>
          <span class="kana-legend-item">
            <span class="kana-legend-mark is-free" /> FREEマス
          </span>
        </div>

        <div class="kana-chart-layout">
          <div class="kana-columns-box">
            <div
              v-for="column in charColumns"
              :key="column.header"
              class="kana-col"
            >
              <div class="kana-col-header">{{ column.header }}</div>
              <div
                v-for="(char, rowIdx) in column.chars"
                :key="`${column.header}-${rowIdx}`"
                class="kana-cell"
                :class="{
                  'is-open': char ? isOpenedChar(char) : false,
                  'is-closed': char ? !isOpenedChar(char) : false,
                  'is-blank': !char,
                }"
              >
                <span
                  class="kana-character"
                  :class="{ 'is-small-char': char ? isSmallKana(char) : false }"
                >{{ char ?? '' }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 単語履歴 -->
    <section class="panel result-section">
      <div class="section-heading">
        <h2>入力された有効単語 ({{ history.length }}語)</h2>
        <button
          type="button"
          class="secondary-button btn-sm"
          :aria-label="showHistory ? '折りたたむ' : '展開する'"
          @click="showHistory = !showHistory"
        >
          {{ showHistory ? '非表示にする' : '表示する' }}
        </button>
      </div>

      <div v-show="showHistory" class="history-grid mt-3">
        <div
          v-for="(entry, idx) in history"
          :key="historyKey(entry, idx)"
          class="history-card"
        >
          <span class="history-word">{{ entry.word }}</span>
          <span class="history-meta">
            {{ snapshot?.players.find((p) => p.playerId === entry.playerId)?.name ?? '' }}
            （{{ entry.round }}ターン目・{{ entry.sequence }}手番）
          </span>
        </div>
      </div>
    </section>

    <!-- アクション（ロビーに戻る） -->
    <section class="result-actions-panel">
      <div v-if="store.isHost" class="text-center">
        <button
          type="button"
          class="primary-button return-lobby-btn"
          @click="onReturnToLobby"
        >
          ゲーム終了（ロビーへ戻る）
        </button>
      </div>
      <div v-else class="notice info text-center">
        親（ホスト）がロビーへ戻るのを待機しています…
      </div>
    </section>
  </div>
</template>

<style scoped>
.result-screen {
  display: grid;
  gap: 20px;
}

.kana-chart-wrapper {
  overflow-x: auto;
  padding-bottom: 8px;
}

.kana-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 7px 14px;
  margin: 0 0 12px;
  color: var(--muted);
  font-size: 0.8rem;
}

.kana-legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.kana-legend-mark {
  width: 18px;
  height: 18px;
  border: 1px solid #cfc5b7;
  border-radius: 4px;
  background: #f8f3e9;
}

.kana-legend-mark.is-open {
  border-color: var(--teal);
  background: var(--teal-pale);
}

.kana-legend-mark.is-closed {
  background: #fffefa;
}

.kana-legend-mark.is-free {
  border-color: var(--gold);
  background: var(--gold-pale);
}

.kana-columns-box {
  display: flex;
  flex-direction: row-reverse;
  justify-content: center;
  gap: 6px;
  min-width: max-content;
  margin: 0 auto;
}

.kana-col {
  display: flex;
  flex-direction: column;
  gap: 5px;
  align-items: center;
}

.kana-col-header {
  height: 20px;
  line-height: 20px;
  font-size: 0.76rem;
  font-weight: 800;
  color: var(--muted);
  text-align: center;
  display: flex;
  align-items: center;
  justify-content: center;
}

.kana-cell {
  width: 36px;
  height: 38px;
  min-width: 36px;
  max-width: 36px;
  min-height: 38px;
  max-height: 38px;
  box-sizing: border-box;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #cfc5b7;
  border-radius: 6px;
  background: #fffefa;
  font-size: 1.05rem;
  font-weight: 800;
  color: var(--ink);
  line-height: 1;
  flex-shrink: 0;
  transition: all 0.15s ease;
}

.kana-character {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  text-align: center;
}

.kana-character.is-small-char {
  text-decoration: underline;
  text-decoration-thickness: 2px;
  text-underline-offset: 3px;
  text-decoration-skip-ink: none;
}

.kana-cell.is-open {
  border-color: var(--teal);
  background: var(--teal-pale);
  color: #075d5a;
}

.kana-cell.is-closed {
  background: #fffefa;
  color: #6f655a;
}

.kana-cell.is-blank {
  border: 1px solid transparent;
  background: transparent;
  pointer-events: none;
  visibility: hidden;
}

.history-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 10px;
}

.history-card {
  padding: 10px 14px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: #fffefa;
  display: grid;
  gap: 2px;
}

.history-card .history-word {
  font-size: 1.1rem;
  font-weight: 800;
  color: var(--navy);
}

.history-card .history-meta {
  font-size: 0.78rem;
  color: var(--muted);
}

.result-actions-panel {
  padding: 16px 0;
}

.return-lobby-btn {
  font-size: 1.15rem;
  padding: 14px 36px;
}

.btn-sm {
  min-height: 32px;
  padding: 4px 10px;
  font-size: 0.82rem;
}

.text-danger {
  color: var(--danger);
}

.text-center {
  text-align: center;
}

.mt-3 { margin-top: 12px; }
.mb-3 { margin-bottom: 12px; }
.mb-4 { margin-bottom: 16px; }
</style>

