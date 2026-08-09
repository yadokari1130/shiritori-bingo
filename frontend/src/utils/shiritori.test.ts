import { describe, expect, it } from 'vitest'
import {
  buildCardCharPool,
  getFreeCharCandidates,
  isSameConnectionGroup,
  isValidInputChars,
  maxCardSize,
  normalizeTail,
  validateWordForFrontend,
} from './shiritori'

describe('shiritori ユーティリティ', () => {
  describe('buildCardCharPool', () => {
    it('基本の清音を常に含む', () => {
      const pool = buildCardCharPool({
        yoon: false,
        sokuon: false,
        prolonged: false,
        smallA: false,
        dakuten: false,
        handakuten: false,
      })
      expect(pool).toContain('あ')
      expect(pool).toContain('か')
      expect(pool).toContain('わ')
      expect(pool).not.toContain('ん')
      expect(pool).not.toContain('を')
    })

    it('濁音・半濁音を追加できる', () => {
      const pool = buildCardCharPool({
        yoon: false,
        sokuon: false,
        prolonged: false,
        smallA: false,
        dakuten: true,
        handakuten: true,
      })
      expect(pool).toContain('が')
      expect(pool).toContain('ぱ')
      expect(pool).not.toContain('ゔ')
    })
  })

  describe('maxCardSize', () => {
    it('清音のみの場合は 5 まで', () => {
      const pool = getFreeCharCandidates()
      expect(maxCardSize(pool)).toBe(5)
    })

    it('濁音・半濁音を含めると 7 まで', () => {
      const pool = buildCardCharPool({
        yoon: false,
        sokuon: false,
        prolonged: false,
        smallA: false,
        dakuten: true,
        handakuten: true,
      })
      expect(maxCardSize(pool)).toBe(7)
    })
  })

  describe('isSameConnectionGroup', () => {
    it('清音同士は完全一致が必要', () => {
      expect(isSameConnectionGroup('か', 'か')).toBe(true)
      expect(isSameConnectionGroup('か', 'さ')).toBe(false)
    })

    it('濁音・清音は同一グループ', () => {
      expect(isSameConnectionGroup('か', 'が')).toBe(true)
      expect(isSameConnectionGroup('さ', 'ざ')).toBe(true)
    })

    it('は行は清音・濁音・半濁音が同一グループ', () => {
      expect(isSameConnectionGroup('は', 'ば')).toBe(true)
      expect(isSameConnectionGroup('は', 'ぱ')).toBe(true)
      expect(isSameConnectionGroup('ば', 'ぱ')).toBe(true)
    })
  })

  describe('normalizeTail', () => {
    it('通常の語尾はそのまま', () => {
      expect(normalizeTail('しりとり')).toContain('り')
    })

    it('拗音は直音に変換', () => {
      expect(normalizeTail('きしゃ')).toContain('や')
      expect(normalizeTail('きょーー')).toContain('よ')
    })

    it('促音はつに変換', () => {
      expect(normalizeTail('きゃっ')).toContain('つ')
    })

    it('小さいあ行は直音に変換', () => {
      expect(normalizeTail('まぁ')).toContain('あ')
    })

    it('伸ばし棒は遡って変換', () => {
      expect(normalizeTail('ぎたー')).toContain('た')
      expect(normalizeTail('らーー')).toContain('ら')
    })

    it('ん で終わる場合は空配列', () => {
      expect(normalizeTail('きりん')).toEqual([])
    })
  })

  describe('isValidInputChars', () => {
    it('ひらがなと伸ばし棒は有効', () => {
      expect(isValidInputChars('しりとり')).toBe(true)
      expect(isValidInputChars('らーめん')).toBe(true)
    })

    it('空文字は無効', () => {
      expect(isValidInputChars('')).toBe(false)
    })

    it('漢字・カタカナ・英字は無効', () => {
      expect(isValidInputChars('東京')).toBe(false)
      expect(isValidInputChars('シリトリ')).toBe(false)
      expect(isValidInputChars('test')).toBe(false)
    })
  })

  describe('validateWordForFrontend', () => {
    it('空文字は拒否', () => {
      const result = validateWordForFrontend('')
      expect(result.valid).toBe(false)
    })

    it('ひらがな以外は拒否', () => {
      const result = validateWordForFrontend('Tokyo')
      expect(result.valid).toBe(false)
    })

    it('接続条件を満たす単語は有効', () => {
      const result = validateWordForFrontend('りんご', 'り')
      expect(result.valid).toBe(true)
    })

    it('接続条件を満たさない単語は拒否', () => {
      const result = validateWordForFrontend('ごりら', 'り')
      expect(result.valid).toBe(false)
    })

    it('最初の単語は濁点緩和なし', () => {
      const result = validateWordForFrontend('がっこう', 'か', true)
      expect(result.valid).toBe(false)
    })
  })
})
