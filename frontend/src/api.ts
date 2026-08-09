/**
 * HTTP API クライアント
 *
 * 仕様書 14. 通信・同期仕様 に基づく。
 */

import type {
  ActionResponse,
  ApiGameStateResponse,
  CreateRoomResponse,
  GameState,
  JoinRoomResponse,
  RoomInfoResponse,
  Settings,
} from './types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

function getHeaders(): Record<string, string> {
  return {
    'Content-Type': 'application/json',
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let message = `HTTP ${res.status}`
    try {
      const body = (await res.json()) as { message?: string; detail?: string }
      message = body.message ?? body.detail ?? message
    } catch {
      // JSON でない場合はステータスコードのみ
    }
    throw new ApiError(message, res.status)
  }
  return (await res.json()) as T
}

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
    this.name = 'ApiError'
  }
}

/** ルーム情報を確認する */
export async function fetchRoomInfo(roomId: string): Promise<RoomInfoResponse> {
  const res = await fetch(`${API_BASE_URL}/api/rooms/${roomId}`, {
    method: 'GET',
    credentials: 'include',
  })
  return handleResponse<RoomInfoResponse>(res)
}

/** ルームを作成する */
export async function createRoom(
  settings: Settings,
  password: string | null = null,
): Promise<CreateRoomResponse> {
  const res = await fetch(`${API_BASE_URL}/api/rooms`, {
    method: 'POST',
    headers: getHeaders(),
    credentials: 'include',
    body: JSON.stringify({ settings, password }),
  })
  return handleResponse<CreateRoomResponse>(res)
}

/** ルームに参加する */
export async function joinRoom(
  roomId: string,
  name: string,
  password: string | null = null,
): Promise<JoinRoomResponse> {
  const res = await fetch(`${API_BASE_URL}/api/rooms/${roomId}/join`, {
    method: 'POST',
    headers: getHeaders(),
    credentials: 'include',
    body: JSON.stringify({ password, name: name.trim() }),
  })
  return handleResponse<JoinRoomResponse>(res)
}

/** 自分の名前を変更する */
export async function updateName(roomId: string, name: string): Promise<ApiGameStateResponse> {
  const res = await fetch(`${API_BASE_URL}/api/rooms/${roomId}/name`, {
    method: 'PUT',
    headers: getHeaders(),
    credentials: 'include',
    body: JSON.stringify({ name: name.trim() }),
  })
  return handleResponse<ApiGameStateResponse>(res)
}

/** ルール設定を変更する */
export async function updateSettings(roomId: string, settings: Settings): Promise<ApiGameStateResponse> {
  const res = await fetch(`${API_BASE_URL}/api/rooms/${roomId}/settings`, {
    method: 'PUT',
    headers: getHeaders(),
    credentials: 'include',
    body: JSON.stringify({ settings }),
  })
  return handleResponse<ApiGameStateResponse>(res)
}

/** ゲームを開始する */
export async function startGame(roomId: string): Promise<ApiGameStateResponse> {
  const res = await fetch(`${API_BASE_URL}/api/rooms/${roomId}/start`, {
    method: 'POST',
    headers: getHeaders(),
    credentials: 'include',
  })
  return handleResponse<ApiGameStateResponse>(res)
}

/** 親を変更する */
export async function changeHost(roomId: string, newHostPlayerId: string): Promise<ApiGameStateResponse> {
  const res = await fetch(`${API_BASE_URL}/api/rooms/${roomId}/host`, {
    method: 'POST',
    headers: getHeaders(),
    credentials: 'include',
    body: JSON.stringify({ playerId: newHostPlayerId }),
  })
  return handleResponse<ApiGameStateResponse>(res)
}

/** 参加者を強制退出させる（親のみ） */
export async function kickPlayer(roomId: string, targetPlayerId: string): Promise<ApiGameStateResponse> {
  const res = await fetch(`${API_BASE_URL}/api/rooms/${roomId}/kick`, {
    method: 'POST',
    headers: getHeaders(),
    credentials: 'include',
    body: JSON.stringify({ playerId: targetPlayerId }),
  })
  return handleResponse<ApiGameStateResponse>(res)
}

