import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { useGameStore } from '../store/game'
import { createDefaultSettings } from '../types'
import ConfirmModal from './ConfirmModal.vue'
import ResultView from './ResultView.vue'

describe('resultView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    document.body.innerHTML = ''
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  function factory() {
    const pinia = createPinia()
    const store = useGameStore(pinia)
    const settings = createDefaultSettings()
    settings.cardOptions = {
      dakuten: true,
      handakuten: true,
      smallA: true,
      yoon: true,
      sokuon: true,
      prolonged: true,
    }
    store.gameState = {
      phase: 'result',
      settings,
      hasPassword: false,
      hostPlayerId: 'host',
      freeChar: 'あ',
      players: [
        {
          id: 'player-1',
          name: 'テストプレイヤー',
          teamId: null,
          status: 'active',
          connectionStatus: 'connected',
          disconnectedAt: null,
          card: null,
          bingoLineIds: [],
          openedCellCount: 0,
        },
      ],
      teams: [],
      playOrder: [],
      round: 1,
      roundRoster: [],
      orderIndex: 0,
      currentPlayerId: null,
      currentTeamId: null,
      requiredStartChar: 'あ',
      usedWords: [],
      remainingTimeMs: 0,
      currentTurnTimeLimitMs: 30000,
      currentTurnInputPlayerId: null,
      turnStartedAt: null,
      wordHistory: [],
      undoHistory: [],
      result: {
        reason: 'turns',
        endRound: 5,
        achieverPlayerIds: ['player-1'],
        achieverTeamIds: [],
        rankings: [
          {
            rank: 1,
            subjectType: 'player',
            subjectId: 'player-1',
            bingoCount: 1,
            openedCellCount: 5,
            status: 'active',
          },
        ],
        snapshot: {
          settings,
          freeChar: 'あ',
          players: [
            {
              playerId: 'player-1',
              name: 'テストプレイヤー',
              teamId: null,
              status: 'active',
              bingoLineIds: [],
              openedCellCount: 3,
              connectionStatus: 'connected',
              card: {
                size: 3,
                freeChar: 'あ',
                cells: [
                  { index: 0, row: 0, column: 0, char: 'や', isOpen: true, isFree: false },
                  { index: 1, row: 0, column: 1, char: 'ゆ', isOpen: false, isFree: false },
                  { index: 2, row: 0, column: 2, char: 'よ', isOpen: true, isFree: false },
                ],
              },
            },
          ],
          teams: [],
          wordHistory: [],
        },
      },
    }

    const wrapper = mount(ResultView, {
      global: {
        plugins: [pinia],
      },
      attachTo: document.body,
    })
    return { wrapper, store }
  }

  it('文字開放状態表でや行の空白マスに is-blank が適用され、文字マスに is-open / is-closed が正しく適用される', async () => {
    const { wrapper } = factory()
    await nextTick()

    const yaCol = wrapper.findAll('.kana-col').find((col) => {
      return col.find('.kana-col-header').text() === 'や'
    })
    expect(yaCol).toBeDefined()

    const cells = yaCol!.findAll('.kana-cell')
    expect(cells.length).toBe(5)

    // あ段: 'や' (isOpen: true)
    expect(cells[0].text()).toBe('や')
    expect(cells[0].classes()).toContain('is-open')
    expect(cells[0].classes()).not.toContain('is-blank')

    // い段: null (空白)
    expect(cells[1].text()).toBe('')
    expect(cells[1].classes()).toContain('is-blank')

    // う段: 'ゆ' (isOpen: false)
    expect(cells[2].text()).toBe('ゆ')
    expect(cells[2].classes()).toContain('is-closed')
    expect(cells[2].classes()).not.toContain('is-blank')

    // え段: null (空白)
    expect(cells[3].text()).toBe('')
    expect(cells[3].classes()).toContain('is-blank')

    // お段: 'よ' (isOpen: true)
    expect(cells[4].text()).toBe('よ')
    expect(cells[4].classes()).toContain('is-open')
    expect(cells[4].classes()).not.toContain('is-blank')

    wrapper.unmount()
  })

  it('特殊文字（ゃゅょっー）の列で伸ばし棒などが正しく配置される', async () => {
    const { wrapper } = factory()
    await nextTick()

    const specialCol = wrapper.findAll('.kana-col').find((col) => {
      return col.find('.kana-col-header').text() === 'ゃ'
    })
    expect(specialCol).toBeDefined()

    const cells = specialCol!.findAll('.kana-cell')
    expect(cells.length).toBe(5)
    expect(cells[0].text()).toBe('ゃ')
    expect(cells[1].text()).toBe('ゅ')
    expect(cells[2].text()).toBe('ょ')
    expect(cells[3].text()).toBe('っ')
    expect(cells[4].text()).toBe('ー')

    wrapper.unmount()
  })

  it('ヘッダーおよび最下部に「トップに戻る」ボタンが表示され、確認ダイアログ確定で leaveAndGoToTop が実行される', async () => {
    const modalWrapper = mount(ConfirmModal, { attachTo: document.body })
    const { wrapper, store } = factory()
    store.myPlayerId = 'player-1'
    const leaveSpy = vi.spyOn(store, 'leaveAndGoToTop').mockResolvedValue()

    // ヘッダーとフッターにトップに戻るボタンが存在することを確認
    const topButtons = wrapper.findAll('button').filter(btn => btn.text().includes('トップに戻る'))
    expect(topButtons.length).toBe(2)

    // ヘッダーのボタンをクリック
    await topButtons[0].trigger('click')
    await modalWrapper.vm.$nextTick()

    expect(document.body.querySelector('.confirm-modal-backdrop')).not.toBeNull()
    expect(document.body.querySelector('.confirm-modal-title')?.textContent).toBe('トップ画面へ戻る')
    expect(document.body.querySelector('.confirm-modal-message')?.textContent).toContain('トップ画面へ戻りますか？')

    const confirmBtn = document.body.querySelector('.modal-confirm-button') as HTMLButtonElement
    confirmBtn.click()

    await wrapper.vm.$nextTick()
    expect(leaveSpy).toHaveBeenCalledTimes(1)

    // 最下部のアクションボタンをクリック
    await topButtons[1].trigger('click')
    await modalWrapper.vm.$nextTick()

    const confirmBtn2 = document.body.querySelector('.modal-confirm-button') as HTMLButtonElement
    confirmBtn2.click()

    await wrapper.vm.$nextTick()
    expect(leaveSpy).toHaveBeenCalledTimes(2)

    modalWrapper.unmount()
    wrapper.unmount()
  })

  it('ホスト（親）の場合は「ロビーに戻る（親のみ）」ボタンが表示され、非ホストの場合は表示されない', async () => {
    const { wrapper, store } = factory()
    store.myPlayerId = 'host'
    store.gameState!.players = [
      {
        id: 'host',
        name: 'ホストプレイヤー',
        teamId: null,
        status: 'active',
        connectionStatus: 'connected',
        disconnectedAt: null,
        card: null,
        bingoLineIds: [],
        openedCellCount: 0,
        isCpu: false,
      },
    ]
    await nextTick()

    expect(store.isHost).toBe(true)
    const lobbyBtn = wrapper.findAll('button').find(btn => btn.text().includes('ロビーに戻る（親のみ）'))
    expect(lobbyBtn).toBeDefined()

    // 非ホストに変更
    store.myPlayerId = 'guest'
    await nextTick()
    expect(store.isHost).toBe(false)
    const noLobbyBtn = wrapper.findAll('button').find(btn => btn.text().includes('ロビーに戻る（親のみ）'))
    expect(noLobbyBtn).toBeUndefined()

    wrapper.unmount()
  })

  it('cPUプレイヤーは順位表に🤖 CPUバッジが表示され、ホストにはならない', async () => {
    const { wrapper, store } = factory()
    store.gameState!.result!.snapshot.players.push({
      playerId: 'cpu-1',
      name: 'CPU 1',
      teamId: null,
      status: 'active',
      bingoLineIds: [],
      openedCellCount: 1,
      connectionStatus: 'connected',
      isCpu: true,
      card: null,
    })
    store.gameState!.result!.rankings.push({
      rank: 2,
      subjectType: 'player',
      subjectId: 'cpu-1',
      bingoCount: 0,
      openedCellCount: 1,
      status: 'active',
    })
    await nextTick()

    const cpuBadge = wrapper.find('.cpu-badge')
    expect(cpuBadge.exists()).toBe(true)
    expect(cpuBadge.text()).toContain('🤖 CPU')

    wrapper.unmount()
  })

  it('チーム戦の結果画面で順位表およびビンゴカードのチーム名が正しく表示される', async () => {
    const pinia = createPinia()
    const store = useGameStore(pinia)
    const settings = {
      ...createDefaultSettings(),
      mode: 'team' as const,
      teamCount: 2,
    }

    store.gameState = {
      phase: 'result',
      settings,
      hasPassword: false,
      hostPlayerId: 'player-1',
      freeChar: 'あ',
      players: [
        {
          id: 'player-1',
          name: '太郎',
          teamId: 'team-1',
          status: 'active',
          connectionStatus: 'connected',
          disconnectedAt: null,
          card: null,
          bingoLineIds: [],
          openedCellCount: 0,
        },
        {
          id: 'player-2',
          name: '次郎',
          teamId: 'team-2',
          status: 'active',
          connectionStatus: 'connected',
          disconnectedAt: null,
          card: null,
          bingoLineIds: [],
          openedCellCount: 0,
        },
      ],
      teams: [],
      playOrder: [],
      round: 3,
      roundRoster: [],
      orderIndex: 0,
      currentPlayerId: null,
      currentTeamId: null,
      requiredStartChar: 'あ',
      usedWords: [],
      remainingTimeMs: 0,
      currentTurnTimeLimitMs: 30000,
      currentTurnInputPlayerId: null,
      turnStartedAt: null,
      wordHistory: [],
      undoHistory: [],
      result: {
        reason: 'bingos',
        endRound: 3,
        achieverPlayerIds: [],
        achieverTeamIds: ['team-2'],
        rankings: [
          {
            rank: 1,
            subjectType: 'team',
            subjectId: 'team-2',
            bingoCount: 1,
            openedCellCount: 5,
            status: 'active',
          },
          {
            rank: 2,
            subjectType: 'team',
            subjectId: 'team-1',
            bingoCount: 0,
            openedCellCount: 3,
            status: 'active',
          },
        ],
        snapshot: {
          settings,
          freeChar: 'あ',
          players: [
            {
              playerId: 'player-1',
              name: '太郎',
              teamId: 'team-1',
              status: 'active',
              bingoLineIds: [],
              openedCellCount: 3,
              connectionStatus: 'connected',
              card: null,
            },
            {
              playerId: 'player-2',
              name: '次郎',
              teamId: 'team-2',
              status: 'active',
              bingoLineIds: [],
              openedCellCount: 5,
              connectionStatus: 'connected',
              card: null,
            },
          ],
          teams: [
            {
              teamId: 'team-1',
              memberPlayerIds: ['player-1'],
              status: 'active',
              bingoLineIds: [],
              openedCellCount: 3,
              card: {
                size: 3,
                freeChar: 'あ',
                cells: [],
              },
            },
            {
              teamId: 'team-2',
              memberPlayerIds: ['player-2'],
              status: 'active',
              bingoLineIds: ['row-0'],
              openedCellCount: 5,
              card: {
                size: 3,
                freeChar: 'あ',
                cells: [],
              },
            },
          ],
          wordHistory: [],
        },
      },
    }

    const wrapper = mount(ResultView, {
      global: {
        plugins: [pinia],
      },
      attachTo: document.body,
    })
    await nextTick()

    // 順位表の確認：1位が「チーム 2」、2位が「チーム 1」
    const rows = wrapper.findAll('.ranking-table tbody tr')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('1位')
    expect(rows[0].text()).toContain('チーム 2')
    expect(rows[1].text()).toContain('2位')
    expect(rows[1].text()).toContain('チーム 1')

    // ビンゴカードのタイトル確認
    const cards = wrapper.findAllComponents({ name: 'BingoCard' })
    expect(cards).toHaveLength(2)
    expect(cards[0].props('title')).toBe('チーム 1')
    expect(cards[1].props('title')).toBe('チーム 2')

    wrapper.unmount()
  })
})
