from __future__ import annotations

import asyncio
import json
import time

from app.models import GameState

# ルームID -> Queue のセット
_rooms: dict[str, set[asyncio.Queue[dict]]] = {}


def _ensure_room(room_id: str) -> set[asyncio.Queue[dict]]:
    if room_id not in _rooms:
        _rooms[room_id] = set()
    return _rooms[room_id]


def subscribe(room_id: str) -> asyncio.Queue[dict]:
    """SSE用のQueueを登録する。"""
    queue: asyncio.Queue[dict] = asyncio.Queue()
    _ensure_room(room_id).add(queue)
    return queue


def unsubscribe(room_id: str, queue: asyncio.Queue[dict]) -> None:
    """SSE用のQueueを解除する。"""
    room = _rooms.get(room_id)
    if room is None:
        return
    room.discard(queue)
    if not room:
        del _rooms[room_id]


async def broadcast(
    room_id: str,
    game_state: GameState,
    notice: str | None = None,
    event: str = "update",
) -> None:
    """ルーム内の全接続クライアントへゲーム状態を配信する。"""
    room = _rooms.get(room_id)
    if room is None:
        return
    payload = {
        "event": event,
        "timestamp": int(time.time() * 1000),
        "gameState": _public_state(game_state),
    }
    if notice:
        payload["notice"] = notice
    dead: set[asyncio.Queue[dict]] = set()
    for queue in room:
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            dead.add(queue)
    for queue in dead:
        room.discard(queue)


async def broadcast_event(
    room_id: str,
    event: str,
    payload: dict,
) -> None:
    """ルーム内の全接続クライアントへ指定イベントを配信する。"""
    room = _rooms.get(room_id)
    if room is None:
        return
    data = {
        "event": event,
        "timestamp": int(time.time() * 1000),
        **payload,
    }
    dead: set[asyncio.Queue[dict]] = set()
    for queue in room:
        try:
            queue.put_nowait(data)
        except asyncio.QueueFull:
            dead.add(queue)
    for queue in dead:
        room.discard(queue)



def _public_state(state: GameState) -> dict:
    """SSE配信用に内部データを除いた公開状態を返す。"""
    data = state.model_dump(mode="json")
    # undo 履歴は内部データとして配信しない
    data.pop("undoHistory", None)
    return data


def format_sse(payload: dict) -> str:
    """dict を SSE メッセージ文字列に変換する。"""
    event = payload.get("event", "update")
    data = json.dumps(payload, ensure_ascii=False)
    return f"event: {event}\ndata: {data}\n\n"
