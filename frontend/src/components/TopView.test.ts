import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import TopView from './TopView.vue'
import * as api from '../api'

describe('TopView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    window.history.replaceState(null, '', '/game/room123')
    vi.spyOn(api, 'fetchRoomInfo').mockResolvedValue({
      phase: 'setup',
      hasPassword: false,
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
    window.history.replaceState(null, '', '/')
  })

  it('新規参加時（Cookieなし）は名前入力を表示する', async () => {
    vi.spyOn(api, 'joinRoom').mockRejectedValue(new api.ApiError('名前を入力してください', 400))

    const wrapper = mount(TopView, {
      global: {
        plugins: [createPinia()],
        config: {
          compilerOptions: {
            isCustomElement: (tag: string) => tag.startsWith('v-'),
          },
        },
      },
    })
    await nextTick()
    await vi.waitFor(() => expect(wrapper.text()).toContain('参加者名'))

    expect(wrapper.text()).toContain('参加者名')
    expect(wrapper.text()).not.toContain('ルール設定')
    expect(wrapper.text()).not.toContain('ルームを作成')
  })

  it('再接続時（Cookieあり）は名前入力をスキップする', async () => {
    const pinia = createPinia()
    vi.spyOn(api, 'joinRoom').mockResolvedValue({
      playerId: 'p1',
      isHost: true,
      gameState: {
        phase: 'setup',
        settings: {
          mode: 'individual',
          teamCount: 2,
          cardSize: 3,
          cardOptions: { dakuten: true, handakuten: true, yoon: false, sokuon: false, prolonged: false, smallA: false },
          endCondition: 'turns',
          targetTurns: 3,
          targetBingos: 3,
          timeLimitSeconds: 30,
          extraTimeSeconds: 10,
          forceSkipOnTimeout: false,
          invalidAction: 'skip',
        },
        hostPlayerId: 'p1',
        freeChar: 'あ',
        players: [
          { id: 'p1', name: '太郎', teamId: null, status: 'active', connectionStatus: 'connected', disconnectedAt: null, card: null, bingoLineIds: null, openedCellCount: null },
        ],
        teams: [],
        playOrder: ['p1'],
        round: 1,
        roundRoster: ['p1'],
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
      },
    })

    const wrapper = mount(TopView, {
      global: {
        plugins: [pinia],
        config: {
          compilerOptions: {
            isCustomElement: (tag: string) => tag.startsWith('v-'),
          },
        },
      },
    })
    await nextTick()

    // 再接続成功時は TopView 内の名前入力フォームはレンダリングされない
    expect(wrapper.find('#dedicatedJoinName').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('名前を入力してゲームに参加してください')
  })

  it('存在しないルームURLアクセス時はトップ画面に戻り「部屋が見つかりませんでした。」を表示する', async () => {
    vi.spyOn(api, 'joinRoom').mockRejectedValue(new api.ApiError('ルームが存在しません', 404))
    vi.spyOn(api, 'fetchRoomInfo').mockRejectedValue(new api.ApiError('ルームが存在しません', 404))

    const wrapper = mount(TopView, {
      global: {
        plugins: [createPinia()],
        config: {
          compilerOptions: {
            isCustomElement: (tag: string) => tag.startsWith('v-'),
          },
        },
      },
    })
    await nextTick()
    await vi.waitFor(() => expect(wrapper.text()).toContain('部屋が見つかりませんでした。'))

    expect(wrapper.text()).toContain('部屋が見つかりませんでした。')
    expect(wrapper.text()).toContain('ルームに参加')
    expect(window.location.pathname).toBe('/')
  })

  it('トップ画面でパスワードを入力してルームを作成できる', async () => {
    window.history.replaceState(null, '', '/')
    const createRoomSpy = vi.spyOn(api, 'createRoom').mockResolvedValue({
      roomId: 'room-new-123',
      url: 'http://localhost:5173/game/room-new-123',
      gameState: {
        phase: 'setup',
        settings: {
          mode: 'individual',
          teamCount: 2,
          cardSize: 3,
          cardOptions: { dakuten: true, handakuten: true, yoon: false, sokuon: false, prolonged: false, smallA: false },
          endCondition: 'turns',
          targetTurns: 3,
          targetBingos: 3,
          timeLimitSeconds: 30,
          extraTimeSeconds: 10,
          forceSkipOnTimeout: false,
          invalidAction: 'skip',
        },
        hasPassword: true,
        hostPlayerId: null,
        freeChar: '',
        players: [],
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
      },
    })

    const wrapper = mount(TopView, {
      global: {
        plugins: [createPinia()],
        config: {
          compilerOptions: {
            isCustomElement: (tag: string) => tag.startsWith('v-'),
          },
        },
      },
    })
    await nextTick()

    // パスワード入力欄が存在する
    const pwdInput = wrapper.find('#createRoomPassword')
    expect(pwdInput.exists()).toBe(true)

    // パスワードを入力
    await pwdInput.setValue('mypassword')

    // ルームを作成ボタンを押す
    const submitBtn = wrapper.find('.submit-settings-btn')
    await submitBtn.trigger('submit')

    expect(createRoomSpy).toHaveBeenCalledWith(
      expect.anything(),
      'mypassword',
    )
  })

  it('専用URLでパスワードが必要なルーム（hasPassword: true）の場合、パスワード入力欄が表示される', async () => {
    vi.spyOn(api, 'joinRoom').mockRejectedValue(new api.ApiError('名前を入力してください', 400))
    vi.spyOn(api, 'fetchRoomInfo').mockResolvedValue({
      phase: 'setup',
      hasPassword: true,
    })

    const wrapper = mount(TopView, {
      global: {
        plugins: [createPinia()],
        config: {
          compilerOptions: {
            isCustomElement: (tag: string) => tag.startsWith('v-'),
          },
        },
      },
    })
    await nextTick()
    await vi.waitFor(() => expect(wrapper.find('#dedicatedJoinPassword').exists()).toBe(true))

    expect(wrapper.find('#dedicatedJoinPassword').exists()).toBe(true)
  })
})


