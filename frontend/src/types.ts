/**
 * しりとりビンゴの型定義
 *
 * 仕様書 9. データモデル・状態遷移 をベースにしている。
 */

/** カード文字設定 */
export interface CardOptions {
  yoon: boolean
  sokuon: boolean
  prolonged: boolean
  smallA: boolean
  dakuten: boolean
  handakuten: boolean
}

/** ゲームルール設定 */
export interface Settings {
  cardSize: number
  mode: 'individual' | 'team'
  teamCount: number
  cardOptions: CardOptions
  endCondition: 'turns' | 'bingos'
  targetTurns: number
  targetBingos: number
  timeLimitSeconds: number
  extraTimeSeconds: number
  forceSkipOnTimeout: boolean
  invalidAction: 'skip' | 'disqualify'
  minWordLength: number | null
  maxWordLength: number | null
}

/** 初期設定値を返す */
export function createDefaultSettings(): Settings {
  return {
    cardSize: 5,
    mode: 'individual',
    teamCount: 2,
    cardOptions: {
      yoon: false,
      sokuon: false,
      prolonged: false,
      smallA: false,
      dakuten: true,
      handakuten: true,
    },
    endCondition: 'turns',
    targetTurns: 3,
    targetBingos: 3,
    timeLimitSeconds: 30,
    extraTimeSeconds: 10,
    forceSkipOnTimeout: false,
    invalidAction: 'skip',
    minWordLength: null,
    maxWordLength: null,
  }
}

/** マスデータ */
export interface Cell {
  index: number
  row: number
  column: number
  char: string
  isFree: boolean
  isOpen: boolean
}

/** ビンゴカード */
export interface BingoCard {
  size: number
  cells: Cell[]
  freeChar: string
}

/** プレイヤー */
export interface Player {
  id: string
  name: string
  teamId: string | null
  status: 'active' | 'disqualified' | null
  connectionStatus: 'connected' | 'disconnected'
  disconnectedAt: number | null
  card: BingoCard | null
  bingoLineIds: string[] | null
  openedCellCount: number | null
}

/** チーム */
export interface Team {
  id: string
  memberPlayerIds: string[]
  status: 'active' | 'disqualified'
  card: BingoCard | null
  bingoLineIds: string[]
  openedCellCount: number
}

/** 単語履歴エントリ */
export interface WordEntry {
  word: string
  playerId: string
  round: number
  sequence: number
  openedChars: string[]
}

/** 順位エントリ */
export interface Ranking {
  rank: number | null
  subjectType: 'player' | 'team'
  subjectId: string
  bingoCount: number
  openedCellCount: number
  status: 'active' | 'disqualified'
}

/** 結果スナップショット内のプレイヤー情報 */
export interface PlayerResult {
  playerId: string
  name: string
  teamId: string | null
  status: 'active' | 'disqualified' | null
  card: BingoCard | null
  bingoLineIds: string[] | null
  openedCellCount: number | null
  connectionStatus: 'connected' | 'disconnected'
}

/** 結果スナップショット内のチーム情報 */
export interface TeamResult {
  teamId: string
  memberPlayerIds: string[]
  status: 'active' | 'disqualified'
  card: BingoCard
  bingoLineIds: string[]
  openedCellCount: number
}

/** 結果スナップショット */
export interface ResultSnapshot {
  players: PlayerResult[]
  teams: TeamResult[]
  wordHistory: WordEntry[]
  freeChar: string
  settings: Settings
}

/** ゲーム結果 */
export interface GameResult {
  reason: 'turns' | 'bingos' | 'all_disqualified'
  endRound: number
  achieverPlayerIds: string[]
  achieverTeamIds: string[]
  rankings: Ranking[]
  snapshot: ResultSnapshot
}

/** undo スナップショット */
export interface UndoSnapshot {
  gameStateBeforeAction: GameSnapshot
  restoredTurnTimeLimitMs: number
}

/** 復元用のゲームスナップショット（undoHistory を除く） */
export type GameSnapshot = Omit<GameState, 'undoHistory'>

/** ゲーム状態 */
export interface GameState {
  phase: 'setup' | 'playing' | 'result'
  settings: Settings
  hasPassword?: boolean
  hostPlayerId: string | null
  freeChar: string
  players: Player[]
  teams: Team[]
  playOrder: string[]
  round: number
  roundRoster: string[]
  orderIndex: number
  currentPlayerId: string | null
  currentTeamId: string | null
  requiredStartChar: string
  usedWords: string[]
  wordHistory: WordEntry[]
  remainingTimeMs: number
  currentTurnTimeLimitMs: number
  currentTurnInputPlayerId: string | null
  turnStartedAt: number | null
  result: GameResult | null
  undoHistory?: UndoSnapshot[]
}

/** 名前付き設定プリセット */
export interface Preset {
  id: string
  name: string
  settings: Settings
  createdAt: number
  updatedAt: number
}

/** SSE イベント種別 */
export type SseEventType = 'initial' | 'update' | 'error' | 'ping'

/** SSE イベントペイロード */
export interface SsePayload {
  event: SseEventType
  timestamp: number
  gameState: GameState
  notice?: string
}

/** API レスポンス: ルーム作成 */
export interface CreateRoomResponse {
  roomId: string
  url: string
  gameState: GameState
}

/** API レスポンス: 参加 */
export interface JoinRoomResponse {
  gameState: GameState
  playerId: string
  isHost: boolean
}

/** API レスポンス: 汎用 */
export interface ApiGameStateResponse {
  gameState: GameState
}

/** API レスポンス: アクション */
export interface ActionResponse {
  success: boolean
  gameState: GameState
}

/** API レスポンス: ルーム情報 */
export interface RoomInfoResponse {
  phase: 'setup' | 'playing' | 'result'
  hasPassword: boolean
}

/** フロントエンドの画面状態 */
export type ViewPhase = 'top' | 'lobby' | 'playing' | 'result'

/** 通信状態 */
export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'reconnecting'
