import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import PlayingView from './PlayingView.vue'
import { useGameStore } from '../store/game'
import { createDefaultSettings } from '../types'

describe('PlayingView タイマー・時間同期', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('手番開始時刻から残り時間をリアルタイムにカウントダウンする', async () => {
    const store = useGameStore()
    const now = 1000000
    vi.setSystemTime(now)

    store.myPlayerId = 'p1'
    store.applyGameState({
      phase: 'playing',
      settings: createDefaultSettings(), // timeLimitSeconds: 30
      hostPlayerId: 'p1',
      freeChar: 'あ',
      players: [
        {
          id: 'p1',
          name: '太郎',
          teamId: null,
          status: 'active',
          connectionStatus: 'connected',
          disconnectedAt: null,
          card: { size: 3, cells: [], freeChar: 'あ' },
          bingoLineIds: [],
          openedCellCount: 1,
        },
      ],
      teams: [],
      playOrder: ['p1'],
      round: 1,
      roundRoster: ['p1'],
      orderIndex: 0,
      currentPlayerId: 'p1',
      currentTeamId: null,
      requiredStartChar: 'あ',
      usedWords: [],
      wordHistory: [],
      remainingTimeMs: 40000,
      currentTurnTimeLimitMs: 40000,
      currentTurnInputPlayerId: null,
      turnStartedAt: now,
      result: null,
      undoHistory: [],
    })

    const wrapper = mount(PlayingView)
    expect(wrapper.text()).toContain('文字数: 0文字')

    // 初期状態: 40秒
    expect(wrapper.find('.time-value').text()).toBe('40秒')

    // 5秒経過
    vi.advanceTimersByTime(5000)
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.time-value').text()).toBe('35秒')

    // 40秒経過: 0秒
    vi.advanceTimersByTime(35000)
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.time-value').text()).toBe('0秒')

    // forceSkipOnTimeout=false の場合、0秒到達時は警告スタイルが表示され、入力欄は無効化されない
    expect(wrapper.find('.timer-card').classes()).toContain('is-warning')
    expect(wrapper.find('.word-input').attributes('disabled')).toBeUndefined()
  })

  it('サーバーオフセットがある場合でも正確な残り時間を算出する', async () => {
    const store = useGameStore()
    const clientNow = 1000000
    const serverOffset = 5000 // サーバー時刻がクライアントより5秒進んでいる
    vi.setSystemTime(clientNow)

    // SSE 等で serverTimestamp: clientNow + serverOffset が渡されたと想定
    store.updateServerTimeOffset(clientNow + serverOffset)

    store.myPlayerId = 'p1'
    store.applyGameState({
      phase: 'playing',
      settings: createDefaultSettings(),
      hostPlayerId: 'p1',
      freeChar: 'あ',
      players: [
        {
          id: 'p1',
          name: '太郎',
          teamId: null,
          status: 'active',
          connectionStatus: 'connected',
          disconnectedAt: null,
          card: { size: 3, cells: [], freeChar: 'あ' },
          bingoLineIds: [],
          openedCellCount: 1,
        },
      ],
      teams: [],
      playOrder: ['p1'],
      round: 1,
      roundRoster: ['p1'],
      orderIndex: 0,
      currentPlayerId: 'p1',
      currentTeamId: null,
      requiredStartChar: 'あ',
      usedWords: [],
      wordHistory: [],
      remainingTimeMs: 30000,
      currentTurnTimeLimitMs: 30000,
      currentTurnInputPlayerId: null,
      // サーバー時刻で 10秒前に開始
      turnStartedAt: clientNow + serverOffset - 10000,
      result: null,
      undoHistory: [],
    })

    const wrapper = mount(PlayingView)

    // 30秒制限 - 10秒経過 = 20秒
    expect(wrapper.find('.time-value').text()).toBe('20秒')
  })

  it('forceSkipOnTimeout が true の場合、0秒で入力欄が無効化される', async () => {
    const store = useGameStore()
    const now = 1000000
    vi.setSystemTime(now)

    const settings = createDefaultSettings()
    settings.forceSkipOnTimeout = true

    store.myPlayerId = 'p1'
    store.applyGameState({
      phase: 'playing',
      settings,
      hostPlayerId: 'p1',
      freeChar: 'あ',
      players: [
        {
          id: 'p1',
          name: '太郎',
          teamId: null,
          status: 'active',
          connectionStatus: 'connected',
          disconnectedAt: null,
          card: { size: 3, cells: [], freeChar: 'あ' },
          bingoLineIds: [],
          openedCellCount: 1,
        },
      ],
      teams: [],
      playOrder: ['p1'],
      round: 1,
      roundRoster: ['p1'],
      orderIndex: 0,
      currentPlayerId: 'p1',
      currentTeamId: null,
      requiredStartChar: 'あ',
      usedWords: [],
      wordHistory: [],
      remainingTimeMs: 30000,
      currentTurnTimeLimitMs: 30000,
      currentTurnInputPlayerId: null,
      turnStartedAt: now,
      result: null,
      undoHistory: [],
    })

    const wrapper = mount(PlayingView)

    expect(wrapper.find('.word-input').attributes('disabled')).toBeUndefined()

    // 30秒経過
    vi.advanceTimersByTime(30000)
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.time-value').text()).toBe('0秒')
    expect(wrapper.find('.timer-card').classes()).toContain('is-expired')
    expect(wrapper.find('.timer-status').text()).toBe('時間切れ')
    expect(wrapper.find('.word-input').attributes('disabled')).toBeDefined()
  })

  it('inputWordCheck: true（デフォルト）のとき、無効な単語（接続不一致）は送信できずエラーが表示される', async () => {
    const store = useGameStore()
    store.myPlayerId = 'p1'
    const settings = createDefaultSettings()
    settings.inputWordCheck = true
    store.applyGameState({
      phase: 'playing',
      settings,
      hostPlayerId: 'p1',
      freeChar: 'あ',
      players: [
        {
          id: 'p1',
          name: '太郎',
          teamId: null,
          status: 'active',
          connectionStatus: 'connected',
          disconnectedAt: null,
          card: { size: 3, cells: [], freeChar: 'あ' },
          bingoLineIds: [],
          openedCellCount: 1,
        },
      ],
      teams: [],
      playOrder: ['p1'],
      round: 1,
      roundRoster: ['p1'],
      orderIndex: 0,
      currentPlayerId: 'p1',
      currentTeamId: null,
      requiredStartChar: 'あ',
      usedWords: [],
      wordHistory: [],
      remainingTimeMs: 30000,
      currentTurnTimeLimitMs: 30000,
      currentTurnInputPlayerId: null,
      turnStartedAt: Date.now(),
      result: null,
      undoHistory: [],
    })

    const submitSpy = vi.spyOn(store, 'submitWord').mockResolvedValue()
    const wrapper = mount(PlayingView)

    const input = wrapper.find('.word-input')
    await input.setValue('いぬ') // 'あ' から始まっていない
    await wrapper.find('.word-form').trigger('submit')

    expect(submitSpy).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('「あ」から始めてください。')
  })

  it('inputWordCheck: false のとき、接続不一致な単語でも送信でき、空文字や非ひらがなのみ送信を防止する', async () => {
    const store = useGameStore()
    store.myPlayerId = 'p1'
    const settings = createDefaultSettings()
    settings.inputWordCheck = false
    store.applyGameState({
      phase: 'playing',
      settings,
      hostPlayerId: 'p1',
      freeChar: 'あ',
      players: [
        {
          id: 'p1',
          name: '太郎',
          teamId: null,
          status: 'active',
          connectionStatus: 'connected',
          disconnectedAt: null,
          card: { size: 3, cells: [], freeChar: 'あ' },
          bingoLineIds: [],
          openedCellCount: 1,
        },
      ],
      teams: [],
      playOrder: ['p1'],
      round: 1,
      roundRoster: ['p1'],
      orderIndex: 0,
      currentPlayerId: 'p1',
      currentTeamId: null,
      requiredStartChar: 'あ',
      usedWords: [],
      wordHistory: [],
      remainingTimeMs: 30000,
      currentTurnTimeLimitMs: 30000,
      currentTurnInputPlayerId: null,
      turnStartedAt: Date.now(),
      result: null,
      undoHistory: [],
    })

    const submitSpy = vi.spyOn(store, 'submitWord').mockResolvedValue()
    const wrapper = mount(PlayingView)

    // 非ひらがな（漢字）は送信不可
    const input = wrapper.find('.word-input')
    await input.setValue('犬')
    await wrapper.find('.word-form').trigger('submit')
    expect(submitSpy).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('ひらがなと伸ばし棒で入力してください。')

    // 接続不一致のひらがな単語（'いぬ'）は送信可能
    await input.setValue('いぬ')
    await wrapper.find('.word-form').trigger('submit')
    expect(submitSpy).toHaveBeenCalledWith('いぬ')
  })

  it('ルール説明ボタンを押すとルール説明モーダルが表示される', async () => {
    const store = useGameStore()
    store.myPlayerId = 'p1'
    store.applyGameState({
      phase: 'playing',
      settings: createDefaultSettings(),
      hostPlayerId: 'p1',
      freeChar: 'あ',
      players: [
        {
          id: 'p1',
          name: '太郎',
          teamId: null,
          status: 'active',
          connectionStatus: 'connected',
          disconnectedAt: null,
          card: { size: 3, cells: [], freeChar: 'あ' },
          bingoLineIds: [],
          openedCellCount: 1,
        },
      ],
      teams: [],
      playOrder: ['p1'],
      round: 1,
      roundRoster: ['p1'],
      orderIndex: 0,
      currentPlayerId: 'p1',
      currentTeamId: null,
      requiredStartChar: 'あ',
      usedWords: [],
      wordHistory: [],
      remainingTimeMs: 30000,
      currentTurnTimeLimitMs: 30000,
      currentTurnInputPlayerId: null,
      turnStartedAt: Date.now(),
      result: null,
      undoHistory: [],
    })

    const wrapper = mount(PlayingView, {
      attachTo: document.body,
    })
    expect(document.body.querySelector('.rule-modal-backdrop')).toBeNull()

    // ルール説明ボタンをクリック
    const ruleBtn = wrapper.findAll('button').find((b) => b.text().includes('ルール説明'))
    expect(ruleBtn).toBeDefined()
    await ruleBtn!.trigger('click')

    const modal = document.body.querySelector('.rule-modal-backdrop')
    expect(modal).not.toBeNull()
    expect(modal?.textContent).toContain('ゲームルール説明')

    wrapper.unmount()
  })
})