/** チームを選択する */
export async function selectTeam(roomId: string, teamId: string | null): Promise<ApiGameStateResponse> {
  const res = await fetch(`${API_BASE_URL}/api/rooms/${roomId}/team`, {
    method: 'PUT',
    headers: getHeaders(),
    credentials: 'include',
    body: JSON.stringify({ teamId }),
  })
  return handleResponse<ApiGameStateResponse>(res)
}

/** 未所属者を均等に振り分ける */
export async function randomizeTeams(roomId: string): Promise<ApiGameStateResponse> {
  const res = await fetch(`${API_BASE_URL}/api/rooms/${roomId}/teams/randomize`, {
    method: 'POST',
    headers: getHeaders(),
    credentials: 'include',
  })
  return handleResponse<ApiGameStateResponse>(res)
}

/** 単語を確定する */
export async function submitWord(roomId: string, word: string): Promise<ActionResponse> {
  const res = await fetch(`${API_BASE_URL}/api/rooms/${roomId}/action`, {
    method: 'POST',
    headers: getHeaders(),
    credentials: 'include',
    body: JSON.stringify({ type: 'word', word: word.trim() }),
  })
  return handleResponse<ActionResponse>(res)
}

/** スキップを適用する（親のみ） */
export async function submitSkip(roomId: string, subjectId: string): Promise<ActionResponse> {
  const res = await fetch(`${API_BASE_URL}/api/rooms/${roomId}/action`, {
    method: 'POST',
    headers: getHeaders(),
    credentials: 'include',
    body: JSON.stringify({ type: 'skip', subjectId }),
  })
  return handleResponse<ActionResponse>(res)
}

/** 失格を適用する（親のみ） */
export async function submitDisqualify(roomId: string, subjectId: string): Promise<ActionResponse> {
  const res = await fetch(`${API_BASE_URL}/api/rooms/${roomId}/action`, {
    method: 'POST',
    headers: getHeaders(),
    credentials: 'include',
    body: JSON.stringify({ type: 'disqualify', subjectId }),
  })
  return handleResponse<ActionResponse>(res)
}

/** undo を実行する（親のみ） */
export async function submitUndo(roomId: string): Promise<ActionResponse> {
  const res = await fetch(`${API_BASE_URL}/api/rooms/${roomId}/action`, {
    method: 'POST',
    headers: getHeaders(),
    credentials: 'include',
    body: JSON.stringify({ type: 'undo' }),
  })
  return handleResponse<ActionResponse>(res)
}

/** ゲーム終了後にロビーへ戻す（親のみ） */
export async function returnToLobby(roomId: string): Promise<ApiGameStateResponse> {
  const res = await fetch(`${API_BASE_URL}/api/rooms/${roomId}/lobby`, {
    method: 'POST',
    headers: getHeaders(),
    credentials: 'include',
  })
  return handleResponse<ApiGameStateResponse>(res)
}

/** ロビーから退出する */
export async function leaveRoom(roomId: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/rooms/${roomId}/leave`, {
    method: 'POST',
    headers: getHeaders(),
    credentials: 'include',
  })
  if (!res.ok) {
    let message = `HTTP ${res.status}`
    try {
      const body = (await res.json()) as { message?: string; detail?: string }
      message = body.message ?? body.detail ?? message
    } catch {
      // ignore
    }
    throw new ApiError(message, res.status)
  }
}

/** 部屋を解散する（親のみ） */
export async function deleteRoom(roomId: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/rooms/${roomId}`, {
    method: 'DELETE',
    headers: getHeaders(),
    credentials: 'include',
  })
  if (!res.ok) {
    let message = `HTTP ${res.status}`
    try {
      const body = (await res.json()) as { message?: string; detail?: string }
      message = body.message ?? body.detail ?? message
    } catch {
      // ignore
    }
    throw new ApiError(message, res.status)
  }
}


/** SSE 接続 URL を取得する */
export function getSseUrl(roomId: string): string {
  return `${API_BASE_URL}/api/rooms/${roomId}/events`
}

export type { GameState }
