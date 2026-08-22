/**
 * ビンゴ計算と文字開放状態表
 *
 * 仕様書 6. カード生成・ビンゴ判定、8. 結果画面仕様 に基づく。
 */

import type { BingoCard, Cell } from '../types'

/** ビンゴ列の識別子 */
export interface BingoLine {
  id: string
  indexes: number[]
}

/** マスの状態フラグ */
export interface CellFlags {
  isOpen: boolean
  isFree: boolean
  isPreview: boolean
  isReach: boolean
  isReachHighlight: boolean
  lineIds: string[]
}

/**
 * カードサイズからビンゴ列を生成する。
 * 横 N 列、縦 N 列、斜め 2 列の計 2N+2 列。仕様 6.5
 */
export function generateBingoLines(size: number): BingoLine[] {
  const lines: BingoLine[] = []

  // 横列
  for (let r = 0; r < size; r++) {
    const indexes: number[] = []
    for (let c = 0; c < size; c++) {
      indexes.push(r * size + c)
    }
    lines.push({ id: `row-${r}`, indexes })
  }

  // 縦列
  for (let c = 0; c < size; c++) {
    const indexes: number[] = []
    for (let r = 0; r < size; r++) {
      indexes.push(r * size + c)
    }
    lines.push({ id: `col-${c}`, indexes })
  }

  // 斜め（左上から右下）
  const diag1: number[] = []
  for (let i = 0; i < size; i++) {
    diag1.push(i * size + i)
  }
  lines.push({ id: 'diag-1', indexes: diag1 })

  // 斜め（右上から左下）
  const diag2: number[] = []
  for (let i = 0; i < size; i++) {
    diag2.push(i * size + (size - 1 - i))
  }
  lines.push({ id: 'diag-2', indexes: diag2 })

  return lines
}

/** 指定したインデックス集合がすべて開いているか */
function isLineComplete(cells: Cell[], indexes: number[]): boolean {
  return indexes.every(idx => cells[idx]?.isOpen === true)
}

/** 現在成立しているビンゴ列の ID 一覧を返す */
export function getCompletedLineIds(card: BingoCard): string[] {
  const lines = generateBingoLines(card.size)
  return lines
    .filter(line => isLineComplete(card.cells, line.indexes))
    .map(line => line.id)
}

/**
 * リーチマスとリーチ強調マスを計算する。
 * 仕様 4.8.1, 6.7
 */
export function calculateReachCells(card: BingoCard): {
  reachIndexes: Set<number>
  reachHighlightIndexes: Set<number>
} {
  const lines = generateBingoLines(card.size)
  const reachIndexes = new Set<number>()
  const reachHighlightIndexes = new Set<number>()

  for (const line of lines) {
    if (isLineComplete(card.cells, line.indexes))
      continue

    const closedIndexes: number[] = []
    for (const idx of line.indexes) {
      if (!card.cells[idx]?.isOpen) {
        closedIndexes.push(idx)
      }
    }

    if (closedIndexes.length === 1) {
      const idx = closedIndexes[0]
      if (reachIndexes.has(idx)) {
        reachHighlightIndexes.add(idx)
      }
      else {
        reachIndexes.add(idx)
      }
    }
  }

  return { reachIndexes, reachHighlightIndexes }
}

/**
 * カードの各マスに対して状態フラグを付与する。
 */
export function buildCellFlags(
  card: BingoCard,
  previewChars: string[],
): CellFlags[] {
  const { reachIndexes, reachHighlightIndexes } = calculateReachCells(card)
  const completedLineIds = getCompletedLineIds(card)

  return card.cells.map((cell, index) => {
    const isPreview = !cell.isOpen && previewChars.includes(cell.char)
    const lineIds = generateBingoLines(card.size)
      .filter(line => line.indexes.includes(index) && completedLineIds.includes(line.id))
      .map(line => line.id)

    return {
      isOpen: cell.isOpen,
      isFree: cell.isFree,
      isPreview,
      isReach: reachIndexes.has(index),
      isReachHighlight: reachHighlightIndexes.has(index),
      lineIds,
    }
  })
}

