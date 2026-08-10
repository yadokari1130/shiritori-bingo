import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { nextTick } from 'vue'
import ResultView from './ResultView.vue'
import { useGameStore } from '../store/game'
import { createDefaultSettings } from '../types'

describe('ResultView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
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
  })
})
