import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useGameStore } from './game'
import { createDefaultSettings } from '../types'
import type { GameState } from '../types'

function createMockGameState(overrides: Partial<GameState> = {}): GameState {
  return {
    phase: 'setup',
    settings: createDefaultSettings(),
    hasPassword: false,
    hostPlayerId: 'host',
    freeChar: 'あ',
    players: [],
    teams: [],
    playOrder: [],
    round: 1,
    roundRoster: [],
    orderIndex: 0,
    currentPlayerId: null,
    currentTeamId: null,
    requiredStartChar: 'あ',
    usedWords: [],
    wordHistory: [],
    remainingTimeMs: 30000,
    currentTurnTimeLimitMs: 30000,
    currentTurnInputPlayerId: null,
    turnStartedAt: null,
    result: null,
    undoHistory: [],
    ...overrides,
  }
}

describe('game ストア', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('初期状態は top 画面', () => {
    const store = useGameStore()
    expect(store.view).toBe('top')
    expect(store.gameState).toBeNull()
  })

  it('gameState.phase で画面を解決する', () => {
    const store = useGameStore()
    store.applyGameState(createMockGameState({ phase: 'setup' }))
    expect(store.view).toBe('lobby')
  })

  it('playing 状態なら canInput は現在プレイヤーのみ true', () => {
    const store = useGameStore()
    store.myPlayerId = 'p1'
    store.applyGameState(createMockGameState({
      phase: 'playing',
      players: [
        { id: 'p1', name: '太郎', teamId: null, status: 'active', connectionStatus: 'connected', disconnectedAt: null, card: null, bingoLineIds: null, openedCellCount: null },
      ],
      playOrder: ['p1'],
      roundRoster: ['p1'],
      currentPlayerId: 'p1',
    }))
    expect(store.canInput).toBe(true)
  })

  it('tryReconnect: 再接続成功時は true を返し画面を復元する', async () => {
    const store = useGameStore()
    const vi_api = await import('../api')
    const joinSpy = vi.spyOn(vi_api, 'joinRoom').mockResolvedValue({
      playerId: 'p1',
      isHost: true,
      gameState: createMockGameState({
        phase: 'setup',
        hostPlayerId: 'p1',
        players: [
          { id: 'p1', name: '太郎', teamId: null, status: 'active', connectionStatus: 'connected', disconnectedAt: null, card: null, bingoLineIds: null, openedCellCount: null },
        ],
        playOrder: ['p1'],
        roundRoster: ['p1'],
      }),
    })

    const result = await store.tryReconnect('room123')
    expect(result).toBe(true)
    expect(joinSpy).toHaveBeenCalledWith('room123', '', null)
    expect(store.myPlayerId).toBe('p1')
    expect(store.view).toBe('lobby')
  })

  it('tryReconnect: 再接続失敗（Cookieなし等）時は false を返す', async () => {
    const store = useGameStore()
    const vi_api = await import('../api')
    vi.spyOn(vi_api, 'joinRoom').mockRejectedValue(new vi_api.ApiError('名前を入力してください', 400))

    const result = await store.tryReconnect('room123')
    expect(result).toBe(false)
    expect(store.errorMessage).toBeNull()
  })

  it('joinRoom: ゲーム中の403エラー時はサーバーメッセージ「ゲーム中のため参加できません」をerrorMessageに設定する', async () => {
    const store = useGameStore()
    const vi_api = await import('../api')
    vi.spyOn(vi_api, 'joinRoom').mockRejectedValue(new vi_api.ApiError('ゲーム中のため参加できません', 403))

    await expect(store.joinRoom('room123', 'プレイヤー名')).rejects.toThrow()
    expect(store.errorMessage).toBe('ゲーム中のため参加できません')
  })

  it('joinRoom: パスワード不一致の403エラー時は「パスワードが違います」をerrorMessageに設定する', async () => {
    const store = useGameStore()
    const vi_api = await import('../api')
    vi.spyOn(vi_api, 'joinRoom').mockRejectedValue(new vi_api.ApiError('パスワードが違います', 403))

    await expect(store.joinRoom('room123', 'プレイヤー名', 'wrong')).rejects.toThrow()
    expect(store.errorMessage).toBe('パスワードが違います')
  })

  it('createRoom: 作成時に指定したパスワードが保持され、同一ルームへのjoinRoomで自動引き継ぎされる', async () => {
    const store = useGameStore()
    const vi_api = await import('../api')
    vi.spyOn(vi_api, 'createRoom').mockResolvedValue({
      roomId: 'room-pass-123',
      url: 'http://localhost:5173/game/room-pass-123',
      gameState: createMockGameState({
        hasPassword: true,
      }),
    })
    const joinRoomSpy = vi.spyOn(vi_api, 'joinRoom').mockResolvedValue({
      playerId: 'p1',
      isHost: true,
      gameState: createMockGameState({
        hasPassword: true,
        hostPlayerId: 'p1',
        players: [{ id: 'p1', name: '作成者', teamId: null, status: 'active', connectionStatus: 'connected', disconnectedAt: null, card: null, bingoLineIds: null, openedCellCount: null }],
        playOrder: ['p1'],
        roundRoster: ['p1'],
      }),
    })

    await store.createRoom('secret123')
    expect(store.lastCreatedPassword).toBe('secret123')

    // パスワード引数なしでjoinRoomを実行しても、作成時のパスワードが使われる
    await store.joinRoom('room-pass-123', '作成者')
    expect(joinRoomSpy).toHaveBeenCalledWith('room-pass-123', '作成者', 'secret123')
  })

  it('joinRoom: 404エラー時は「ルームが見つかりません。」をerrorMessageに設定する', async () => {
    const store = useGameStore()
    const vi_api = await import('../api')
    vi.spyOn(vi_api, 'joinRoom').mockRejectedValue(new vi_api.ApiError('Not Found', 404))

    await expect(store.joinRoom('invalid_room', 'プレイヤー名')).rejects.toThrow()
    expect(store.errorMessage).toBe('ルームが見つかりません。')
  })

  it('changeHost: api.changeHost を呼び出して状態を更新する', async () => {
    const store = useGameStore()
    store.roomId = 'room123'
    const vi_api = await import('../api')
    const changeHostSpy = vi.spyOn(vi_api, 'changeHost').mockResolvedValue({
      gameState: createMockGameState({
        hostPlayerId: 'p2',
        players: [
          { id: 'p1', name: '太郎', teamId: null, status: 'active', connectionStatus: 'connected', disconnectedAt: null, card: null, bingoLineIds: null, openedCellCount: null },
          { id: 'p2', name: '次郎', teamId: null, status: 'active', connectionStatus: 'connected', disconnectedAt: null, card: null, bingoLineIds: null, openedCellCount: null },
        ],
      }),
    })

    await store.changeHost('p2')
    expect(changeHostSpy).toHaveBeenCalledWith('room123', 'p2')
    expect(store.gameState?.hostPlayerId).toBe('p2')
  })

  it('kickPlayer: api.kickPlayer を呼び出して状態を更新する', async () => {
    const store = useGameStore()
    store.roomId = 'room123'
    const vi_api = await import('../api')
    const kickSpy = vi.spyOn(vi_api, 'kickPlayer').mockResolvedValue({
      gameState: createMockGameState({
        hostPlayerId: 'p1',
        players: [
          { id: 'p1', name: '太郎', teamId: null, status: 'active', connectionStatus: 'connected', disconnectedAt: null, card: null, bingoLineIds: null, openedCellCount: null },
        ],
      }),
    })

    await store.kickPlayer('p2')
    expect(kickSpy).toHaveBeenCalledWith('room123', 'p2')
    expect(store.gameState?.players.length).toBe(1)
  })

  it('applyGameState: 自身がプレイヤーリストから除外された場合トップ画面へ戻る', () => {
    const store = useGameStore()
    store.roomId = 'room123'
    store.myPlayerId = 'p2'
    store.view = 'lobby'

    store.applyGameState(createMockGameState({
      hostPlayerId: 'p1',
      players: [
        { id: 'p1', name: '太郎', teamId: null, status: 'active', connectionStatus: 'connected', disconnectedAt: null, card: null, bingoLineIds: null, openedCellCount: null },
      ],
    }))

    expect(store.view).toBe('top')
    expect(store.roomId).toBeNull()
    expect(store.myPlayerId).toBeNull()
    expect(store.errorMessage).toBe('ルームから退出させられました。')
  })

  it('selectTeam: チームの選択および離脱(null)ができる', async () => {
    const store = useGameStore()
    store.roomId = 'room123'
    store.myPlayerId = 'p1'
    const vi_api = await import('../api')
    const teamSpy = vi.spyOn(vi_api, 'selectTeam').mockResolvedValue({
      gameState: createMockGameState({
        settings: { ...createDefaultSettings(), mode: 'team', teamCount: 2 },
        hostPlayerId: 'p1',
        players: [
          { id: 'p1', name: '太郎', teamId: null, status: 'active', connectionStatus: 'connected', disconnectedAt: null, card: null, bingoLineIds: null, openedCellCount: null },
        ],
        teams: [
          { id: 'team-1', status: 'active', card: null, bingoLineIds: [], openedCellCount: 0, memberPlayerIds: [] },
          { id: 'team-2', status: 'active', card: null, bingoLineIds: [], openedCellCount: 0, memberPlayerIds: [] },
        ],
      }),
    })

    await store.selectTeam(null)
    expect(teamSpy).toHaveBeenCalledWith('room123', null)
    expect(store.myPlayer?.teamId).toBeNull()
  })

  it('leaveAndGoToTop: api.leaveRoom を呼び出してトップ画面に戻りURLを/に更新する', async () => {
    window.history.pushState(null, '', '/game/room123')
    const store = useGameStore()
    store.roomId = 'room123'
    store.myPlayerId = 'p1'
    store.view = 'result'
    store.gameState = createMockGameState({
      phase: 'result',
      hostPlayerId: 'p1',
      players: [
        { id: 'p1', name: '太郎', teamId: null, status: 'active', connectionStatus: 'connected', disconnectedAt: null, card: null, bingoLineIds: null, openedCellCount: null },
      ],
    })

    const vi_api = await import('../api')
    const leaveSpy = vi.spyOn(vi_api, 'leaveRoom').mockResolvedValue(undefined)
    const pushStateSpy = vi.spyOn(window.history, 'pushState')

    await store.leaveAndGoToTop()
    expect(leaveSpy).toHaveBeenCalledWith('room123')
    expect(pushStateSpy).toHaveBeenCalledWith(null, '', '/')
    expect(window.location.pathname).toBe('/')
    expect(store.view).toBe('top')
    expect(store.roomId).toBeNull()
    expect(store.myPlayerId).toBeNull()
  })

  it('dissolveRoom: api.deleteRoom を呼び出してトップ画面に戻り通知を設定する', async () => {
    const store = useGameStore()
    store.roomId = 'room123'
    store.myPlayerId = 'p1'
    store.view = 'lobby'

    const vi_api = await import('../api')
    const deleteSpy = vi.spyOn(vi_api, 'deleteRoom').mockResolvedValue(undefined)

    await store.dissolveRoom()
    expect(deleteSpy).toHaveBeenCalledWith('room123')
    expect(store.view).toBe('top')
    expect(store.roomId).toBeNull()
    expect(store.noticeMessage).toBe('部屋を解散しました。')
  })

  it('startGame: 指定された settings があれば api.startGame に渡して開始する', async () => {
    const store = useGameStore()
    store.roomId = 'room123'

    const customSettings = {
      ...createDefaultSettings(),
      cardSize: 3,
      minWordLength: 3,
    }

    const mockGameState = createMockGameState({
      phase: 'playing',
      settings: customSettings,
      hostPlayerId: 'p1',
      currentPlayerId: 'p1',
    })

    const vi_api = await import('../api')
    const startSpy = vi.spyOn(vi_api, 'startGame').mockResolvedValue({
      gameState: mockGameState,
    })

    await store.startGame(customSettings)
    expect(startSpy).toHaveBeenCalledWith('room123', customSettings)
    expect(store.gameState?.settings.cardSize).toBe(3)
    expect(store.gameState?.settings.minWordLength).toBe(3)
  })
})


