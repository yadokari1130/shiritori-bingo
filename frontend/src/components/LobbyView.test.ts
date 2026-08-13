import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import LobbyView from './LobbyView.vue'
import { useGameStore } from '../store/game'
import { createDefaultSettings } from '../types'

describe('LobbyView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    document.body.innerHTML = ''
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('ルール説明ボタンを押すとルール説明モーダルが表示される', async () => {
    const store = useGameStore()
    store.roomId = 'room-123'
    store.myPlayerId = 'p1'
    store.applyGameState({
      phase: 'setup',
      settings: {
        ...createDefaultSettings(),
        mode: 'team',
        teamCount: 3,
      },
      hostPlayerId: 'p1',
      freeChar: 'あ',
      players: [
        {
          id: 'p1',
          name: 'ホスト',
          teamId: null,
          status: null,
          connectionStatus: 'connected',
          disconnectedAt: null,
          card: null,
          bingoLineIds: null,
          openedCellCount: null,
        },
      ],
      teams: [],
      playOrder: [],
      round: 0,
      roundRoster: [],
      orderIndex: 0,
      currentPlayerId: null,
      currentTeamId: null,
      requiredStartChar: '',
      usedWords: [],
      wordHistory: [],
      remainingTimeMs: 0,
      currentTurnTimeLimitMs: 0,
      currentTurnInputPlayerId: null,
      turnStartedAt: null,
      result: null,
      undoHistory: [],
    })

    const wrapper = mount(LobbyView, {
      attachTo: document.body,
    })
    expect(document.body.querySelector('.rule-modal-backdrop')).toBeNull()

    // ルール説明ボタンをクリック
    const ruleBtn = wrapper.findAll('button').find((b) => b.text().includes('ルール説明'))
    expect(ruleBtn).toBeDefined()
    await ruleBtn!.trigger('click')

    const modal = document.body.querySelector('.rule-modal-backdrop')
    expect(modal).not.toBeNull()
    // チーム戦の設定がモーダルに反映されている
    expect(modal?.textContent).toContain('チーム戦 (3チーム)')

    wrapper.unmount()
  })
})
