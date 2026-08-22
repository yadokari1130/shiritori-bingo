<script setup lang="ts">
import type { Settings } from '../types'
import { computed, onMounted, onUnmounted } from 'vue'

const props = withDefaults(
  defineProps<{
    modelValue: boolean
    settings: Settings
    disableTeleport?: boolean
  }>(),
  {
    disableTeleport: false,
  },
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
}>()

function close(): void {
  emit('update:modelValue', false)
}

function onKeydown(e: KeyboardEvent): void {
  if (e.key === 'Escape' && props.modelValue) {
    close()
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
})

// カードに含まれる追加文字種
const cardOptionLabels = computed(() => {
  const opts = props.settings.cardOptions
  const list: string[] = []
  if (opts.dakuten)
    list.push('濁音（が・ざ・だ・ば等）')
  if (opts.handakuten)
    list.push('半濁音（ぱ・ぴ・ぷ・ぺ・ぽ）')
  if (opts.yoon)
    list.push('拗音（ゃ・ゅ・ょ）')
  if (opts.sokuon)
    list.push('促音（っ）')
  if (opts.smallA)
    list.push('小さいあ行（ぁ・ぃ・ぅ・ぇ・ぉ）')
  if (opts.prolonged)
    list.push('伸ばし棒（ー）')
  return list
})

// 文字数制限テキスト
const wordLengthLimitText = computed(() => {
  const min = props.settings.minWordLength
  const max = props.settings.maxWordLength
  if (min !== null && max !== null) {
    return `${min}文字以上 ${max}文字以下`
  }
  if (min !== null) {
    return `${min}文字以上`
  }
  if (max !== null) {
    return `${max}文字以下`
  }
  return '制限なし（ひらがな1文字以上）'
})
</script>

