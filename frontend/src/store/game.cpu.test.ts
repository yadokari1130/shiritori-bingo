import type { GameState } from '../types'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '../api'
import { createDefaultSettings } from '../types'
import { useGameStore } from './game'

vi.mock('../api', () => {
  class ApiError extends Error {
    status: number
    constructor(message: string, status: number) {
      super(message)
      this.status = status
      this.name = 'ApiError'
    }
  }

  return {
    ApiError,
    createRoom: vi.fn(),
    joinRoom: vi.fn(),
    updateName: vi.fn(),
    updateSettings: vi.fn(),
    startGame: vi.fn(),
    changeHost: vi.fn(),
    kickPlayer: vi.fn(),
    selectTeam: vi.fn(),
    randomizeTeams: vi.fn(),
    submitWord: vi.fn(),
    submitSkip: vi.fn(),
    submitDisqualify: vi.fn(),
    submitUndo: vi.fn(),
    returnToLobby: vi.fn(),
    fetchRoomInfo: vi.fn(),
    leaveRoom: vi.fn(),
    deleteRoom: vi.fn(),
    notifyDisconnect: vi.fn(),
    getSseUrl: vi.fn().mockReturnValue('http://localhost/sse'),
    addCpu: vi.fn(),
    deleteAllCpus: vi.fn(),
    fetchWordSuggestions: vi.fn(),
  }
})

