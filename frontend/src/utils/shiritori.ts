/**
 * しりとり用の文字処理と入力検証
 *
 * 仕様書 4. ゲームルール詳細、6. カード生成・ビンゴ判定 に基づく。
 */

/** 清音候補（あいうえお表）。仕様 6.2 */
export const SEIONG_CHARS: readonly string[] = [
  'あ', 'い', 'う', 'え', 'お',
  'か', 'き', 'く', 'け', 'こ',
  'さ', 'し', 'す', 'せ', 'そ',
  'た', 'ち', 'つ', 'て', 'と',
  'な', 'に', 'ぬ', 'ね', 'の',
  'は', 'ひ', 'ふ', 'へ', 'ほ',
  'ま', 'み', 'む', 'め', 'も',
  'や', 'ゆ', 'よ',
  'ら', 'り', 'る', 'れ', 'ろ',
  'わ',
]

/** カードに含めない文字 */
export const EXCLUDED_CARD_CHARS: readonly string[] = ['ん', 'ゐ', 'ゑ', 'ゔ', 'を']

/** 拗音カテゴリ */
export const YOON_CHARS: readonly string[] = ['ゃ', 'ゅ', 'ょ']
/** 促音カテゴリ */
export const SOKUON_CHARS: readonly string[] = ['っ']
/** 伸ばし棒カテゴリ */
export const PROLONGED_CHARS: readonly string[] = ['ー']
/** 小さいあ行カテゴリ */
export const SMALL_A_CHARS: readonly string[] = ['ぁ', 'ぃ', 'ぅ', 'ぇ', 'ぉ']
/** 濁音カテゴリ */
export const DAKUTEN_CHARS: readonly string[] = [
  'が', 'ぎ', 'ぐ', 'げ', 'ご',
  'ざ', 'じ', 'ず', 'ぜ', 'ぞ',
  'だ', 'ぢ', 'づ', 'で', 'ど',
  'ば', 'び', 'ぶ', 'べ', 'ぼ',
]
/** 半濁音カテゴリ */
export const HANDAKUTEN_CHARS: readonly string[] = ['ぱ', 'ぴ', 'ぷ', 'ぺ', 'ぽ']

/** 小文字（拗音・促音・小さいあ行）の全文字 */
export const SMALL_KANA_CHARS: readonly string[] = [
  ...YOON_CHARS,
  ...SOKUON_CHARS,
  ...SMALL_A_CHARS,
]

/** 指定された1文字が小文字（拗音・促音・小さいあ行）かどうかを判定する */
export function isSmallKana(char: string): boolean {
  return SMALL_KANA_CHARS.includes(char)
}

/** カード文字候補を生成する。仕様 6.2, 6.3 */
export function buildCardCharPool(options: {
  yoon: boolean
  sokuon: boolean
  prolonged: boolean
  smallA: boolean
  dakuten: boolean
  handakuten: boolean
}): string[] {
  const pool = [...SEIONG_CHARS.filter((c) => !EXCLUDED_CARD_CHARS.includes(c))]
  if (options.yoon) pool.push(...YOON_CHARS)
  if (options.sokuon) pool.push(...SOKUON_CHARS)
  if (options.prolonged) pool.push(...PROLONGED_CHARS)
  if (options.smallA) pool.push(...SMALL_A_CHARS)
  if (options.dakuten) pool.push(...DAKUTEN_CHARS)
  if (options.handakuten) pool.push(...HANDAKUTEN_CHARS)
  return pool
}

/** カードサイズの上限を計算する。仕様 6.1 */
export function maxCardSize(cardCharPool: string[]): number {
  const m = cardCharPool.length
  let max = 3
  while ((max + 2) * (max + 2) <= m) {
    max += 2
  }
  return max
}

/** 清音候補（フリーマス用）を取得する。仕様 6.2 */
export function getFreeCharCandidates(): string[] {
  return SEIONG_CHARS.filter((c) => !EXCLUDED_CARD_CHARS.includes(c))
}

/** 濁音・半濁点の同一グループ定義。仕様 4.3.2 */
const DAKUON_GROUP: Record<string, string[]> = {
  'か': ['か', 'が'], 'が': ['か', 'が'],
  'き': ['き', 'ぎ'], 'ぎ': ['き', 'ぎ'],
  'く': ['く', 'ぐ'], 'ぐ': ['く', 'ぐ'],
  'け': ['け', 'げ'], 'げ': ['け', 'げ'],
  'こ': ['こ', 'ご'], 'ご': ['こ', 'ご'],
  'さ': ['さ', 'ざ'], 'ざ': ['さ', 'ざ'],
  'し': ['し', 'じ'], 'じ': ['し', 'じ'],
  'す': ['す', 'ず'], 'ず': ['す', 'ず'],
  'せ': ['せ', 'ぜ'], 'ぜ': ['せ', 'ぜ'],
  'そ': ['そ', 'ぞ'], 'ぞ': ['そ', 'ぞ'],
  'た': ['た', 'だ'], 'だ': ['た', 'だ'],
  'ち': ['ち', 'ぢ'], 'ぢ': ['ち', 'ぢ'],
  'つ': ['つ', 'づ'], 'づ': ['つ', 'づ'],
  'て': ['て', 'で'], 'で': ['て', 'で'],
  'と': ['と', 'ど'], 'ど': ['と', 'ど'],
  'は': ['は', 'ば', 'ぱ'], 'ば': ['は', 'ば', 'ぱ'], 'ぱ': ['は', 'ば', 'ぱ'],
  'ひ': ['ひ', 'び', 'ぴ'], 'び': ['ひ', 'び', 'ぴ'], 'ぴ': ['ひ', 'び', 'ぴ'],
  'ふ': ['ふ', 'ぶ', 'ぷ'], 'ぶ': ['ふ', 'ぶ', 'ぷ'], 'ぷ': ['ふ', 'ぶ', 'ぷ'],
  'へ': ['へ', 'べ', 'ぺ'], 'べ': ['へ', 'べ', 'ぺ'], 'ぺ': ['へ', 'べ', 'ぺ'],
  'ほ': ['ほ', 'ぼ', 'ぽ'], 'ぼ': ['ほ', 'ぼ', 'ぽ'], 'ぽ': ['ほ', 'ぼ', 'ぽ'],
  'う': ['う', 'ゔ'], 'ゔ': ['う', 'ゔ'],
}