<template>
  <Teleport to="body" :disabled="disableTeleport">
    <div
      v-if="modelValue"
      class="rule-modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="rule-modal-title"
      @click.self="close"
    >
      <div class="rule-modal-container">
        <!-- モーダルヘッダー -->
        <header class="rule-modal-header">
          <div class="modal-title-group">
            <span class="modal-badge">📖 ルールガイド</span>
            <h2 id="rule-modal-title">
              ゲームルール説明
            </h2>
          </div>
          <button
            type="button"
            class="modal-close-icon"
            aria-label="閉じる"
            @click="close"
          >
            ✕
          </button>
        </header>

        <!-- モーダルコンテンツ（スクロール可能） -->
        <div class="rule-modal-body">
          <!-- 現在の設定サマリー -->
          <section class="rule-summary-banner">
            <h3 class="summary-banner-title">
              現在の適用ルール概要
            </h3>
            <div class="summary-chips">
              <span class="rule-chip">
                {{ settings.mode === 'team' ? `👥 チーム戦 (${settings.teamCount}チーム)` : '👤 個人戦' }}
              </span>
              <span class="rule-chip">
                🔲 {{ settings.cardSize }}×{{ settings.cardSize }} マス
              </span>
              <span class="rule-chip">
                🎯 {{ settings.endCondition === 'turns' ? `指定ターン数 (${settings.targetTurns}ターン)` : `指定ビンゴ数 (${settings.targetBingos}本達成)` }}
              </span>
              <span class="rule-chip">
                ⏱ 持ち時間 {{ settings.timeLimitSeconds }}秒 (+初回{{ settings.extraTimeSeconds }}秒)
              </span>
              <span class="rule-chip" :class="{ 'chip-alert': settings.invalidAction === 'disqualify' }">
                ⚠️ 無効時: {{ settings.invalidAction === 'disqualify' ? '失格' : 'ターンスキップ' }}
              </span>
              <span class="rule-chip" :class="{ 'chip-alert': !settings.inputWordCheck }">
                🔍 送信前チェック: {{ settings.inputWordCheck ? 'あり' : 'なし（即ペナルティ）' }}
              </span>
              <span v-if="settings.minWordLength !== null || settings.maxWordLength !== null" class="rule-chip chip-extra">
                📏 文字数: {{ wordLengthLimitText }}
              </span>
            </div>
          </section>

          <!-- ルール詳細カード一覧 -->
          <div class="rule-sections-grid">
            <!-- 1. 基本の遊び方としりとり -->
            <section class="rule-card">
              <div class="rule-card-header">
                <span class="card-num">1</span>
                <h3>しりとりとマス開放の基本</h3>
              </div>
              <ul class="rule-card-list">
                <li>
                  <strong>しりとりを繋ぐ:</strong> 順番にひらがなで単語を入力します。直前の単語の「最後の文字」から始まる単語を答えます。
                </li>
                <li>
                  <strong>最初の単語:</strong> ゲーム開始時の最初の単語は、カード中央の<strong>「フリーマスの文字」</strong>から始めます。
                </li>
                <li>
                  <strong>マスが開く:</strong> 入力した単語に含まれる文字が、自分および全員のカードにあれば<strong>その文字のマスが開きます</strong>（例: 「すいか」ならカードにある「す」「い」「か」が開く）。
                </li>
                <li>
                  <strong>単語の存在判定:</strong> 単語の実在確認は行われません。ひらがな・伸ばし棒でしりとりが成立していれば送信可能です。
                </li>
                <li>
                  <strong>濁点・半濁点の接続緩和:</strong> 前の単語の語尾と次の単語の頭文字は、同じ行グループ（例:「ず」の次に「す」や「ず」、「ば」の次に「は」「ば」「ぱ」）であれば接続できます（※開くマスは入力された完全一致文字のみ）。
                </li>
                <li>
                  <strong>語尾の処理:</strong> 「伸ばし棒（ー）」や「ゃ・ゅ・ょ」「っ」「ぁ〜ぉ」で終わる単語は、直音に変換した文字から続きます（例:「ぎたー」→「た」、「きしゃ」→「や」）。
                </li>
              </ul>
            </section>

            <!-- 2. 対戦モード -->
            <section class="rule-card">
              <div class="rule-card-header">
                <span class="card-num">2</span>
                <h3>対戦モード（{{ settings.mode === 'team' ? 'チーム戦' : '個人戦' }}）</h3>
              </div>
              <div v-if="settings.mode === 'team'" class="rule-mode-content">
                <p class="rule-highlight-box">
                  <strong>現在「チーム戦（全{{ settings.teamCount }}チーム）」が設定されています。</strong>
                </p>
                <ul class="rule-card-list">
                  <li>各チームに1枚のビンゴカードが配られます。</li>
                  <li>チームの手番が来たら、<strong>そのチームの所属者なら誰でも</strong>単語を入力して確定できます。</li>
                  <li>ビンゴ数、開いたマス数、失格状態、順位はすべて<strong>チーム単位</strong>で競います。</li>
                </ul>
              </div>
              <div v-else class="rule-mode-content">
                <p class="rule-highlight-box">
                  <strong>現在「個人戦」が設定されています。</strong>
                </p>
                <ul class="rule-card-list">
                  <li>プレイヤー各自に専用のビンゴカードが1枚ずつ配られます。</li>
                  <li>ゲーム開始時にランダムに決まった手番順に、1人ずつ回答します。</li>
                  <li>個人のビンゴ数・開いたマス数で順位を競います。</li>
                </ul>
              </div>
            </section>

            <!-- 3. カードと文字候補 -->
            <section class="rule-card">
              <div class="rule-card-header">
                <span class="card-num">3</span>
                <h3>ビンゴカードの仕様</h3>
              </div>
              <ul class="rule-card-list">
                <li>
                  <strong>カードサイズ:</strong> <strong>{{ settings.cardSize }} × {{ settings.cardSize }} マス</strong>（合計 {{ settings.cardSize * settings.cardSize }} マス、中央は最初から開いているフリーマス）。
                </li>
                <li>
                  <strong>カードに含まれる文字:</strong>
                  基本の清音（あ〜わ）に加えて、以下の文字カテゴリがカードマスに配置されます。
                  <div class="char-options-tags mt-1">
                    <span v-for="label in cardOptionLabels" :key="label" class="char-tag">
                      ✓ {{ label }}
                    </span>
                    <span v-if="cardOptionLabels.length === 0" class="char-tag-muted">
                      ※ 清音のみ
                    </span>
                  </div>
                </li>
                <li class="note-item">
                  ※ カードに含まれない文字種であっても、しりとり単語の入力自体には自由に使用できます。
                </li>
              </ul>
            </section>

            <!-- 4. 終了条件と順位決定 -->
            <section class="rule-card">
              <div class="rule-card-header">
                <span class="card-num">4</span>
                <h3>終了条件と順位</h3>
              </div>
              <ul class="rule-card-list">
                <li v-if="settings.endCondition === 'turns'">
                  <strong>ゲーム終了条件:</strong>
                  <strong>指定ターン数（{{ settings.targetTurns }}ターン）</strong>が終了した時点でゲーム終了となります。
                </li>
                <li v-else>
                  <strong>ゲーム終了条件:</strong>
                  いずれかの{{ settings.mode === 'team' ? 'チーム' : 'プレイヤー' }}が<strong>{{ settings.targetBingos }}本ビンゴ</strong>を達成したターンの終了時にゲーム終了となります。
                </li>
                <li>
                  <strong>順位の決定（1224方式）:</strong>
                  <ol class="sub-ordered-list">
                    <li>成立したビンゴ数が多い順</li>
                    <li>開いたマス数が多い順</li>
                    <li>上記が同じ場合は同順位</li>
                  </ol>
                </li>
                <li>
                  全員が失格となった場合はその時点で即時終了となります。失格者は順位計算の対象外（「失格」表示）となります。
                </li>
              </ul>
            </section>

            <!-- 5. 制限時間と時間切れ -->
            <section class="rule-card">
              <div class="rule-card-header">
                <span class="card-num">5</span>
                <h3>制限時間</h3>
              </div>
              <ul class="rule-card-list">
                <li>
                  <strong>持ち時間:</strong> 1手番あたり <strong>{{ settings.timeLimitSeconds }}秒</strong>
                </li>
                <li>
                  <strong>初回エクストラタイム:</strong> 1ターン目の最初の手番のみ <strong>+{{ settings.extraTimeSeconds }}秒</strong> が加算されます。
                </li>
                <li>
                  <strong>時間切れ時の挙動:</strong>
                  <span v-if="settings.forceSkipOnTimeout" class="text-alert-highlight">
                    <strong>「強制スキップあり」</strong>に設定されています。残り時間が0秒になると自動的に手番がスキップされます。
                  </span>
                  <span v-else>
                    <strong>「強制スキップなし」</strong>に設定されています。0秒になっても自動スキップはされず、入力を継続できます。
                  </span>
                </li>
              </ul>
            </section>

            <!-- 6. 無効入力とエクストラルール -->
            <section class="rule-card">
              <div class="rule-card-header">
                <span class="card-num">6</span>
                <h3>無効入力とペナルティ</h3>
              </div>
              <ul class="rule-card-list">
                <li>
                  <strong>無効となる単語:</strong>
                  「ん」で終わる単語、すでに使用された単語、前の文字と繋がっていない単語、文字数制限外の単語。
                </li>
                <li>
                  <strong>無効入力時のペナルティ:</strong>
                  <span v-if="settings.invalidAction === 'disqualify'" class="text-danger-highlight">
                    <strong>【失格】</strong> 無効な単語を入力すると即座に失格となり、以降の手番から除外されます。
                  </span>
                  <span v-else class="text-warning-highlight">
                    <strong>【ターンスキップ】</strong> マスは開かず、その手番のみスキップされて次の人の番になります。
                  </span>
                </li>
                <li>
                  <strong>送信前入力文字チェック:</strong>
                  <span v-if="settings.inputWordCheck">
                    <strong>【有効】</strong> ルール違反の単語（接続ミス、文字数違反など）は送信前にチェックされ、送信が阻止されます（手番は消費されません）。
                  </span>
                  <span v-else class="text-alert-highlight">
                    <strong>【無効（上級者向け）】</strong> 送信前の自動チェックが行われません。ルール違反の単語を送信すると直ちに上記のペナルティ（{{ settings.invalidAction === 'disqualify' ? '失格' : 'スキップ' }}）が適用されます。
                  </span>
                </li>
                <li v-if="settings.minWordLength !== null || settings.maxWordLength !== null">
                  <strong>文字数制限:</strong>
                  単語の長さは <strong>{{ wordLengthLimitText }}</strong> でなければなりません。
                </li>
              </ul>
            </section>
          </div>
        </div>

        <!-- モーダルフッター -->
        <footer class="rule-modal-footer">
          <button type="button" class="primary-button modal-btn" @click="close">
            閉じる
          </button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.rule-modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(16, 43, 57, 0.65);
  backdrop-filter: blur(6px);
  padding: 16px;
  animation: modal-fade-in 0.2s ease-out;
}