describe('gameStore CPU・補助モード連携', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    localStorage.clear()
  })

  function createBaseGameState(): GameState {
    return {
      phase: 'setup',
      settings: createDefaultSettings(),
      hasPassword: false,
      freeChar: null,
      players: [
        {
          id: 'player-1',
          name: 'ホスト',
          teamId: null,
          status: null,
          connectionStatus: 'connected',
          disconnectedAt: null,
          card: null,
          bingoLineIds: null,
          openedCellCount: null,
          isCpu: false,
        },
      ],
      teams: [],
      playOrder: [],
      currentPlayerId: null,
      currentTeamId: null,
      currentTurnInputPlayerId: null,
      requiredStartChar: null,
      usedWords: [],
      wordHistory: [],
      round: 0,
      orderIndex: 0,
      roundRoster: [],
      remainingTimeMs: 0,
      currentTurnTimeLimitMs: 0,
      turnStartedAt: null,
      result: null,
      hostPlayerId: 'player-1',
    }
  }

  it('addCpu: 親がCPUプレイヤーを追加できる', async () => {
    const store = useGameStore()
    const state = createBaseGameState()
    store.roomId = 'room-1'
    store.myPlayerId = 'player-1'
    store.applyGameState(state)

    const updatedState: GameState = {
      ...state,
      players: [
        ...state.players,
        {
          id: 'cpu-1',
          name: 'CPU 1',
          teamId: null,
          status: null,
          connectionStatus: 'connected',
          disconnectedAt: null,
          card: null,
          bingoLineIds: null,
          openedCellCount: null,
          isCpu: true,
        },
      ],
    }

    vi.mocked(api.addCpu).mockResolvedValueOnce({ gameState: updatedState })

    await store.addCpu()

    expect(api.addCpu).toHaveBeenCalledWith('room-1')
    expect(store.players.length).toBe(2)
    expect(store.players[1].isCpu).toBe(true)
  })

  it('deleteAllCpus: 親がCPUプレイヤーを一括削除できる', async () => {
    const store = useGameStore()
    const state = createBaseGameState()
    state.players.push(
      {
        id: 'cpu-1',
        name: 'CPU 1',
        teamId: null,
        status: null,
        connectionStatus: 'connected',
        disconnectedAt: null,
        card: null,
        bingoLineIds: null,
        openedCellCount: null,
        isCpu: true,
      },
      {
        id: 'cpu-2',
        name: 'CPU 2',
        teamId: null,
        status: null,
        connectionStatus: 'connected',
        disconnectedAt: null,
        card: null,
        bingoLineIds: null,
        openedCellCount: null,
        isCpu: true,
      },
    )
    store.roomId = 'room-1'
    store.myPlayerId = 'player-1'
    store.applyGameState(state)
    expect(store.players.length).toBe(3)

    const clearedState: GameState = {
      ...state,
      players: [state.players[0]],
    }

    vi.mocked(api.deleteAllCpus).mockResolvedValueOnce({ gameState: clearedState })

    await store.deleteAllCpus()

    expect(api.deleteAllCpus).toHaveBeenCalledWith('room-1')
    expect(store.players.length).toBe(1)
    expect(store.players.some(p => p.isCpu)).toBe(false)
  })

  it('deleteAllCpus: APIエラー発生時に errorMessage が設定される', async () => {
    const store = useGameStore()
    store.roomId = 'room-1'
    store.myPlayerId = 'player-1'

    vi.mocked(api.deleteAllCpus).mockRejectedValueOnce(new api.ApiError('一括削除に失敗しました', 500))

    await expect(store.deleteAllCpus()).rejects.toThrow()
    expect(store.errorMessage).toBe('一括削除に失敗しました')
  })

  it('isCurrentSubjectCpu & canInput: CPU手番のときは入力不可になる', () => {
    const store = useGameStore()
    const state = createBaseGameState()
    state.phase = 'playing'
    state.players.push({
      id: 'cpu-1',
      name: 'CPU 1',
      teamId: null,
      status: 'active',
      connectionStatus: 'connected',
      disconnectedAt: null,
      card: null,
      bingoLineIds: null,
      openedCellCount: null,
      isCpu: true,
    })
    state.currentPlayerId = 'cpu-1'
    store.myPlayerId = 'player-1'
    store.applyGameState(state)

    expect(store.isCurrentSubjectCpu).toBe(true)
    expect(store.canInput).toBe(false)
  })

  it('setAssistMode: 補助モードを切り替え、手番時に推薦単語を取得・反映する', async () => {
    const store = useGameStore()
    const state = createBaseGameState()
    state.phase = 'playing'
    state.players[0].status = 'active'
    state.currentPlayerId = 'player-1'
    state.assistSuggestions = ['りんご', 'りす', 'りぼん']
    store.roomId = 'room-1'
    store.myPlayerId = 'player-1'

    store.applyGameState(state)
    store.setAssistMode(true)
    expect(store.assistMode).toBe(true)
    expect(localStorage.getItem('shiritori-bingo:assist-mode')).toBe('true')
    expect(store.wordSuggestions).toEqual(['りんご', 'りす', 'りぼん'])
  })

  it('他のプレイヤーの手番中であっても補助モードをONにすると共通の候補単語を閲覧できる', async () => {
    const store = useGameStore()
    const state = createBaseGameState()
    state.phase = 'playing'
    state.players[0].status = 'active'
    state.players.push({
      id: 'player-2',
      name: 'ゲスト',
      teamId: null,
      status: 'active',
      connectionStatus: 'connected',
      disconnectedAt: null,
      card: null,
      bingoLineIds: null,
      openedCellCount: null,
      isCpu: false,
    })
    state.currentPlayerId = 'player-2' // 他人の手番
    state.assistSuggestions = ['たいやき', 'たぬき', 'たまご']
    store.roomId = 'room-1'
    store.myPlayerId = 'player-1'

    store.applyGameState(state)
    expect(store.canInput).toBe(false) // 自分の手番ではない

    // 補助モードをONにする
    store.setAssistMode(true)
    expect(store.assistMode).toBe(true)
    // 他人の手番中であっても候補単語が表示される
    expect(store.wordSuggestions).toEqual(['たいやき', 'たぬき', 'たまご'])
  })

  it('手番が移るタイミングで補助モード（候補表示）が自動的にOFFになる', async () => {
    const store = useGameStore()
    const state1 = createBaseGameState()
    state1.phase = 'playing'
    state1.players[0].status = 'active'
    state1.currentPlayerId = 'player-1'
    state1.assistSuggestions = ['りんご', 'りす', 'りぼん']
    store.roomId = 'room-1'
    store.myPlayerId = 'player-1'

    store.applyGameState(state1)
    store.setAssistMode(true)
    expect(store.assistMode).toBe(true)
    expect(store.wordSuggestions).toEqual(['りんご', 'りす', 'りぼん'])

    // 手番が player-2 に移る
    const state2 = {
      ...state1,
      orderIndex: 1,
      currentPlayerId: 'player-2',
      assistSuggestions: ['たいやき', 'たぬき', 'たまご'],
    }
    store.applyGameState(state2)

    // 手番が移ったので assistMode は false にリセットされ、候補もクリアされる
    expect(store.assistMode).toBe(false)
    expect(store.wordSuggestions).toEqual([])
    expect(localStorage.getItem('shiritori-bingo:assist-mode')).toBe('false')

    // 手番が移った後、再度補助モードをONにすると新しい手番の候補が見える
    store.setAssistMode(true)
    expect(store.assistMode).toBe(true)
    expect(store.wordSuggestions).toEqual(['たいやき', 'たぬき', 'たまご'])
  })
})
