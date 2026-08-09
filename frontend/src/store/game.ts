/**
 * Pinia ストア：ゲーム状態と通信状態を集中管理
 *
 * 仕様書 9. データモデル・状態遷移、10. UIUX・画面遷移、14. 通信・同期仕様 に基づく。
 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type { GameState, Settings, ViewPhase } from '../types'
import { createDefaultSettings } from '../types'
import * as api from '../api'
import { SseClient } from '../sse'
import type { ConnectionStatus } from '../types'

export const useGameStore = defineStore('game', () => {
  // 画面状態
  const view = ref<ViewPhase>('top')
  const roomId = ref<string | null>(null)
  const myPlayerId = ref<string | null>(null)
  const connectionStatus = ref<ConnectionStatus>('disconnected')
  const isRestoringRoom = ref(false)
  const errorMessage = ref<string | null>(null)
  const noticeMessage = ref<string | null>(null)

  // 編集中の設定（トップ画面・ロビーで使用）
  const draftSettings = ref<Settings>(createDefaultSettings())

  // サーバーから受信したゲーム状態
  const gameState = ref<GameState | null>(null)

  // SSE クライアント
  let sseClient: SseClient | null = null

  // 派生状態
  const players = computed(() => gameState.value?.players ?? [])
  const teams = computed(() => gameState.value?.teams ?? [])
  const settings = computed(() => gameState.value?.settings ?? draftSettings.value)
  const phase = computed(() => gameState.value?.phase ?? 'setup')

  const myPlayer = computed(() => {
    if (!myPlayerId.value || !gameState.value) return null
    return gameState.value.players.find((p) => p.id === myPlayerId.value) ?? null
  })

  const isHost = computed(() => {
    if (!myPlayerId.value || !gameState.value) return false
    return gameState.value.hostPlayerId === myPlayerId.value
  })

  const currentSubjectName = computed(() => {
    if (!gameState.value) return ''
    if (gameState.value.settings.mode === 'individual' && gameState.value.currentPlayerId) {
      const p = gameState.value.players.find((pl) => pl.id === gameState.value!.currentPlayerId)
      return p?.name ?? ''
    }
    if (gameState.value.settings.mode === 'team' && gameState.value.currentTeamId) {
      const idx = gameState.value.teams.findIndex((t) => t.id === gameState.value!.currentTeamId)
      return idx >= 0 ? `チーム ${idx + 1}` : ''
    }
    return ''
  })

  const canInput = computed(() => {
    if (!gameState.value || gameState.value.phase !== 'playing') return false
    if (!myPlayerId.value || !myPlayer.value) return false

    if (gameState.value.settings.mode === 'individual') {
      return gameState.value.currentPlayerId === myPlayerId.value
    }

    // チーム戦：現在チームのメンバーなら入力可能
    const teamId = gameState.value.currentTeamId
    if (!teamId) return false
    return myPlayer.value.teamId === teamId
  })

  const canUndo = computed(() => {
    if (!isHost.value || gameState.value?.phase !== 'playing') return false
    return (gameState.value.undoHistory?.length ?? 0) > 0 || (gameState.value.wordHistory?.length ?? 0) > 0
  })

  const orderedPlayers = computed(() => {
    if (!gameState.value) return []
    const order = gameState.value.playOrder
    return order
      .map((id) => gameState.value!.players.find((p) => p.id === id))
      .filter((p): p is NonNullable<typeof p> => p !== undefined)
  })

  const orderedTeams = computed(() => {
    if (!gameState.value) return []
    const order = gameState.value.playOrder
    return order
      .map((id) => gameState.value!.teams.find((t) => t.id === id))
      .filter((t): t is NonNullable<typeof t> => t !== undefined)
  })

  // サーバー時刻とのオフセット (ms): サーバー時刻 = Date.now() + serverTimeOffset
  const serverTimeOffset = ref(0)

  function updateServerTimeOffset(serverTimestamp?: number): void {
    if (typeof serverTimestamp === 'number' && !Number.isNaN(serverTimestamp)) {
      serverTimeOffset.value = serverTimestamp - Date.now()
    }
  }

  function getNowOnServer(): number {
    return Date.now() + serverTimeOffset.value
  }

  /** 表示すべき画面を GameState.phase から決定する */
  function resolveViewFromPhase(state: GameState): ViewPhase {
    switch (state.phase) {
      case 'setup':
        return 'lobby'
      case 'playing':
        return 'playing'
      case 'result':
        return 'result'
      default:
        return 'top'
    }
  }

  /** ゲーム状態を更新し、画面遷移を行う */
  function applyGameState(state: GameState, notice?: string, timestamp?: number): void {
    if (timestamp) {
      updateServerTimeOffset(timestamp)
    }

    // 参加していたプレイヤーが削除された（強制退出させられた等）場合
    if (myPlayerId.value && !state.players.some((p) => p.id === myPlayerId.value)) {
      disconnectSse()
      view.value = 'top'
      roomId.value = null
      myPlayerId.value = null
      gameState.value = null
      errorMessage.value = 'ルームから退出させられました。'
      return
    }

    gameState.value = state
    view.value = resolveViewFromPhase(state)
    if (notice) {
      noticeMessage.value = notice
      setTimeout(() => {
        if (noticeMessage.value === notice) {
          noticeMessage.value = null
        }
      }, 5000)
    }
  }

  /** SSE 接続を確立する */
  function connectSse(targetRoomId: string): void {
    sseClient?.stop()
    connectionStatus.value = 'connecting'

    sseClient = new SseClient({
      url: api.getSseUrl(targetRoomId),
      roomId: targetRoomId,
      onInitial: (state, notice, timestamp) => {
        connectionStatus.value = 'connected'
        applyGameState(state, notice, timestamp)
      },
      onUpdate: (state, notice, timestamp) => {
        connectionStatus.value = 'connected'
        applyGameState(state, notice, timestamp)
      },
      onError: (message) => {
        connectionStatus.value = 'disconnected'
        errorMessage.value = message
      },
      onDissolved: (message) => {
        goToTop()
        window.history.pushState(null, '', '/')
        noticeMessage.value = message
      },
      onPing: (timestamp) => {
        if (timestamp) updateServerTimeOffset(timestamp)
      },

      onConnectionChange: (connected) => {
        connectionStatus.value = connected ? 'connected' : 'reconnecting'
      },
    })

    sseClient.start()
  }

  /** SSE 接続を切断する */
  function disconnectSse(): void {
    sseClient?.stop()
    sseClient = null
    connectionStatus.value = 'disconnected'
  }

  /** ルームを作成する */
  async function createRoom(password: string | null = null): Promise<void> {
    errorMessage.value = null
    try {
      const res = await api.createRoom(draftSettings.value, password)
      roomId.value = res.roomId
      myPlayerId.value = null
      applyGameState(res.gameState)
      window.history.pushState(null, '', `/game/${res.roomId}`)
    } catch (err) {
      errorMessage.value = err instanceof api.ApiError ? err.message : 'ルームを作成できませんでした。'
      throw err
    }
  }

  /** ルームに参加する */
  async function joinRoom(targetRoomId: string, name: string, password: string | null = null): Promise<void> {
    errorMessage.value = null
    try {
      const res = await api.joinRoom(targetRoomId, name, password)
      roomId.value = targetRoomId
      myPlayerId.value = res.playerId
      applyGameState(res.gameState)
      connectSse(targetRoomId)
    } catch (err) {
      if (err instanceof api.ApiError && err.status === 404) {
        errorMessage.value = 'ルームが見つかりません。'
      } else if (err instanceof api.ApiError && err.status === 403) {
        errorMessage.value = 'パスワードが違います。'
      } else {
        errorMessage.value = 'ルームに参加できませんでした。'
      }
      throw err
    }
  }

  /** 名前を変更する */
  async function updateName(name: string): Promise<void> {
    const id = roomId.value
    if (!id) return
    errorMessage.value = null
    try {
      const res = await api.updateName(id, name)
      applyGameState(res.gameState)
    } catch (err) {
      errorMessage.value = err instanceof api.ApiError ? err.message : '名前を変更できませんでした。'
      throw err
    }
  }

  /** ルール設定を反映する */
  async function updateSettings(settings: Settings): Promise<void> {
    const id = roomId.value
    if (!id) return
    errorMessage.value = null
    try {
      const res = await api.updateSettings(id, settings)
      applyGameState(res.gameState)
      draftSettings.value = { ...settings }
    } catch (err) {
      errorMessage.value = err instanceof api.ApiError ? err.message : '設定を反映できませんでした。'
      throw err
    }
  }

  /** ゲームを開始する */
  async function startGame(): Promise<void> {
    const id = roomId.value
    if (!id) return
    errorMessage.value = null
    try {
      const res = await api.startGame(id)
      applyGameState(res.gameState)
    } catch (err) {
      errorMessage.value = err instanceof api.ApiError ? err.message : 'ゲームを開始できませんでした。'
      throw err
    }
  }

  /** 親を変更する */
  async function changeHost(newHostPlayerId: string): Promise<void> {
    const id = roomId.value
    if (!id) return
    errorMessage.value = null
    try {
      const res = await api.changeHost(id, newHostPlayerId)
      applyGameState(res.gameState, '親が変更されました。')
    } catch (err) {
      errorMessage.value = err instanceof api.ApiError ? err.message : '親を変更できませんでした。'
      throw err
    }
  }

  /** 参加者を強制退出させる（親のみ） */
  async function kickPlayer(targetPlayerId: string): Promise<void> {
    const id = roomId.value
    if (!id) return
    errorMessage.value = null
    try {
      const res = await api.kickPlayer(id, targetPlayerId)
      applyGameState(res.gameState)
    } catch (err) {
      errorMessage.value = err instanceof api.ApiError ? err.message : '参加者を退出させられませんでした。'
      throw err
    }
  }

  /** チームを選択する */
  async function selectTeam(teamId: string | null): Promise<void> {
    const id = roomId.value
    if (!id) return
    errorMessage.value = null
    try {
      const res = await api.selectTeam(id, teamId)
      applyGameState(res.gameState)
    } catch (err) {
      errorMessage.value = err instanceof api.ApiError ? err.message : 'チームを変更できませんでした。'
      throw err
    }
  }

  /** 未所属者を均等に振り分ける */
  async function randomizeTeams(): Promise<void> {
    const id = roomId.value
    if (!id) return
    errorMessage.value = null
    try {
      const res = await api.randomizeTeams(id)
      applyGameState(res.gameState)
    } catch (err) {
      errorMessage.value = err instanceof api.ApiError ? err.message : 'チーム分けできませんでした。'
      throw err
    }
  }

  /** 単語を確定する */
  async function submitWord(word: string): Promise<void> {
    const id = roomId.value
    if (!id) return
    errorMessage.value = null
    try {
      const res = await api.submitWord(id, word)
      applyGameState(res.gameState)
    } catch (err) {
      errorMessage.value = err instanceof api.ApiError ? err.message : '送信できませんでした。'
      throw err
    }
  }

  /** スキップを適用する（親のみ） */
  async function submitSkip(subjectId: string): Promise<void> {
    const id = roomId.value
    if (!id) return
    errorMessage.value = null
    try {
      const res = await api.submitSkip(id, subjectId)
      applyGameState(res.gameState)
    } catch (err) {
      errorMessage.value = err instanceof api.ApiError ? err.message : 'スキップできませんでした。'
      throw err
    }
  }

  /** 失格を適用する（親のみ） */
  async function submitDisqualify(subjectId: string): Promise<void> {
    const id = roomId.value
    if (!id) return
    errorMessage.value = null
    try {
      const res = await api.submitDisqualify(id, subjectId)
      applyGameState(res.gameState)
    } catch (err) {
      errorMessage.value = err instanceof api.ApiError ? err.message : '失格にできませんでした。'
      throw err
    }
  }

  /** undo を実行する（親のみ） */
  async function submitUndo(): Promise<void> {
    const id = roomId.value
    if (!id) return
    errorMessage.value = null
    try {
      const res = await api.submitUndo(id)
      applyGameState(res.gameState, '直前の操作を取り消しました。')
    } catch (err) {
      errorMessage.value = err instanceof api.ApiError ? err.message : 'undo できませんでした。'
      throw err
    }
  }

  /** ゲーム終了後にロビーへ戻す（親のみ） */
  async function returnToLobby(): Promise<void> {
    const id = roomId.value
    if (!id) return
    errorMessage.value = null
    try {
      const res = await api.returnToLobby(id)
      applyGameState(res.gameState)
    } catch (err) {
      errorMessage.value = err instanceof api.ApiError ? err.message : 'ロビーに戻れませんでした。'
      throw err
    }
  }

  /** ルーム情報を確認する */
  async function checkRoomInfo(targetRoomId: string): Promise<{ exists: boolean; hasPassword: boolean }> {
    errorMessage.value = null
    try {
      const info = await api.fetchRoomInfo(targetRoomId)
      return { exists: true, hasPassword: info.hasPassword }
    } catch (err) {
      if (err instanceof api.ApiError && err.status === 404) {
        return { exists: false, hasPassword: false }
      }
      errorMessage.value = 'ルーム情報を取得できませんでした。'
      throw err
    }
  }

  /** 再接続Cookieを使ってルームへの再接続を試行する */
  async function tryReconnect(targetRoomId: string): Promise<boolean> {
    errorMessage.value = null
    try {
      await joinRoom(targetRoomId, '')
      return true
    } catch (err) {
      if (err instanceof api.ApiError && (err.status === 400 || err.status === 403 || err.status === 404)) {
        clearError()
        return false
      }
      throw err
    }
  }


  /** 専用URLを開いたとき、再接続Cookieで参加者を復元する */
  async function restoreRoomFromUrl(): Promise<boolean> {
    const parts = window.location.pathname.split('/').filter(Boolean)
    if (parts.length !== 2 || parts[0] !== 'game' || !parts[1]) return false

    const targetRoomId = parts[1]
    isRestoringRoom.value = true
    try {
      return await tryReconnect(targetRoomId)
    } catch {
      return false
    } finally {
      isRestoringRoom.value = false
    }
  }

  /** トップ画面へ戻る（ローカル状態をリセット） */
  function goToTop(): void {
    disconnectSse()
    view.value = 'top'
    roomId.value = null
    myPlayerId.value = null
    gameState.value = null
    errorMessage.value = null
    noticeMessage.value = null
    draftSettings.value = createDefaultSettings()
  }

  /** ロビーから退出してトップ画面へ戻る */
  async function leaveAndGoToTop(): Promise<void> {
    const id = roomId.value
    if (id && myPlayer.value) {
      try {
        await api.leaveRoom(id)
      } catch {
        // 退出APIエラー時もトップ画面への離脱は優先
      }
    }
    goToTop()
    window.history.pushState(null, '', '/')
  }

  /** 部屋を解散してトップ画面へ戻る（親のみ） */
  async function dissolveRoom(): Promise<void> {
    const id = roomId.value
    if (!id) return
    errorMessage.value = null
    try {
      await api.deleteRoom(id)
      goToTop()
      window.history.pushState(null, '', '/')
      noticeMessage.value = '部屋を解散しました。'
    } catch (err) {
      errorMessage.value = err instanceof api.ApiError ? err.message : '部屋を解散できませんでした。'
      throw err
    }
  }

  function clearError(): void {
    errorMessage.value = null
  }

  function clearNotice(): void {
    noticeMessage.value = null
  }

  return {
    // state
    view,
    roomId,
    myPlayerId,
    isHost,
    connectionStatus,
    isRestoringRoom,
    errorMessage,
    noticeMessage,
    draftSettings,
    gameState,
    serverTimeOffset,
    // getters
    players,
    teams,
    settings,
    phase,
    myPlayer,
    currentSubjectName,
    canInput,
    canUndo,
    orderedPlayers,
    orderedTeams,
    // actions
    applyGameState,
    createRoom,
    joinRoom,
    updateName,
    updateSettings,
    startGame,
    changeHost,
    kickPlayer,
    selectTeam,
    randomizeTeams,
    submitWord,
    submitSkip,
    submitDisqualify,
    submitUndo,
    returnToLobby,
    checkRoomInfo,
    tryReconnect,
    restoreRoomFromUrl,
    goToTop,
    leaveAndGoToTop,
    dissolveRoom,
    clearError,
    clearNotice,
    connectSse,
    disconnectSse,
    getNowOnServer,
    updateServerTimeOffset,
  }

})