.rule-modal-container {
  position: relative;
  display: flex;
  flex-direction: column;
  width: min(860px, 100%);
  max-height: min(90vh, 880px);
  border-radius: 20px;
  border: 1px solid var(--line);
  background: var(--panel, #fffdf8);
  box-shadow: 0 24px 60px rgba(16, 43, 57, 0.25);
  overflow: hidden;
  animation: modal-slide-up 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

/* ヘッダー */
.rule-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 24px;
  background: #fff;
  border-bottom: 1px solid var(--line);
}

.modal-title-group {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.modal-badge {
  font-size: 0.8rem;
  font-weight: 800;
  padding: 3px 10px;
  border-radius: 999px;
  background: var(--teal-pale, #dff2ed);
  color: var(--teal, #1c8b86);
}

.rule-modal-header h2 {
  margin: 0;
  font-size: 1.35rem;
  font-weight: 900;
  color: var(--navy-deep, #102b39);
}

.modal-close-icon {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border: 1px solid var(--line);
  border-radius: 50%;
  background: #fffefa;
  color: var(--muted);
  font-size: 1.1rem;
  cursor: pointer;
  transition: all 0.15s ease;
}

.modal-close-icon:hover {
  background: var(--danger-pale, #ffe4df);
  color: var(--danger, #a7302c);
  border-color: var(--danger);
}

/* ボディ */
.rule-modal-body {
  padding: 20px 24px;
  overflow-y: auto;
  display: grid;
  gap: 20px;
}

/* サマリーバナー */
.rule-summary-banner {
  padding: 14px 18px;
  border-radius: 14px;
  background: #f4efe6;
  border: 1px solid var(--line);
}

.summary-banner-title {
  margin: 0 0 10px;
  font-size: 0.95rem;
  font-weight: 800;
  color: var(--navy);
}

.summary-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.rule-chip {
  display: inline-flex;
  align-items: center;
  padding: 5px 12px;
  border-radius: 999px;
  background: #ffffff;
  border: 1px solid var(--line);
  font-size: 0.82rem;
  font-weight: 700;
  color: var(--navy);
  box-shadow: 0 2px 4px rgba(23, 35, 45, 0.04);
}

.rule-chip.chip-alert {
  background: #fff3f0;
  border-color: var(--coral);
  color: var(--coral-dark);
}

.rule-chip.chip-extra {
  background: var(--gold-pale);
  border-color: var(--gold);
  color: #74510d;
}

/* グリッド */
.rule-sections-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

@media (max-width: 720px) {
  .rule-sections-grid {
    grid-template-columns: 1fr;
  }
}

.rule-card {
  padding: 16px;
  border-radius: 14px;
  border: 1px solid var(--line);
  background: #ffffff;
  box-shadow: 0 2px 8px rgba(23, 35, 45, 0.03);
}

.rule-card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 2px solid #f0ebe1;
}

.card-num {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border-radius: 8px;
  background: var(--coral);
  color: #ffffff;
  font-size: 0.85rem;
  font-weight: 900;
}

.rule-card-header h3 {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 800;
  color: var(--navy);
}

.rule-card-list {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 8px;
  font-size: 0.88rem;
  line-height: 1.5;
  color: var(--ink);
}

.rule-card-list li strong {
  color: var(--navy-deep);
}

.sub-ordered-list {
  margin: 4px 0 0;
  padding-left: 20px;
  font-size: 0.84rem;
  color: var(--muted);
}

.rule-highlight-box {
  margin: 0 0 10px;
  padding: 8px 12px;
  border-radius: 8px;
  background: var(--teal-pale, #dff2ed);
  border: 1px solid rgba(28, 139, 134, 0.25);
  font-size: 0.88rem;
  color: #075d5a;
}

.char-options-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.char-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 6px;
  background: #f0fdf4;
  border: 1px solid #86efac;
  color: #15803d;
  font-size: 0.76rem;
  font-weight: 700;
}

.char-tag-muted {
  color: var(--muted);
  font-size: 0.8rem;
}

.note-item {
  color: var(--muted);
  font-size: 0.82rem;
}

.text-alert-highlight {
  color: var(--coral-dark);
  font-weight: 700;
}

.text-danger-highlight {
  color: var(--danger);
  font-weight: 700;
}

.text-warning-highlight {
  color: #8c5b00;
  font-weight: 700;
}

.mt-1 {
  margin-top: 4px;
}

/* フッター */
.rule-modal-footer {
  display: flex;
  justify-content: flex-end;
  padding: 14px 24px;
  background: #fff;
  border-top: 1px solid var(--line);
}

.modal-btn {
  min-width: 120px;
  padding: 10px 24px;
  font-size: 0.95rem;
}

/* アニメーション */
@keyframes modal-fade-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes modal-slide-up {
  from {
    opacity: 0;
    transform: translateY(16px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}
</style>
