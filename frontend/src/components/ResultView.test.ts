import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import ResultView from './ResultView.vue'
import ConfirmModal from './ConfirmModal.vue'
import { useGameStore } from '../store/game'
import { createDefaultSettings } from '../types'

describe('ResultView', () => {
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
    const topButtons = wrapper.findAll('button').filter((btn) => btn.text().includes('トップに戻る'))
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
    const lobbyBtn = wrapper.findAll('button').find((btn) => btn.text().includes('ロビーに戻る（親のみ）'))
    expect(lobbyBtn).toBeDefined()

    // 非ホストに変更
    store.myPlayerId = 'guest'
    await nextTick()
    expect(store.isHost).toBe(false)
    const noLobbyBtn = wrapper.findAll('button').find((btn) => btn.text().includes('ロビーに戻る（親のみ）'))
    expect(noLobbyBtn).toBeUndefined()

    wrapper.unmount()
  })

  it('CPUプレイヤーは順位表に🤖 CPUバッジが表示され、ホストにはならない', async () => {
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
})
