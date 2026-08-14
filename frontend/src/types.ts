/** カード生成文字オプション */
export interface CardOptions {
  yoon: boolean
  sokuon: boolean
  prolonged: boolean
  smallA: boolean
  dakuten: boolean
  handakuten: boolean
}

/** ゲーム設定 */
export interface Settings {
  cardSize: number
  mode: 'individual' | 'team'
  teamCount: number
  timeLimitSeconds: number
  extraTimeSeconds: number
  forceSkipOnTimeout: boolean
  endCondition: 'turns' | 'bingos'
  targetTurns: number
  targetBingos: number
  invalidAction: 'skip' | 'disqualify'
  cardOptions: CardOptions
  inputWordCheck: boolean
  minWordLength: number | null
  maxWordLength: number | null
}

/** 設定プリセット */
export interface Preset {
  id: string
  name: string
  settings: Settings
  createdAt: number
  updatedAt: number
}

/** カードマス */
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
  isCpu?: boolean
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
  isCpu?: boolean
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

/** ゲーム状態 */
export interface GameState {
  phase: 'setup' | 'playing' | 'result'
  settings: Settings
  hasPassword: boolean
  freeChar: string | null
  players: Player[]
  teams: Team[]
  playOrder: string[]
  currentPlayerId: string | null
  currentTeamId: string | null
  currentTurnInputPlayerId: string | null
  requiredStartChar: string | null
  usedWords: string[]
  wordHistory: WordEntry[]
  round: number
  orderIndex: number
  roundRoster: string[]
  remainingTimeMs: number
  currentTurnTimeLimitMs: number
  turnStartedAt: number | null
  result: GameResult | null
  hostPlayerId: string | null
  undoHistory?: unknown[]
}

/** アシスト候補レスポンス */
export interface AssistResponse {
  suggestions: string[]
}

/** 接続状態 */
export type SseConnectionStatus = 'connecting' | 'connected' | 'disconnected'

/** ルーム情報レスポンス */
export interface RoomInfoResponse {
  roomId: string
  phase: 'setup' | 'playing' | 'result'
  hasPassword: boolean
}

/** ルーム作成レスポンス */
export interface CreateRoomResponse {
  roomId: string
  url: string
  gameState: GameState
}

/** ルーム参加レスポンス */
export interface JoinRoomResponse {
  playerId: string
  isHost: boolean
  gameState?: GameState
}

/** 汎用 GameState レスポンス */
export interface ApiGameStateResponse {
  gameState: GameState
}

/** アクション実行レスポンス */
export interface ActionResponse {
  success: boolean
  gameState: GameState
}

/** 接続状態（UI用） */
export type ConnectionStatus = 'connected' | 'connecting' | 'reconnecting' | 'disconnected'

/** 画面ビューフェーズ */
export type ViewPhase = 'top' | 'lobby' | 'playing' | 'result'

/** デフォルト設定を生成する */
export function createDefaultSettings(): Settings {
  return {
    cardSize: 5,
    mode: 'individual',
    teamCount: 2,
    timeLimitSeconds: 30,
    extraTimeSeconds: 10,
    forceSkipOnTimeout: false,
    endCondition: 'turns',
    targetTurns: 3,
    targetBingos: 3,
    invalidAction: 'skip',
    cardOptions: {
      yoon: false,
      sokuon: false,
      prolonged: false,
      smallA: false,
      dakuten: true,
      handakuten: true,
    },
    inputWordCheck: true,
    minWordLength: null,
    maxWordLength: null,
  }
}

/** GameStateから表示フェーズを判定する */
export function resolveViewFromPhase(state: GameState | null): ViewPhase {
  if (!state) return 'top'
  switch (state.phase) {
    case 'setup':
      return 'lobby'
    case 'playing':
      return 'playing'
    case 'result':
      return 'result'
    default:
      return 'top'
  }
}


