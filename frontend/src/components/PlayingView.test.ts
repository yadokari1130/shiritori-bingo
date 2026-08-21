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
      hasPassword: false,
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
      hasPassword: false,
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
      hasPassword: false,
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
      hasPassword: false,
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
    expect(wrapper.text()).toContain('前の単語の最後の文字から始まっていません。')
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
      hasPassword: false,
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
      hasPassword: false,
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

  it('単語履歴は新しい順に表示され、番号は古いほうから1、最新が大きい数字になる', async () => {
    const store = useGameStore()
    store.myPlayerId = 'p1'
    store.applyGameState({
      phase: 'playing',
      settings: createDefaultSettings(),
      hostPlayerId: 'p1',
      hasPassword: false,
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
      round: 3,
      roundRoster: ['p1'],
      orderIndex: 0,
      currentPlayerId: 'p1',
      currentTeamId: null,
      requiredStartChar: 'ご',
      usedWords: ['りんご', 'ごりら', 'らっぱ'],
      wordHistory: [
        { word: 'りんご', playerId: 'p1', round: 1, sequence: 1, openedChars: ['り', 'ん', 'ご'] },
        { word: 'ごりら', playerId: 'p1', round: 2, sequence: 2, openedChars: ['ら'] },
        { word: 'らっぱ', playerId: 'p1', round: 3, sequence: 3, openedChars: ['ぱ'] },
      ],
      remainingTimeMs: 30000,
      currentTurnTimeLimitMs: 30000,
      currentTurnInputPlayerId: null,
      turnStartedAt: Date.now(),
      result: null,
      undoHistory: [],
    })

    const wrapper = mount(PlayingView)
    const ol = wrapper.find('ol.history-list')
    expect(ol.exists()).toBe(true)
    expect(ol.attributes('reversed')).toBeDefined()

    const items = ol.findAll('li')
    expect(items).toHaveLength(3)

    // 新しい順に並んでいること（先頭が最新の単語「らっぱ」）
    expect(items[0].find('.history-word').text()).toBe('らっぱ')
    expect(items[1].find('.history-word').text()).toBe('ごりら')
    expect(items[2].find('.history-word').text()).toBe('りんご')

    // 番号（value属性）は古いほうが1、新しいほうが大きい数字になっていること
    expect(items[0].attributes('value')).toBe('3')
    expect(items[1].attributes('value')).toBe('2')
    expect(items[2].attributes('value')).toBe('1')
  })

  it('自分の手番でなくても入力欄に入力でき、回答ボタンは無効のままプレビューが確認できる', async () => {
    const store = useGameStore()
    store.myPlayerId = 'p2' // 自分のIDはp2だが、現在の手番はp1
    store.applyGameState({
      phase: 'playing',
      settings: createDefaultSettings(),
      hostPlayerId: 'p1',
      hasPassword: false,
      freeChar: 'あ',
      players: [
        {
          id: 'p1',
          name: '太郎',
          teamId: null,
          status: 'active',
          connectionStatus: 'connected',
          disconnectedAt: null,
          card: {
            size: 3,
            freeChar: 'あ',
            cells: [
              { index: 0, row: 0, column: 0, char: 'い', isOpen: false, isFree: false },
              { index: 1, row: 0, column: 1, char: 'ぬ', isOpen: false, isFree: false },
              { index: 2, row: 0, column: 2, char: 'ね', isOpen: false, isFree: false },
              { index: 3, row: 1, column: 0, char: 'こ', isOpen: false, isFree: false },
              { index: 4, row: 1, column: 1, char: 'あ', isOpen: true, isFree: true },
              { index: 5, row: 1, column: 2, char: 'さ', isOpen: false, isFree: false },
              { index: 6, row: 2, column: 0, char: 'る', isOpen: false, isFree: false },
              { index: 7, row: 2, column: 1, char: 'き', isOpen: false, isFree: false },
              { index: 8, row: 2, column: 2, char: 'じ', isOpen: false, isFree: false },
            ],
          },
          bingoLineIds: [],
          openedCellCount: 1,
        },
        {
          id: 'p2',
          name: '次郎',
          teamId: null,
          status: 'active',
          connectionStatus: 'connected',
          disconnectedAt: null,
          card: {
            size: 3,
            freeChar: 'あ',
            cells: [
              { index: 0, row: 0, column: 0, char: 'い', isOpen: false, isFree: false },
              { index: 1, row: 0, column: 1, char: 'ぬ', isOpen: false, isFree: false },
              { index: 2, row: 0, column: 2, char: 'ね', isOpen: false, isFree: false },
              { index: 3, row: 1, column: 0, char: 'こ', isOpen: false, isFree: false },
              { index: 4, row: 1, column: 1, char: 'あ', isOpen: true, isFree: true },
              { index: 5, row: 1, column: 2, char: 'さ', isOpen: false, isFree: false },
              { index: 6, row: 2, column: 0, char: 'る', isOpen: false, isFree: false },
              { index: 7, row: 2, column: 1, char: 'き', isOpen: false, isFree: false },
              { index: 8, row: 2, column: 2, char: 'じ', isOpen: false, isFree: false },
            ],
          },
          bingoLineIds: [],
          openedCellCount: 1,
        },
      ],
      teams: [],
      playOrder: ['p1', 'p2'],
      round: 1,
      roundRoster: ['p1', 'p2'],
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

    const wrapper = mount(PlayingView)
    const input = wrapper.find('.word-input')
    const submitBtn = wrapper.find('button[type="submit"]')

    // 自分の手番でなくても入力欄は有効
    expect(input.attributes('disabled')).toBeUndefined()
    // 確定（回答）ボタンは無効
    expect(submitBtn.attributes('disabled')).toBeDefined()

    // 入力してプレビューが反映されることを確認
    await input.setValue('いぬ')
    const previewCells = wrapper.findAll('.bingo-cell.is-preview')
    // 太郎と次郎の両方のカードで「い」と「ぬ」がプレビュー表示される（計4マス）
    expect(previewCells.length).toBeGreaterThan(0)

    // 送信を試みても送信APIは呼ばれない
    const submitSpy = vi.spyOn(store, 'submitWord')
    await wrapper.find('.word-form').trigger('submit')
    expect(submitSpy).not.toHaveBeenCalled()
  })
})