/** 2文字がしりとりの同一接続グループに属するか。仕様 4.3.2 */
export function isSameConnectionGroup(a: string, b: string): boolean {
  const groupA = DAKUON_GROUP[a]
  const groupB = DAKUON_GROUP[b]
  if (!groupA || !groupB) return a === b
  return groupA === groupB || groupA.includes(b)
}

const YOON_TO_STRAIGHT: Record<string, string> = {
  'ゃ': 'や',
  'ゅ': 'ゆ',
  'ょ': 'よ',
}

const SMALL_A_TO_STRAIGHT: Record<string, string> = {
  'ぁ': 'あ',
  'ぃ': 'い',
  'ぅ': 'う',
  'ぇ': 'え',
  'ぉ': 'お',
}

function hasNormalCharBefore(tail: string, endIndex: number): boolean {
  for (let i = 0; i <= endIndex; i++) {
    const ch = tail[i]
    const isSpecial =
      PROLONGED_CHARS.includes(ch) ||
      YOON_CHARS.includes(ch) ||
      SOKUON_CHARS.includes(ch) ||
      SMALL_A_CHARS.includes(ch)
    if (!isSpecial) return true
  }
  return false
}

/**
 * 語尾を正規化して次の開始文字候補リストを返す。
 * 接続判定緩和のため、同一グループに属する文字すべてを返す。
 * 仕様 4.3.3
 */
export function normalizeTail(tail: string): string[] {
  if (tail.length === 0) return []

  // 1. 語尾が「ん」なら無効（空配列を返す）
  if (tail[tail.length - 1] === 'ん') return []

  // 2. 末尾の伸ばし棒をスキップ
  let i = tail.length - 1
  while (i >= 0 && PROLONGED_CHARS.includes(tail[i])) {
    i--
  }
  if (i < 0) return [] // 「ーー」など

  const ch = tail[i]

  // 3. 拗音 → 直音
  if (YOON_CHARS.includes(ch)) {
    if (!hasNormalCharBefore(tail, i)) return []
    const straight = YOON_TO_STRAIGHT[ch]
    return straight ? [straight] : []
  }

  // 4. 促音 → つ
  if (SOKUON_CHARS.includes(ch)) {
    if (!hasNormalCharBefore(tail, i)) return []
    return ['つ']
  }

  // 5. 小さいあ行 → 直音
  if (SMALL_A_CHARS.includes(ch)) {
    if (!hasNormalCharBefore(tail, i)) return []
    const straight = SMALL_A_TO_STRAIGHT[ch]
    return straight ? [straight] : []
  }

  // 6. 通常文字
  const group = DAKUON_GROUP[ch]
  return group ? [...group] : [ch]
}

/** 単語の最後の文字を取得する（空の場合は空文字） */
export function getLastChar(word: string): string {
  return word.length > 0 ? word[word.length - 1] : ''
}

/** 入力文字列がひらがなと伸ばし棒のみか検証する。仕様 4.2, 7.4 */
export function isValidInputChars(word: string): boolean {
  if (word.length === 0) return false
  return /^[\u3040-\u309fー]+$/.test(word)
}

/** 入力が空か検証する */
export function isEmptyInput(word: string): boolean {
  return word.trim().length === 0
}

/** 語尾が「ん」か検証する */
export function endsWithN(word: string): boolean {
  return getLastChar(word) === 'ん'
}

/** 単語がしりとりの接続条件を満たすかを検証する。 */
export function validateConnection(
  word: string,
  requiredStartChar: string,
): { valid: boolean; reason?: string } {
  if (word.length === 0) {
    return { valid: false, reason: '単語を入力してください。' }
  }
  if (!isValidInputChars(word)) {
    return { valid: false, reason: 'ひらがなと伸ばし棒で入力してください。' }
  }
  const candidates = normalizeTail(requiredStartChar)
  const first = word[0]
  if (candidates.length === 0) {
    return { valid: false, reason: '前の単語の語尾が無効です。' }
  }
  const matched = candidates.some((c) => isSameConnectionGroup(c, first))
  if (!matched) {
    return { valid: false, reason: '前の単語の最後の文字から始まっていません。' }
  }
  return { valid: true }
}

/** フロントエンドで確定前に入力を検証する。仕様 7.4, 12.1 */
export function validateWordForFrontend(
  word: string,
  requiredStartChar?: string,
  isFirstWord = false,
): { valid: boolean; reason?: string } {
  const trimmed = word.trim()
  if (trimmed.length === 0) {
    return { valid: false, reason: '単語を入力してください。' }
  }
  if (!isValidInputChars(trimmed)) {
    return { valid: false, reason: 'ひらがなと伸ばし棒で入力してください。' }
  }
  if (requiredStartChar && requiredStartChar.length > 0) {
    if (isFirstWord) {
      // 最初の単語はフリーマス文字と完全一致が必要（濁点緩和なし）。仕様 4.3.4
      if (trimmed[0] !== requiredStartChar) {
        return { valid: false, reason: `「${requiredStartChar}」から始めてください。` }
      }
      return { valid: true }
    }
    return validateConnection(trimmed, requiredStartChar)
  }
  return { valid: true }
}
