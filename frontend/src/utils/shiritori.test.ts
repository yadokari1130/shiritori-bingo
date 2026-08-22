import { describe, expect, it } from 'vitest'
import {
  buildCardCharPool,
  getFreeCharCandidates,
  isSameConnectionGroup,
  isSmallKana,
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
      expect(normalizeTail('んー')).toEqual([])
      expect(normalizeTail('らーめんー')).toEqual([])
      expect(normalizeTail('うどんーー')).toEqual([])
    })
  })

  describe('isValidInputChars', () => {
    it('ひらがなと伸ばし棒は有効', () => {
      expect(isValidInputChars('しりとり')).toBe(true)
      expect(isValidInputChars('らーめん')).toBe(true)
      expect(isValidInputChars('ぱんだ')).toBe(true)
      expect(isValidInputChars('ゔぁよりん')).toBe(true)
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
    it('空文字は常に拒否', () => {
      expect(validateWordForFrontend('').valid).toBe(false)
      expect(validateWordForFrontend('', { inputWordCheck: false }).valid).toBe(false)
    })

    it('ひらがな・伸ばし棒以外は常に拒否', () => {
      expect(validateWordForFrontend('Tokyo').valid).toBe(false)
      expect(validateWordForFrontend('Tokyo', { inputWordCheck: false }).valid).toBe(false)
      expect(validateWordForFrontend('漢字').valid).toBe(false)
      expect(validateWordForFrontend('漢字', { inputWordCheck: false }).valid).toBe(false)
    })

    describe('inputWordCheck: true（デフォルト）の場合', () => {
      it('接続条件を満たす単語は有効', () => {
        const result = validateWordForFrontend('りんご', { requiredStartChar: 'り' })
        expect(result.valid).toBe(true)
      })

      it('濁点・半濁点の付け外し（緩和）が成立する', () => {
        // は行：清音・濁音・半濁音の相互接続
        expect(validateWordForFrontend('ぱんだ', { requiredStartChar: 'は' }).valid).toBe(true)
        expect(validateWordForFrontend('ばなな', { requiredStartChar: 'は' }).valid).toBe(true)
        expect(validateWordForFrontend('はさみ', { requiredStartChar: 'ぱ' }).valid).toBe(true)
        expect(validateWordForFrontend('ばなな', { requiredStartChar: 'ぱ' }).valid).toBe(true)
        expect(validateWordForFrontend('ぱんつ', { requiredStartChar: 'ぱ' }).valid).toBe(true)
        expect(validateWordForFrontend('ぱんだ', { requiredStartChar: 'ば' }).valid).toBe(true)
        expect(validateWordForFrontend('はさみ', { requiredStartChar: 'ば' }).valid).toBe(true)

        // か行
        expect(validateWordForFrontend('がす', { requiredStartChar: 'か' }).valid).toBe(true)
        expect(validateWordForFrontend('からす', { requiredStartChar: 'が' }).valid).toBe(true)

        // さ行
        expect(validateWordForFrontend('ざる', { requiredStartChar: 'さ' }).valid).toBe(true)
        expect(validateWordForFrontend('さる', { requiredStartChar: 'ざ' }).valid).toBe(true)

        // た行
        expect(validateWordForFrontend('だるま', { requiredStartChar: 'た' }).valid).toBe(true)
        expect(validateWordForFrontend('たいこ', { requiredStartChar: 'だ' }).valid).toBe(true)

        // う行（う・ゔ）
        expect(validateWordForFrontend('ゔぇーる', { requiredStartChar: 'う' }).valid).toBe(true)
        expect(validateWordForFrontend('うみ', { requiredStartChar: 'ゔ' }).valid).toBe(true)
      })

      it('unicode 結合文字（NFD）でも正しく判定される', () => {
        // 'は' + U+309A (半濁点) -> 'ぱ'
        const nfdPanda = 'は\u309Aんだ'
        expect(validateWordForFrontend(nfdPanda, { requiredStartChar: 'は' }).valid).toBe(true)
        expect(validateWordForFrontend(nfdPanda, { requiredStartChar: 'ぱ' }).valid).toBe(true)
      })

      it('接続条件を満たさない単語は拒否', () => {
        const result = validateWordForFrontend('ごりら', { requiredStartChar: 'り' })
        expect(result.valid).toBe(false)
        expect(result.reason).toBe('前の単語の最後の文字から始まっていません。')
      })

      it('最初の単語でも濁点・半濁点の付け外し（緩和）が可能', () => {
        const result = validateWordForFrontend('がっこう', { requiredStartChar: 'か', isFirstWord: true })
        expect(result.valid).toBe(true)

        const result2 = validateWordForFrontend('ぱんだ', { requiredStartChar: 'は', isFirstWord: true })
        expect(result2.valid).toBe(true)

        const result3 = validateWordForFrontend('ばなな', { requiredStartChar: 'は', isFirstWord: true })
        expect(result3.valid).toBe(true)

        const result4 = validateWordForFrontend('はいしゃ', { requiredStartChar: 'は', isFirstWord: true })
        expect(result4.valid).toBe(true)

        // 異なるグループは拒否
        const result5 = validateWordForFrontend('さる', { requiredStartChar: 'は', isFirstWord: true })
        expect(result5.valid).toBe(false)
      })

      it('「ん」で終わる単語（伸ばし棒含む）は拒否', () => {
        const result = validateWordForFrontend('きりん', { requiredStartChar: 'き' })
        expect(result.valid).toBe(false)
        expect(result.reason).toBe('「ん」で終わる単語は使えません。')

        const resultProlonged = validateWordForFrontend('らーめんー', { requiredStartChar: 'ら' })
        expect(resultProlonged.valid).toBe(false)
        expect(resultProlonged.reason).toBe('「ん」で終わる単語は使えません。')

        const resultUdon = validateWordForFrontend('うどんーー', { requiredStartChar: 'う' })
        expect(resultUdon.valid).toBe(false)
        expect(resultUdon.reason).toBe('「ん」で終わる単語は使えません。')
      })

      it('既出単語は拒否', () => {
        const result = validateWordForFrontend('りんご', { requiredStartChar: 'り', usedWords: ['りんご'] })
        expect(result.valid).toBe(false)
        expect(result.reason).toBe('この単語はすでに使われています。')
      })

      it('文字数制限外は拒否', () => {
        const minRes = validateWordForFrontend('りす', { requiredStartChar: 'り', minWordLength: 3 })
        expect(minRes.valid).toBe(false)
        expect(minRes.reason).toBe('設定された文字数の範囲外です。')

        const maxRes = validateWordForFrontend('りんご飴', { requiredStartChar: 'り' }) // 漢字で拒否
        expect(maxRes.valid).toBe(false)

        const maxRes2 = validateWordForFrontend('りんごばなな', { requiredStartChar: 'り', maxWordLength: 4 })
        expect(maxRes2.valid).toBe(false)
        expect(maxRes2.reason).toBe('設定された文字数の範囲外です。')
      })
    })

    describe('inputWordCheck: false の場合', () => {
      it('接続不一致や「ん」で終わる単語、既出単語、文字数範囲外でも空文字・非ひらがな以外は送信可能（valid: true）', () => {
        // 接続不一致
        expect(validateWordForFrontend('ごりら', { inputWordCheck: false, requiredStartChar: 'り' }).valid).toBe(true)
        // 「ん」で終わる単語
        expect(validateWordForFrontend('きりん', { inputWordCheck: false, requiredStartChar: 'き' }).valid).toBe(true)
        // 既出単語
        expect(validateWordForFrontend('りんご', { inputWordCheck: false, requiredStartChar: 'り', usedWords: ['りんご'] }).valid).toBe(true)
        // 文字数範囲外
        expect(validateWordForFrontend('りす', { inputWordCheck: false, requiredStartChar: 'り', minWordLength: 3 }).valid).toBe(true)
      })
    })
  })

  describe('isSmallKana', () => {
    it('拗音（ゃ, ゅ, ょ）は true を返す', () => {
      expect(isSmallKana('ゃ')).toBe(true)
      expect(isSmallKana('ゅ')).toBe(true)
      expect(isSmallKana('ょ')).toBe(true)
    })

    it('促音（っ）は true を返す', () => {
      expect(isSmallKana('っ')).toBe(true)
    })

    it('小さいあ行（ぁ, ぃ, ぅ, ぇ, ぉ）は true を返す', () => {
      expect(isSmallKana('ぁ')).toBe(true)
      expect(isSmallKana('ぃ')).toBe(true)
      expect(isSmallKana('ぅ')).toBe(true)
      expect(isSmallKana('ぇ')).toBe(true)
      expect(isSmallKana('ぉ')).toBe(true)
    })

    it('通常の清音・濁音・半濁音・伸ばし棒は false を返す', () => {
      expect(isSmallKana('あ')).toBe(false)
      expect(isSmallKana('つ')).toBe(false)
      expect(isSmallKana('や')).toBe(false)
      expect(isSmallKana('が')).toBe(false)
      expect(isSmallKana('ぱ')).toBe(false)
      expect(isSmallKana('ー')).toBe(false)
    })
  })
})
