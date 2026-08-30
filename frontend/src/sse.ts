/**
 * Server-Sent Events クライアント
 *
 * 仕様書 14. 通信・同期仕様、11.7 通信エラー時の復旧 に基づく。
 */

import type { GameState, SsePayload } from './types'

export interface SseClientOptions {
  url: string
  roomId: string
  onInitial: (gameState: GameState, notice?: string, timestamp?: number) => void
  onUpdate: (gameState: GameState, notice?: string, timestamp?: number) => void
  onError: (message: string) => void
  onDissolved?: (message: string) => void
  onPing?: (timestamp?: number) => void
  onConnectionChange?: (connected: boolean) => void
}

export class SseClient {
  private eventSource: EventSource | null = null
  private url: string
  private options: SseClientOptions
  private reconnectDelay = 1000
  private maxReconnectDelay = 30000
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private stopped = false

  constructor(options: SseClientOptions) {
    this.url = options.url
    this.options = options
  }

  /** SSE 接続を開始する */
  start(): void {
    this.stopped = false
    this.connect()
  }

  /** SSE 接続を停止する */
  stop(): void {
    this.stopped = true
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.eventSource) {
      this.eventSource.close()
      this.eventSource = null
    }
    this.options.onConnectionChange?.(false)
  }

  private connect(): void {
    if (this.stopped)
      return

    if (this.eventSource) {
      this.eventSource.close()
      this.eventSource = null
    }

    try {
      // withCredentials で Cookie を送信する。仕様 14.2, 14.5
      const eventSource = new EventSource(this.url, { withCredentials: true })
      this.eventSource = eventSource

      eventSource.onopen = () => {
        this.reconnectDelay = 1000
        this.options.onConnectionChange?.(true)
      }

      eventSource.addEventListener('initial', (event: MessageEvent) => {
        this.handlePayload(event.data)
      })

      eventSource.addEventListener('update', (event: MessageEvent) => {
        this.handlePayload(event.data)
      })

      eventSource.addEventListener('dissolved', (event: MessageEvent) => {
        let message = '部屋が解散されました。'
        try {
          const parsed = JSON.parse(event.data) as { message?: string }
          if (parsed.message)
            message = parsed.message
        }
        catch {
          // ignore
        }
        this.stop()
        this.options.onDissolved?.(message)
      })

      eventSource.addEventListener('error', (event: MessageEvent) => {
        const message = this.parseErrorMessage(event.data)
        this.options.onError(message ?? 'サーバーでエラーが発生しました。')
      })

      eventSource.addEventListener('ping', (event: MessageEvent) => {
        let ts: number | undefined
        try {
          const parsed = JSON.parse(event.data) as { timestamp?: number }
          ts = parsed.timestamp
        }
        catch {
          // ignore
        }
        this.options.onPing?.(ts)
      })

      eventSource.onerror = () => {
        // EventSource自体の自動再接続と二重にならないよう、古い接続を閉じる。
        eventSource.close()
        if (this.eventSource === eventSource) {
          this.eventSource = null
        }
        this.options.onConnectionChange?.(false)
        this.options.onError('通信が切断されました。再接続を試みます。')
        this.scheduleReconnect()
      }
    }
    catch {
      this.options.onError('接続を開始できませんでした。')
      this.scheduleReconnect()
    }
  }

  private handlePayload(rawData: string): void {
    try {
      const payload = JSON.parse(rawData) as SsePayload
      if (payload.event === 'initial') {
        this.options.onInitial(payload.gameState, payload.notice, payload.timestamp)
      }
      else if (payload.event === 'update') {
        this.options.onUpdate(payload.gameState, payload.notice, payload.timestamp)
      }
    }
    catch {
      this.options.onError('受信したデータを解析できませんでした。')
    }
  }

  private parseErrorMessage(rawData: string): string | null {
    try {
      const parsed = JSON.parse(rawData) as { message?: string }
      return parsed.message ?? null
    }
    catch {
      return null
    }
  }

  private scheduleReconnect(): void {
    if (this.stopped)
      return
    if (this.reconnectTimer)
      return

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      this.connect()
    }, this.reconnectDelay)

    // 指数バックオフ。仕様 11.7
    this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay)
  }
}
