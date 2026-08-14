from __future__ import annotations

import asyncio
import logging

from app import broadcast, dao, db, engine
from app.models import GameState

logger = logging.getLogger(__name__)


def remove_player_from_state(state: GameState, player_id: str) -> bool:
    """プレイヤーを状態から削除し、ホストが変わったかを返す。"""
    before_host = state.hostPlayerId
    state.players = [p for p in state.players if p.id != player_id]
    if state.hostPlayerId == player_id:
        connected = [p for p in state.players if p.connectionStatus == "connected"]
        connected.sort(key=lambda p: p.sortOrder)
        state.hostPlayerId = connected[0].id if connected else None
    # チームのメンバー一覧を再計算
    for team in state.teams:
        team.memberPlayerIds = [
            p.id for p in state.players if p.teamId == team.id
        ]
    return state.hostPlayerId != before_host


async def run_cleanup_loop() -> None:
    """古いルームと切断プレイヤーを削除するバックグラウンドタスク。"""
    while True:
        await asyncio.sleep(5)
        try:
            await _cleanup_once()
        except Exception:
            logger.warning("クリーンアップ処理でエラーが発生しました", exc_info=True)


async def _cleanup_once() -> None:
    now = dao.now_ms()

    # 切断通知を受け取れない場合に備え、ハートビートの停止した接続を切断扱いにする。
    stale_connections = await dao.expire_stale_sessions(now - 10 * 1000)
    for room_id, player_id in set(stale_connections):
        async with db._write_lock:
            state = await dao.load_room_state(room_id)
            if state is None:
                continue
            host_changed = False
            if state.phase == "setup":
                state.players = [p for p in state.players if p.id != player_id]
                for team in state.teams:
                    team.memberPlayerIds = [
                        p.id for p in state.players if p.teamId == team.id
                    ]
                if state.hostPlayerId == player_id:
                    connected = [
                        p for p in state.players if p.connectionStatus == "connected"
                    ]
                    connected.sort(key=lambda p: p.sortOrder)
                    state.hostPlayerId = connected[0].id if connected else None
                    host_changed = True
            else:
                player = next((p for p in state.players if p.id == player_id), None)
                if player is None:
                    continue
                player.connectionStatus = "disconnected"
                player.disconnectedAt = now
                if state.hostPlayerId == player_id:
                    connected = [
                        p for p in state.players if p.connectionStatus == "connected"
                    ]
                    connected.sort(key=lambda p: p.sortOrder)
                    state.hostPlayerId = connected[0].id if connected else None
                    host_changed = True
            await dao.save_room_state(room_id, state)
            await broadcast.broadcast(
                room_id,
                state,
                notice="親が変更されました。" if host_changed else None,
            )

    # 24時間経過したルームを削除
    cutoff_room = now - 24 * 60 * 60 * 1000
    old_rooms = await dao.list_rooms_updated_before(cutoff_room)
    for room_id in old_rooms:
        await dao.delete_room(room_id)
        broadcast._rooms.pop(room_id, None)

    # setup/result 状態で30分以上切断されているプレイヤーを削除
    cutoff_player = now - 30 * 60 * 1000
    for phase in ("setup", "result"):
        targets = await dao.list_disconnected_players_to_remove(
            phase, cutoff_player
        )
        for room_id, player_id in targets:
            async with db._write_lock:
                state = await dao.load_room_state(room_id)
                if state is None:
                    continue
                if state.phase != phase:
                    continue
                host_changed = remove_player_from_state(state, player_id)
                await dao.delete_player(player_id)
                if state.players:
                    await dao.save_room_state(room_id, state)
                    await broadcast.broadcast(
                        room_id,
                        state,
                        notice="親が変更されました。" if host_changed else None,
                    )
                else:
                    await dao.delete_room(room_id)
                    broadcast._rooms.pop(room_id, None)

    # 30分以上プレイヤーが0人のルームを削除
    cutoff_empty_room = now - 30 * 60 * 1000
    empty_rooms = await dao.list_empty_rooms(cutoff_empty_room)
    for room_id in empty_rooms:
        await dao.delete_room(room_id)
        broadcast._rooms.pop(room_id, None)


async def run_forced_skip_loop() -> None:
    """強制スキップ設定が有効なルームの時間切れを監視する。"""
    while True:
        await asyncio.sleep(1.0)
        try:
            await _forced_skip_once()
        except Exception:
            logger.warning("強制スキップ監視でエラーが発生しました", exc_info=True)


async def _forced_skip_once() -> None:
    now = dao.now_ms()
    from app.orm_models import Room

    # 制限時間を経過した可能性がある playing ルームのみを絞り込み
    playing_rooms = await Room.filter(phase="playing", turn_started_at__isnull=False)
    for room in playing_rooms:
        if room.turn_started_at is None:
            continue
        elapsed = now - room.turn_started_at
        if elapsed < room.current_turn_time_limit_ms:
            continue

        async with db._write_lock:
            state = await dao.load_room_state(room.id)
            if state is None or state.phase != "playing":
                continue
            if not state.settings.forceSkipOnTimeout:
                continue
            if state.turnStartedAt is None:
                continue
            current_elapsed = now - state.turnStartedAt
            if current_elapsed < state.currentTurnTimeLimitMs:
                continue
            try:
                engine.process_skip(state, now)
                await dao.save_room_state(room.id, state)
                await broadcast.broadcast(
                    room.id,
                    state,
                    notice="時間切れでスキップしました。",
                )
            except Exception:
                logger.warning("強制スキップ実行でエラーが発生しました", exc_info=True)
