import type { GameState } from '../types'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useGameStore } from '../store/game'
import { createDefaultSettings } from '../types'
import ConfirmModal from './ConfirmModal.vue'
import LobbyView from './LobbyView.vue'

function createLobbyState(overrides: Partial<GameState> = {}): GameState {
  return {
    phase: 'setup',
    hasPassword: false,
    settings: {
      ...createDefaultSettings(),
      mode: 'individual',
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
      {
        id: 'p2',
        name: 'ゲスト',
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
    ...overrides,
  }
}

describe('lobbyView', () => {
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
    store.applyGameState(
      createLobbyState({
        settings: {
          ...createDefaultSettings(),
          mode: 'team',
          teamCount: 3,
        },
      }),
    )

    const wrapper = mount(LobbyView, {
      attachTo: document.body,
    })
    expect(document.body.querySelector('.rule-modal-backdrop')).toBeNull()

    // ルール説明ボタンをクリック
    const ruleBtn = wrapper.findAll('button').find(b => b.text().includes('ルール説明'))
    expect(ruleBtn).toBeDefined()
    await ruleBtn!.trigger('click')

    const modal = document.body.querySelector('.rule-modal-backdrop')
    expect(modal).not.toBeNull()
    expect(modal?.textContent).toContain('チーム戦 (3チーム)')

    wrapper.unmount()
  })

  it('部屋を解散ボタンを押すとカスタム確認ダイアログが表示され、確定でdissolveRoomが実行される', async () => {
    const store = useGameStore()
    store.roomId = 'room-123'
    store.myPlayerId = 'p1'
    store.applyGameState(createLobbyState())
    store.dissolveRoom = vi.fn().mockResolvedValue(undefined)

    const modalWrapper = mount(ConfirmModal, { attachTo: document.body })
    const hostWrapper = mount(LobbyView, { attachTo: document.body })

    const dissolveButton = hostWrapper.findAll('button').find(b => b.text().includes('部屋を解散'))
    expect(dissolveButton).toBeDefined()
    await dissolveButton!.trigger('click')
    await modalWrapper.vm.$nextTick()

    expect(document.body.querySelector('.confirm-modal-backdrop')).not.toBeNull()
    expect(document.body.querySelector('.confirm-modal-title')?.textContent).toBe('部屋の解散')
    expect(document.body.querySelector('.confirm-modal-message')?.textContent).toContain('部屋を解散しますか？')

    const confirmBtn = document.body.querySelector('.modal-confirm-button') as HTMLButtonElement
    confirmBtn.click()

    await hostWrapper.vm.$nextTick()
    expect(store.dissolveRoom).toHaveBeenCalled()

    modalWrapper.unmount()
    hostWrapper.unmount()
  })

  it('親の変更ボタンを押すとカスタム確認ダイアログが表示され、確定でchangeHostが実行される', async () => {
    const store = useGameStore()
    store.roomId = 'room-123'
    store.myPlayerId = 'p1'
    store.applyGameState(createLobbyState())
    store.changeHost = vi.fn().mockResolvedValue(undefined)

    const modalWrapper = mount(ConfirmModal, { attachTo: document.body })
    const hostWrapper = mount(LobbyView, { attachTo: document.body })

    const changeHostBtn = hostWrapper.findAll('button').find(b => b.text().includes('親にする'))
    expect(changeHostBtn).toBeDefined()
    await changeHostBtn!.trigger('click')
    await modalWrapper.vm.$nextTick()

    expect(document.body.querySelector('.confirm-modal-backdrop')).not.toBeNull()
    expect(document.body.querySelector('.confirm-modal-title')?.textContent).toBe('親（ホスト）の変更')
    expect(document.body.querySelector('.confirm-modal-message')?.textContent).toContain('ゲスト さんを親（ホスト）に変更しますか？')

    const confirmBtn = document.body.querySelector('.modal-confirm-button') as HTMLButtonElement
    confirmBtn.click()

    await hostWrapper.vm.$nextTick()
    expect(store.changeHost).toHaveBeenCalledWith('p2')

    modalWrapper.unmount()
    hostWrapper.unmount()
  })

  it('強制退出ボタンを押すとカスタム確認ダイアログが表示され、確定でkickPlayerが実行される', async () => {
    const store = useGameStore()
    store.roomId = 'room-123'
    store.myPlayerId = 'p1'
    store.applyGameState(createLobbyState())
    store.kickPlayer = vi.fn().mockResolvedValue(undefined)

    const modalWrapper = mount(ConfirmModal, { attachTo: document.body })
    const hostWrapper = mount(LobbyView, { attachTo: document.body })

    const kickBtn = hostWrapper.findAll('button').find(b => b.text().trim() === '退出')
    expect(kickBtn).toBeDefined()
    await kickBtn!.trigger('click')
    await modalWrapper.vm.$nextTick()

    expect(document.body.querySelector('.confirm-modal-backdrop')).not.toBeNull()
    expect(document.body.querySelector('.confirm-modal-title')?.textContent).toBe('参加者の強制退出')
    expect(document.body.querySelector('.confirm-modal-message')?.textContent).toContain('ゲスト さんを強制退出させますか？')

    const confirmBtn = document.body.querySelector('.modal-confirm-button') as HTMLButtonElement
    confirmBtn.click()

    await hostWrapper.vm.$nextTick()
    expect(store.kickPlayer).toHaveBeenCalledWith('p2')

    modalWrapper.unmount()
    hostWrapper.unmount()
  })

  it('トップに戻るボタンを押すとカスタム確認ダイアログが表示され、確定でleaveAndGoToTopが実行される', async () => {
    const store = useGameStore()
    store.roomId = 'room-123'
    store.myPlayerId = 'p2'
    store.applyGameState(createLobbyState())
    store.leaveAndGoToTop = vi.fn().mockResolvedValue(undefined)

    const modalWrapper = mount(ConfirmModal, { attachTo: document.body })
    const guestWrapper = mount(LobbyView, { attachTo: document.body })

    const leaveBtn = guestWrapper.findAll('button').find(b => b.text().includes('トップに戻る'))
    expect(leaveBtn).toBeDefined()
    await leaveBtn!.trigger('click')
    await modalWrapper.vm.$nextTick()

    expect(document.body.querySelector('.confirm-modal-backdrop')).not.toBeNull()
    expect(document.body.querySelector('.confirm-modal-title')?.textContent).toBe('ロビーからの退出')
    expect(document.body.querySelector('.confirm-modal-message')?.textContent).toContain('ロビーから退出してトップ画面へ戻りますか？')

    const confirmBtn = document.body.querySelector('.modal-confirm-button') as HTMLButtonElement
    confirmBtn.click()

    await guestWrapper.vm.$nextTick()
    expect(store.leaveAndGoToTop).toHaveBeenCalled()

    modalWrapper.unmount()
    guestWrapper.unmount()
  })
})
