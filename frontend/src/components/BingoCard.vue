<script setup lang="ts">
import { computed } from 'vue'
import type { BingoCard as BingoCardType } from '../types'
import { buildCellFlags } from '../utils/bingo'
import { isSmallKana } from '../utils/shiritori'

const props = withDefaults(
  defineProps<{
    card: BingoCardType
    title?: string
    subtitle?: string
    disqualified?: boolean
    previewChars?: string[]
    size?: 'small' | 'medium' | 'large'
    isCurrent?: boolean
  }>(),
  {
    title: '',
    subtitle: '',
    disqualified: false,
    previewChars: () => [],
    size: 'medium',
    isCurrent: false,
  },
)

const cellFlags = computed(() => buildCellFlags(props.card, props.previewChars))

// ビンゴ成立ライン数（ユニークな成立ラインIDの数）
const bingoLineCount = computed(() => {
  const lineSet = new Set<string>()
  for (const flag of cellFlags.value) {
    for (const lineId of flag.lineIds) {
      lineSet.add(lineId)
    }
  }
  return lineSet.size
})

// 開いたマス数（FREE含む）
const openedCellCount = computed(() => {
  return props.card.cells.filter((c) => c.isOpen || c.isFree).length
})

const gridStyle = computed(() => {
  return {
    gridTemplateColumns: `repeat(${props.card.size}, minmax(0, 1fr))`,
  }
})

// マス目のサイズに応じた動的フォントサイズ
const cellFontSize = computed(() => {
  const s = props.card.size
  if (s <= 3) return 'clamp(1.2rem, 3.2vw, 2rem)'
  if (s <= 5) return 'clamp(0.85rem, 2.1vw, 1.35rem)'
  return 'clamp(0.7rem, 1.5vw, 1rem)'
})

function cellLabel(flags: ReturnType<typeof buildCellFlags>[number], char: string): string {
  if (flags.isFree) return 'フリー'
  if (flags.lineIds.length > 0) return `${char} ビンゴ成立`
  if (flags.isOpen) return `${char} 開放済み`
  if (flags.isPreview) return `${char} プレビュー`
  if (flags.isReachHighlight) return `${char} リーチ強調`
  if (flags.isReach) return `${char} リーチ`
  return `${char} 未開放`
}
</script>

<template>
  <article
    class="player-card"
    :class="{
      'is-current': isCurrent,
      'is-disqualified': disqualified,
    }"
  >
    <div class="player-card-header">
      <div class="player-card-name">
        <span :class="{ 'text-strike': disqualified }">{{ title || 'カード' }}</span>
        <small v-if="subtitle">{{ subtitle }}</small>
        <small v-if="disqualified">失格</small>
      </div>

      <div class="header-badges">
        <span
          class="status-badge"
          :class="{ disqualified }"
        >
          {{ disqualified ? '失格' : '参加中' }}
        </span>
        <span class="bingo-badge">
          ビンゴ {{ bingoLineCount }}
        </span>
      </div>
    </div>

    <div class="card-stats">
      <span>開いたマス {{ openedCellCount }} / {{ card.cells.length }}</span>
    </div>

    <div
      class="bingo-card"
      :style="gridStyle"
      role="grid"
      :aria-label="`${title || ''}のビンゴカード`"
    >
      <div
        v-for="(cell, index) in card.cells"
        :key="index"
        class="bingo-cell"
        :class="{
          'is-open': cellFlags[index].isOpen,
          'is-free': cellFlags[index].isFree,
          'is-preview': cellFlags[index].isPreview,
          'is-reach': cellFlags[index].isReach && !cellFlags[index].isOpen,
          'is-reach-highlight': cellFlags[index].isReachHighlight && !cellFlags[index].isOpen,
          'is-bingo': cellFlags[index].lineIds.length > 0,
        }"
        :style="{ fontSize: cellFontSize }"
        :aria-label="cellLabel(cellFlags[index], cell.char)"
        role="gridcell"
      >
        <span
          class="cell-character"
          :class="{ 'is-small-char': isSmallKana(cell.char) }"
        >{{ cell.char }}</span>
        <small v-if="cell.isFree" class="free-label">FREE</small>
        <span
          v-else-if="cellFlags[index].isReachHighlight && !cellFlags[index].isOpen"
          class="reach-mark"
          aria-hidden="true"
        >◎</span>
        <span
          v-else-if="cellFlags[index].isReach && !cellFlags[index].isOpen"
          class="reach-mark"
          aria-hidden="true"
        >◯</span>
      </div>
    </div>
  </article>