/** 文字開放状態表で使用する列定義。仕様 8.4 */
export interface CharOpenStateColumn {
  header: string
  chars: (string | null)[]
}

/**
 * 文字開放状態表の列を生成する。
 * 右から順に：あ行〜わ行の清音、が行〜ば行の濁音、ぱ行の半濁音、小さいあ行、特殊文字（ゃゅょっー）。
 * 仕様 8.4
 */
export function buildCharOpenStateColumns(options: {
  yoon: boolean
  sokuon: boolean
  prolonged: boolean
  smallA: boolean
  dakuten: boolean
  handakuten: boolean
}): CharOpenStateColumn[] {
  const columns: CharOpenStateColumn[] = []

  // 清音：あ〜わ（5 段縦書き）
  const seionGroups = [
    ['あ', 'い', 'う', 'え', 'お'],
    ['か', 'き', 'く', 'け', 'こ'],
    ['さ', 'し', 'す', 'せ', 'そ'],
    ['た', 'ち', 'つ', 'て', 'と'],
    ['な', 'に', 'ぬ', 'ね', 'の'],
    ['は', 'ひ', 'ふ', 'へ', 'ほ'],
    ['ま', 'み', 'む', 'め', 'も'],
    ['や', null, 'ゆ', null, 'よ'],
    ['ら', 'り', 'る', 'れ', 'ろ'],
    ['わ', null, null, null, null],
  ]
  for (const group of seionGroups) {
    columns.push({ header: group[0] ?? '', chars: group })
  }

  // 濁音
  if (options.dakuten) {
    const dakutenGroups = [
      ['が', 'ぎ', 'ぐ', 'げ', 'ご'],
      ['ざ', 'じ', 'ず', 'ぜ', 'ぞ'],
      ['だ', 'ぢ', 'づ', 'で', 'ど'],
      ['ば', 'び', 'ぶ', 'べ', 'ぼ'],
    ]
    for (const group of dakutenGroups) {
      columns.push({ header: group[0] ?? '', chars: group })
    }
  }

  // 半濁音
  if (options.handakuten) {
    columns.push({ header: 'ぱ', chars: ['ぱ', 'ぴ', 'ぷ', 'ぺ', 'ぽ'] })
  }

  // 小さいあ行
  if (options.smallA) {
    columns.push({ header: 'ぁ', chars: ['ぁ', 'ぃ', 'ぅ', 'ぇ', 'ぉ'] })
  }

  // 特殊文字（拗音・促音・伸ばし棒）
  if (options.yoon || options.sokuon || options.prolonged) {
    const special: (string | null)[] = [null, null, null, null, null]
    if (options.yoon) {
      special[0] = 'ゃ'
      special[1] = 'ゅ'
      special[2] = 'ょ'
    }
    if (options.sokuon) {
      special[3] = 'っ'
    }
    if (options.prolonged) {
      special[4] = 'ー'
    }
    columns.push({ header: special[0] ?? special[3] ?? special[4] ?? '特殊', chars: special })
  }

  return columns
}

/** 開放済み文字の集合を取得する（全カードを走査）。仕様 8.4 */
export function collectOpenedChars(cards: BingoCard[]): Set<string> {
  const opened = new Set<string>()
  for (const card of cards) {
    for (const cell of card.cells) {
      if (cell.isOpen) {
        opened.add(cell.char)
      }
    }
  }
  return opened
}

/** 指定したカードの開いたマス数を数える */
export function countOpenedCells(card: BingoCard): number {
  return card.cells.filter(cell => cell.isOpen).length
}

/** 指定したカードのビンゴ数を数える */
export function countBingoLines(card: BingoCard): number {
  return getCompletedLineIds(card).length
}
