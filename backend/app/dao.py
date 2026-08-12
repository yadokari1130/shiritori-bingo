from __future__ import annotations

import json
import time
import uuid

from app.models import GameState, UndoSnapshot
from app.orm_models import (
    Player,
    PlayerSession,
    Room,
    Team,
    WordHistory,
)
from app.orm_models import UndoSnapshot as UndoSnapshotRow


def now_ms() -> int:
    return time.time_ns() // 1_000_000


def _dump(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _load(text: str):
    return json.loads(text)


def generate_uuid() -> str:
    return uuid.uuid4().hex


def _room_row(room: Room) -> dict:
    return {field: getattr(room, field) for field in (
        "id", "password_hash", "creator_token_hash", "settings_json", "phase",
        "free_char", "current_player_id", "current_team_id", "required_start_char",
        "round", "order_index", "remaining_time_ms", "current_turn_time_limit_ms",
        "turn_started_at", "result_json", "state_json", "created_at", "updated_at",
        "host_player_id", "round_roster_json",
    )}


def _player_row(player: Player) -> dict:
    return {field: getattr(player, field) for field in (
        "id", "room_id", "name", "status", "card_json", "bingo_line_ids_json",
        "opened_cell_count", "sort_order", "team_id", "connection_status",
        "disconnected_at",
    )}


async def create_room(room_id, password_hash, settings, creator_token_hash=None):
    from app.models import Team as TeamState

    state = GameState(phase="setup", settings=settings, hasPassword=bool(password_hash))
    now = now_ms()
    await Room.create(
        id=room_id, password_hash=password_hash, creator_token_hash=creator_token_hash,
        settings_json=settings.model_dump_json(), phase=state.phase,
        free_char=state.freeChar, required_start_char=state.requiredStartChar,
        state_json=state.model_dump_json(), created_at=now, updated_at=now,
        host_player_id=None, round_roster_json="[]",
    )
    if settings.mode == "team":
        for i in range(settings.teamCount):
            team_id = generate_uuid()
            await Team.create(id=team_id, room_id=room_id, sort_order=i)
            state.teams.append(TeamState(id=team_id, sortOrder=i))
        room = await Room.get(id=room_id)
        room.state_json = state.model_dump_json()
        await room.save(update_fields=["state_json"])
    return state


async def get_room(room_id):
    room = await Room.get_or_none(id=room_id)
    return _room_row(room) if room else None


async def delete_room(room_id):
    await Room.filter(id=room_id).delete()


async def get_player(player_id):
    player = await Player.get_or_none(id=player_id)
    return _player_row(player) if player else None


async def list_players(room_id):
    return [_player_row(p) for p in await Player.filter(room_id=room_id).order_by("sort_order")]


async def get_next_player_sort_order(room_id):
    players = await Player.filter(room_id=room_id).order_by("-sort_order").limit(1)
    return (players[0].sort_order if players else 0) + 1


async def load_room_state(room_id):
    room = await Room.get_or_none(id=room_id)
    if room is None:
        return None
    state = GameState.model_validate(_load(room.state_json))
    state.hasPassword = bool(room.password_hash)
    db_players = {p["id"]: p for p in await list_players(room_id)}
    for player in state.players:
        dbp = db_players.get(player.id)
        if dbp:
            player.connectionStatus = dbp["connection_status"]
            player.disconnectedAt = dbp["disconnected_at"]
    for team in state.teams:
        team.memberPlayerIds = [p.id for p in state.players if p.teamId == team.id]
    return state


async def save_room_state(room_id, state):
    room = await Room.get(id=room_id)
    room.settings_json = state.settings.model_dump_json()
    room.phase = state.phase
    room.free_char = state.freeChar
    room.current_player_id = state.currentPlayerId if state.settings.mode == "individual" else None
    room.current_team_id = state.currentTeamId if state.settings.mode == "team" else None
    room.required_start_char = state.requiredStartChar
    room.round = state.round
    room.order_index = state.orderIndex
    room.remaining_time_ms = state.remainingTimeMs
    room.current_turn_time_limit_ms = state.currentTurnTimeLimitMs
    room.turn_started_at = state.turnStartedAt
    room.result_json = state.result.model_dump_json() if state.result else None
    room.state_json = state.model_dump_json()
    room.updated_at = now_ms()
    room.host_player_id = state.hostPlayerId
    room.round_roster_json = _dump(state.roundRoster)
    await room.save()

    state_ids = {p.id for p in state.players}
    for player in state.players:
        await Player.update_or_create(
            id=player.id,
            defaults={
                "room_id": room_id, "name": player.name, "status": player.status,
                "card_json": player.card.model_dump_json() if player.card else None,
                "bingo_line_ids_json": _dump(player.bingoLineIds or []),
                "opened_cell_count": player.openedCellCount, "sort_order": player.sortOrder,
                "team_id": player.teamId, "connection_status": player.connectionStatus,
                "disconnected_at": player.disconnectedAt,
            },
        )
    if state.phase != "setup":
        for player in await Player.filter(room_id=room_id).exclude(id__in=state_ids):
            await PlayerSession.filter(player_id=player.id).delete()
            await player.delete()

    state_team_ids = {t.id for t in state.teams}
    for team in state.teams:
        await Team.update_or_create(
            id=team.id,
            defaults={
                "room_id": room_id, "sort_order": team.sortOrder, "status": team.status,
                "card_json": team.card.model_dump_json() if team.card else None,
                "bingo_line_ids_json": _dump(team.bingoLineIds or []),
                "opened_cell_count": team.openedCellCount,
            },
        )
    await Team.filter(room_id=room_id).exclude(id__in=state_team_ids).delete()


async def create_session(session_id, room_id, player_id, token_hash):
    await PlayerSession.create(id=session_id, room_id=room_id, player_id=player_id,
                               token_hash=token_hash, last_seen_at=now_ms())


async def reset_connection_statuses() -> None:
    """サーバー再起動時に、前回プロセスの接続数を破棄する。"""
    now = now_ms()
    await PlayerSession.all().update(active_connections=0, disconnected_at=now, last_seen_at=now)
    await Player.all().update(connection_status="disconnected", disconnected_at=now)


def _session_row(session: PlayerSession) -> dict:
    return {"id": session.id, "room_id": session.room_id, "player_id": session.player_id,
            "token_hash": session.token_hash, "active_connections": session.active_connections,
            "last_seen_at": session.last_seen_at, "disconnected_at": session.disconnected_at}


async def get_session_by_token_hash(token_hash):
    session = await PlayerSession.get_or_none(token_hash=token_hash)
    return _session_row(session) if session else None


async def update_session_connections(session_id, delta):
    session = await PlayerSession.get_or_none(id=session_id)
    if session is None:
        return 0
    session.active_connections = max(0, session.active_connections + delta)
    session.last_seen_at = now_ms()
    session.disconnected_at = now_ms() if session.active_connections == 0 else None
    await session.save()
    return session.active_connections


async def touch_session(session_id):
    """SSE接続が生存していることを記録する。"""
    await PlayerSession.filter(id=session_id).update(last_seen_at=now_ms())


async def expire_stale_sessions(before_ms):
    """ハートビートが途絶えたSSE接続を切断済みにする。"""
    sessions = await PlayerSession.filter(
        active_connections__gt=0, last_seen_at__lt=before_ms
    )
    if not sessions:
        return []
    now = now_ms()
    result = [(session.room_id, session.player_id) for session in sessions]
    for session in sessions:
        session.active_connections = 0
        session.disconnected_at = now
        session.last_seen_at = now
        await session.save(
            update_fields=["active_connections", "disconnected_at", "last_seen_at"]
        )
        await Player.filter(id=session.player_id).update(
            connection_status="disconnected", disconnected_at=now
        )
    return result


async def set_player_connection_status(player_id, connected):
    await Player.filter(id=player_id).update(
        connection_status="connected" if connected else "disconnected",
        disconnected_at=None if connected else now_ms(),
    )


async def delete_player(player_id):
    await Player.filter(id=player_id).delete()


async def add_word_history(room_id, entry):
    await WordHistory.create(room_id=room_id, player_id=entry.playerId, word=entry.word,
                             round=entry.round, sequence=entry.sequence,
                             opened_chars_json=_dump(entry.openedChars), created_at=now_ms())


async def sync_word_history(room_id, entries):
    await WordHistory.filter(room_id=room_id).delete()
    for entry in entries:
        await add_word_history(room_id, entry)


async def add_undo_snapshot(room_id, snapshot):
    await UndoSnapshotRow.create(room_id=room_id,
                                 snapshot_json=snapshot.gameStateBeforeAction.model_dump_json(),
                                 restored_turn_time_limit_ms=snapshot.restoredTurnTimeLimitMs,
                                 created_at=now_ms())


async def pop_undo_snapshot(room_id):
    row = await UndoSnapshotRow.filter(room_id=room_id).order_by("-id").first()
    if row is None:
        return None
    await row.delete()
    return UndoSnapshot.model_validate({"gameStateBeforeAction": _load(row.snapshot_json),
                                        "restoredTurnTimeLimitMs": row.restored_turn_time_limit_ms})


async def delete_word_history_for_room(room_id):
    await WordHistory.filter(room_id=room_id).delete()


async def delete_undo_snapshots_for_room(room_id):
    await UndoSnapshotRow.filter(room_id=room_id).delete()


async def list_rooms_updated_before(timestamp_ms):
    return [r.id for r in await Room.filter(updated_at__lt=timestamp_ms)]


async def list_disconnected_players_to_remove(phase, before_ms):
    rooms = {r.id for r in await Room.filter(phase=phase)}
    return [(p.room_id, p.id) for p in await Player.filter(room_id__in=rooms,
        connection_status="disconnected", disconnected_at__lt=before_ms)]


async def list_empty_rooms(before_ms):
    rooms = await Room.filter(updated_at__lt=before_ms)
    result = []
    for room in rooms:
        if not await Player.filter(room_id=room.id).exists():
            result.append(room.id)
    return result


async def list_playing_rooms():
    return [r.id for r in await Room.filter(phase="playing")]


async def delete_teams(room_id):
    await Team.filter(room_id=room_id).delete()


async def create_team(room_id, team_id, sort_order):
    await Team.create(id=team_id, room_id=room_id, sort_order=sort_order)