</template>

<style scoped>
.player-card {
  min-width: 0;
  padding: 14px;
  border: 1px solid var(--line);
  border-radius: 16px;
  background: #fffefa;
  box-shadow: 0 4px 14px rgba(23, 35, 45, 0.05);
  transition: border-color 120ms ease, box-shadow 120ms ease;
  display: flex;
  flex-direction: column;
}

.player-card.is-current {
  border: 2px solid var(--coral);
  box-shadow: 0 0 0 4px rgba(223, 104, 79, 0.18);
}

.player-card.is-disqualified {
  background: #f3efe9;
  border-color: #d1c8bc;
  opacity: 0.85;
}

.player-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.player-card-name {
  min-width: 0;
  overflow-wrap: anywhere;
  color: var(--navy);
  font-weight: 900;
  font-size: 1.05rem;
  line-height: 1.25;
}

.player-card-name small {
  display: block;
  color: var(--coral-dark);
  font-size: 0.75rem;
  letter-spacing: 0.04em;
  font-weight: 700;
  margin-top: 2px;
}

.header-badges {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.card-stats {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin: 0 0 10px;
  color: var(--muted);
  font-size: 0.82rem;
  font-weight: 600;
}

.card-dimension {
  color: var(--muted);
  font-size: 0.76rem;
}

.text-strike {
  text-decoration: line-through;
  color: #757575;
}

.bingo-card {
  display: grid;
  gap: 4px;
  width: 100%;
  aspect-ratio: 1 / 1;
  padding: 5px;
  border: 2px solid var(--navy);
  border-radius: 10px;
  background: var(--navy);
  box-sizing: border-box;
}

.bingo-cell {
  position: relative;
  display: grid;
  place-items: center;
  min-width: 0;
  min-height: 0;
  aspect-ratio: 1 / 1;
  overflow: hidden;
  border: 1px solid #cfc5b7;
  border-radius: 5px;
  background: #f8f3e9;
  color: #8b8176;
  font-weight: 700;
  line-height: 1;
  user-select: none;
  transition: background 120ms ease, color 120ms ease, border-color 120ms ease;
}

.bingo-cell.is-open {
  border-color: var(--teal);
  background: var(--teal-pale);
  color: #075d5a;
  font-weight: 900;
}

.bingo-cell.is-free {
  border-color: var(--gold);
  background: var(--gold-pale);
  color: #71500d;
  font-weight: 900;
}

.bingo-cell.is-preview {
  border: 2px dashed var(--coral);
  background: #ffe3dc;
  color: var(--coral-dark);
  font-weight: 900;
}

.bingo-cell.is-reach {
  border: 2px dashed var(--gold);
  background: #fff8e1;
  color: #71500d;
}

.bingo-cell.is-reach-highlight {
  border: 2px dashed var(--coral);
  background: #ffede8;
  color: var(--coral-dark);
}

.bingo-cell.is-bingo {
  box-shadow: inset 0 0 0 2px var(--gold);
  background-image: repeating-linear-gradient(135deg, rgba(237, 184, 77, 0.22) 0 4px, transparent 4px 8px);
}

.bingo-cell.is-bingo::after {
  position: absolute;
  right: 3px;
  bottom: 2px;
  color: #9a6b11;
  content: "★";
  font-size: 0.65rem;
  line-height: 1;
}

.cell-character {
  position: relative;
  z-index: 1;
}

.cell-character.is-small-char {
  text-decoration: underline;
  text-decoration-thickness: 2px;
  text-underline-offset: 3px;
  text-decoration-skip-ink: none;
}

.free-label {
  position: absolute;
  right: 2px;
  bottom: 2px;
  color: #9a6b11;
  font-size: 0.48rem;
  font-weight: 900;
  letter-spacing: 0.02em;
}

.reach-mark {
  position: absolute;
  right: 2px;
  bottom: 2px;
  font-size: 0.55rem;
  font-weight: 900;
  line-height: 1;
  opacity: 0.85;
}
</style>

