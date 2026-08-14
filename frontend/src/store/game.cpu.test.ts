import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useGameStore } from './game'
import * as api from '../api'
import type { GameState } from '../types'
import { createDefaultSettings } from '../types'

vi.mock('../api', () => ({
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
  fetchWordSuggestions: vi.fn(),
}))

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

  it('setAssistMode: 補助モードを切り替え、手番時に推薦単語を取得する', async () => {
    const store = useGameStore()
    const state = createBaseGameState()
    state.phase = 'playing'
    state.players[0].status = 'active'
    state.currentPlayerId = 'player-1'
    store.roomId = 'room-1'
    store.myPlayerId = 'player-1'

    vi.mocked(api.fetchWordSuggestions).mockResolvedValue({
      suggestions: ['りんご', 'りす', 'りぼん'],
    })

    store.setAssistMode(true)
    expect(store.assistMode).toBe(true)
    expect(localStorage.getItem('shiritori-bingo:assist-mode')).toBe('true')

    store.applyGameState(state)
    await store.fetchWordSuggestions()

    expect(api.fetchWordSuggestions).toHaveBeenCalledWith('room-1')
    expect(store.wordSuggestions).toEqual(['りんご', 'りす', 'りぼん'])
  })

  it('isHost: CPUプレイヤーはisHostがfalseになる', () => {
    const store = useGameStore()
    const state = createBaseGameState()
    state.players.push({
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
    })
    // 万が一 hostPlayerId が CPU に設定されていても、myPlayerId が cpu-1 の場合は isHost は false
    state.hostPlayerId = 'cpu-1'
    store.myPlayerId = 'cpu-1'
    store.applyGameState(state)

    expect(store.isHost).toBe(false)
  })
})
