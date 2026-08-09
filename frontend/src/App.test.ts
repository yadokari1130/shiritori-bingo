import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { createVuetify } from 'vuetify'
import { nextTick } from 'vue'
import App from './App.vue'
import { useGameStore } from './store/game'
import { createDefaultSettings } from './types'

describe('App', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  function factory() {
    const pinia = createPinia()
    const wrapper = mount(App, {
      global: {
        plugins: [createVuetify(), pinia],
        stubs: {
          VApp: { template: '<div><slot /></div>' },
          VAppBar: { template: '<header><slot /></header>' },
          VAppBarTitle: { template: '<span><slot /></span>' },
          VMain: { template: '<main><slot /></main>' },
          VSpacer: { template: '<span />' },
          VChip: { template: '<span><slot /></span>' },
          TopView: { template: '<div data-testid="top-view">トップ画面</div>' },
          LobbyView: { template: '<div data-testid="lobby-view">ロビー画面</div>' },
          PlayingView: { template: '<div data-testid="playing-view">対戦画面</div>' },
          ResultView: { template: '<div data-testid="result-view">結果画面</div>' },
        },
      },
    })
    const store = useGameStore(pinia)
    return { wrapper, store }
  }

  it('初期表示はトップ画面である', () => {
    const { wrapper } = factory()
    expect(wrapper.find('[data-testid="top-view"]').exists()).toBe(true)
  })

  it('view を lobby に変更するとロビー画面が表示される', async () => {
    const { wrapper, store } = factory()
    store.view = 'lobby'
    await nextTick()
    expect(wrapper.find('[data-testid="lobby-view"]').exists()).toBe(true)
  })

  it('playing 状態に遷移すると対戦画面が表示される', async () => {
    const { wrapper, store } = factory()
    store.gameState = {
      phase: 'playing',
      settings: createDefaultSettings(),
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
      wordHistory: [],
      remainingTimeMs: 30000,
      currentTurnTimeLimitMs: 30000,
      currentTurnInputPlayerId: null,
      turnStartedAt: null,
      result: null,
      undoHistory: [],
    }
    store.view = 'playing'
    await nextTick()
    expect(wrapper.find('[data-testid="playing-view"]').exists()).toBe(true)
  })
})
