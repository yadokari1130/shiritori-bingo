import { describe, expect, it } from 'vitest'
import type { BingoCard, Cell } from '../types'
import {
  buildCharOpenStateColumns,
  calculateReachCells,
  collectOpenedChars,
  countBingoLines,
  countOpenedCells,
  generateBingoLines,
  getCompletedLineIds,
} from './bingo'

function makeCard(size: number, openIndexes: Set<number>, freeChar = 'あ'): BingoCard {
  const cells: Cell[] = []
  const freeIndex = Math.floor(size / 2) * size + Math.floor(size / 2)
  const chars = 'あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん'.split('')
  for (let r = 0; r < size; r++) {
    for (let c = 0; c < size; c++) {
      const index = r * size + c
      const isFree = index === freeIndex
      cells.push({
        index,
        row: r,
        column: c,
        char: isFree ? freeChar : chars[index % chars.length],
        isFree,
        isOpen: isFree || openIndexes.has(index),
      })
    }
  }
  return { size, cells, freeChar }
}

describe('bingo ユーティリティ', () => {
  describe('generateBingoLines', () => {
    it('5x5 では 12 列', () => {
      expect(generateBingoLines(5).length).toBe(12)
    })

    it('3x3 では 8 列', () => {
      expect(generateBingoLines(3).length).toBe(8)
    })
  })

  describe('getCompletedLineIds', () => {
    it('フリーマスを含む横列が成立', () => {
      const size = 3
      const freeIndex = 4
      // 中央行をすべて開く
      const open = new Set([freeIndex, 3, 5])
      const card = makeCard(size, open)
      const ids = getCompletedLineIds(card)
      expect(ids).toContain('row-1')
    })
  })

  describe('calculateReachCells', () => {
    it('ビンゴまで1マスの未開放マスがリーチ', () => {
      const size = 3
      const freeIndex = 4
      // 中央行の両端だけ開く（中央はフリー）
      const open = new Set([freeIndex, 3])
      const card = makeCard(size, open)
      const { reachIndexes } = calculateReachCells(card)
      expect(reachIndexes.has(5)).toBe(true)
    })

    it('複数列を同時完成できるマスは強調', () => {
      const size = 5
      const freeIndex = 12
      // 1行目と1列目の残りを開けて、左上隅 (0) が2列を同時完成できるようにする
      const open = new Set([freeIndex, 1, 2, 3, 4, 5, 10, 15, 20])
      const card = makeCard(size, open)
      const { reachIndexes, reachHighlightIndexes } = calculateReachCells(card)
      expect(reachHighlightIndexes.has(0)).toBe(true)
      expect(reachIndexes.has(0)).toBe(true)
    })
  })

  describe('buildCharOpenStateColumns', () => {
    it('清音列は必ず含まれる', () => {
      const columns = buildCharOpenStateColumns({
        yoon: false,
        sokuon: false,
        prolonged: false,
        smallA: false,
        dakuten: false,
        handakuten: false,
      })
      expect(columns.length).toBeGreaterThanOrEqual(10)
      expect(columns[0].header).toBe('あ')
    })

    it('濁音・半濁音を追加できる', () => {
      const columns = buildCharOpenStateColumns({
        yoon: false,
        sokuon: false,
        prolonged: false,
        smallA: false,
        dakuten: true,
        handakuten: true,
      })
      expect(columns.some((c) => c.header === 'が')).toBe(true)
      expect(columns.some((c) => c.header === 'ぱ')).toBe(true)
    })
  })

  describe('collectOpenedChars', () => {
    it('開いた文字を収集する', () => {
      const card = makeCard(3, new Set([0, 1, 2]))
      const opened = collectOpenedChars([card])
      expect(opened.size).toBeGreaterThanOrEqual(3)
    })
  })

  describe('countOpenedCells / countBingoLines', () => {
    it('開いたマス数を数える', () => {
      const card = makeCard(3, new Set([0, 1]))
      expect(countOpenedCells(card)).toBe(3) // フリー + 2
    })

    it('ビンゴ列数を数える', () => {
      const size = 3
      const freeIndex = 4
      const open = new Set([freeIndex, 3, 5])
      const card = makeCard(size, open)
      expect(countBingoLines(card)).toBe(1)
    })
  })
})
