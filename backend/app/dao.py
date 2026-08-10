from __future__ import annotations

import json
import time
import uuid

import aiosqlite

from app.models import GameState, UndoSnapshot, WordEntry


def now_ms() -> int:
    """現在時刻をミリ秒で返す。"""
    return time.time_ns() // 1_000_000


def _dump(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _load(text: str):
    return json.loads(text)


def generate_uuid() -> str:
    """UUIDを返す。"""
    return uuid.uuid4().hex


async def create_room(
    conn: aiosqlite.Connection,
    room_id: str,
    password_hash: str | None,
    settings,
    creator_token_hash: str | None = None,
) -> GameState:
    """ルームと初期ゲーム状態を作成する。"""
    from app.models import GameState, Team

    state = GameState(
        phase="setup", settings=settings, hasPassword=bool(password_hash)
    )
    now = now_ms()
    await conn.execute(
        """
        INSERT INTO rooms (
            id, password_hash, creator_token_hash, settings_json, phase, free_char,
            current_player_id, current_team_id, required_start_char,
            round, order_index, remaining_time_ms, current_turn_time_limit_ms,
            turn_started_at, result_json, state_json, created_at, updated_at,
            host_player_id, round_roster_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            room_id,
            password_hash,
            creator_token_hash,
            settings.model_dump_json(),
            state.phase,
            state.freeChar,
            None,
            None,
            state.requiredStartChar,
            state.round,
            state.orderIndex,
            state.remainingTimeMs,
            state.currentTurnTimeLimitMs,
            state.turnStartedAt,
            None,
            state.model_dump_json(),
            now,
            now,
            state.hostPlayerId,
            _dump([]),
        ),
    )
    if settings.mode == "team":
        for i in range(settings.teamCount):
            team_id = generate_uuid()
            await conn.execute(
                "INSERT INTO teams (id, room_id, sort_order) VALUES (?, ?, ?)",
                (team_id, room_id, i),
            )
            state.teams.append(Team(id=team_id, sortOrder=i))
        await conn.execute(
            "UPDATE rooms SET state_json = ? WHERE id = ?",
            (state.model_dump_json(), room_id),
        )
    await conn.commit()
    return state


async def get_room(conn: aiosqlite.Connection, room_id: str) -> aiosqlite.Row | None:
    async with conn.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)) as cursor:
        return await cursor.fetchone()


async def room_exists(conn: aiosqlite.Connection, room_id: str) -> bool:
    async with conn.execute(
        "SELECT 1 FROM rooms WHERE id = ?", (room_id,)
    ) as cursor:
        return await cursor.fetchone() is not None


async def delete_room(conn: aiosqlite.Connection, room_id: str) -> None:
    await conn.execute("DELETE FROM rooms WHERE id = ?", (room_id,))
    await conn.commit()


async def list_players(
    conn: aiosqlite.Connection, room_id: str
) -> list[aiosqlite.Row]:
    async with conn.execute(
        "SELECT * FROM players WHERE room_id = ? ORDER BY sort_order",
        (room_id,),
    ) as cursor:
        return await cursor.fetchall()


async def list_teams(conn: aiosqlite.Connection, room_id: str) -> list[aiosqlite.Row]:
    async with conn.execute(
        "SELECT * FROM teams WHERE room_id = ? ORDER BY sort_order", (room_id,)
    ) as cursor:
        return await cursor.fetchall()


async def get_next_player_sort_order(
    conn: aiosqlite.Connection, room_id: str
) -> int:
    async with conn.execute(
        "SELECT MAX(sort_order) AS m FROM players WHERE room_id = ?", (room_id,)
    ) as cursor:
        row = await cursor.fetchone()
    return (row["m"] or 0) + 1


async def load_room_state(
    conn: aiosqlite.Connection, room_id: str
) -> GameState | None:
    """ルームの最新ゲーム状態を読み込む。"""
    row = await get_room(conn, room_id)
    if row is None:
        return None
    state = GameState.model_validate(_load(row["state_json"]))
    state.hasPassword = bool(row["password_hash"])
    # DB側の接続状態を反映する
    db_players = {p["id"]: p for p in await list_players(conn, room_id)}
    for player in state.players:
        dbp = db_players.get(player.id)
        if dbp:
            player.connectionStatus = dbp["connection_status"]
            player.disconnectedAt = dbp["disconnected_at"]
    # チームのメンバー一覧を再計算
    for team in state.teams:
        team.memberPlayerIds = [
            p.id for p in state.players if p.teamId == team.id
        ]
    return state


async def save_room_state(
    conn: aiosqlite.Connection, room_id: str, state: GameState
) -> None:
    """ルーム状態と所属プレイヤー・チーム行をSQLiteに保存する。"""
    now = now_ms()
    current_player_id = (
        state.currentPlayerId if state.settings.mode == "individual" else None
    )
    current_team_id = (
        state.currentTeamId if state.settings.mode == "team" else None
    )
    result_json = state.result.model_dump_json() if state.result else None
    await conn.execute(
        """
        UPDATE rooms SET
            settings_json = ?,
            phase = ?,
            free_char = ?,
            current_player_id = ?,
            current_team_id = ?,
            required_start_char = ?,
            round = ?,
            order_index = ?,
            remaining_time_ms = ?,
            current_turn_time_limit_ms = ?,
            turn_started_at = ?,
            result_json = ?,
            state_json = ?,
            updated_at = ?,
            host_player_id = ?,
            round_roster_json = ?
        WHERE id = ?
        """,
        (
            state.settings.model_dump_json(),
            state.phase,
            state.freeChar,
            current_player_id,
            current_team_id,
            state.requiredStartChar,
            state.round,
            state.orderIndex,
            state.remainingTimeMs,
            state.currentTurnTimeLimitMs,
            state.turnStartedAt,
            result_json,
            state.model_dump_json(),
            now,
            state.hostPlayerId,
            _dump(state.roundRoster),
            room_id,
        ),
    )
    for player in state.players:
        async with conn.execute(
            "SELECT 1 FROM players WHERE id = ?", (player.id,)
        ) as cursor:
            exists = await cursor.fetchone() is not None
        if exists:
            await conn.execute(
                """
                UPDATE players SET
                    room_id = ?, name = ?, status = ?, card_json = ?,
                    bingo_line_ids_json = ?, opened_cell_count = ?, sort_order = ?,
                    team_id = ?, connection_status = ?, disconnected_at = ?
                WHERE id = ?
                """,
                (
                    room_id,
                    player.name,
                    player.status,
                    player.card.model_dump_json() if player.card else None,
                    _dump(player.bingoLineIds or []),
                    player.openedCellCount,
                    player.sortOrder,
                    player.teamId,
                    player.connectionStatus,
                    player.disconnectedAt,
                    player.id,
                ),
            )
        else:
            await conn.execute(
                """
                INSERT INTO players (
                    id, room_id, name, status, card_json, bingo_line_ids_json,
                    opened_cell_count, sort_order, team_id, connection_status, disconnected_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    player.id,
                    room_id,
                    player.name,
                    player.status,
                    player.card.model_dump_json() if player.card else None,
                    _dump(player.bingoLineIds or []),
                    player.openedCellCount,
                    player.sortOrder,
                    player.teamId,
                    player.connectionStatus,
                    player.disconnectedAt,
                ),
            )
    db_player_ids = {p["id"] for p in await list_players(conn, room_id)}
    state_player_ids = {p.id for p in state.players}
    for pid in db_player_ids - state_player_ids:
        await conn.execute("DELETE FROM players WHERE id = ?", (pid,))
        await conn.execute("DELETE FROM player_sessions WHERE player_id = ?", (pid,))

    for team in state.teams:
        async with conn.execute(
            "SELECT 1 FROM teams WHERE id = ?", (team.id,)
        ) as cursor:
            exists = await cursor.fetchone() is not None
        if exists:
            await conn.execute(
                """
                UPDATE teams SET
                    room_id = ?, sort_order = ?, status = ?, card_json = ?,
                    bingo_line_ids_json = ?, opened_cell_count = ?
                WHERE id = ?
                """,
                (
                    room_id,
                    team.sortOrder,
                    team.status,
                    team.card.model_dump_json() if team.card else None,
                    _dump(team.bingoLineIds or []),
                    team.openedCellCount,
                    team.id,
                ),
            )
        else:
            await conn.execute(
                """
                INSERT INTO teams (
                    id, room_id, sort_order, status, card_json, bingo_line_ids_json,
                    opened_cell_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    team.id,
                    room_id,
                    team.sortOrder,
                    team.status,
                    team.card.model_dump_json() if team.card else None,
                    _dump(team.bingoLineIds or []),
                    team.openedCellCount,
                ),
            )
    db_team_ids = {t["id"] for t in await list_teams(conn, room_id)}
    state_team_ids = {t.id for t in state.teams}
    for tid in db_team_ids - state_team_ids:
        await conn.execute("DELETE FROM teams WHERE id = ?", (tid,))

    await conn.commit()


async def create_session(
    conn: aiosqlite.Connection,
    session_id: str,
    room_id: str,
    player_id: str,
    token_hash: str,
) -> None:
    now = now_ms()
    await conn.execute(
        """
        INSERT INTO player_sessions (
            id, room_id, player_id, token_hash, active_connections, last_seen_at, disconnected_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (session_id, room_id, player_id, token_hash, 0, now, None),
    )
    await conn.commit()


async def get_session_by_token_hash(
    conn: aiosqlite.Connection, token_hash: str
) -> aiosqlite.Row | None:
    async with conn.execute(
        "SELECT * FROM player_sessions WHERE token_hash = ?", (token_hash,)
    ) as cursor:
        return await cursor.fetchone()


async def update_session_connections(
    conn: aiosqlite.Connection,
    session_id: str,
    delta: int,
) -> int:
    """接続数を増減し、新しい接続数を返す。"""
    now = now_ms()
    async with conn.execute(
        "SELECT active_connections FROM player_sessions WHERE id = ?",
        (session_id,),
    ) as cursor:
        row = await cursor.fetchone()
    if row is None:
        return 0
    new_count = max(0, row["active_connections"] + delta)
    disconnected_at = now if new_count == 0 else None
    await conn.execute(
        """
        UPDATE player_sessions
        SET active_connections = ?, last_seen_at = ?, disconnected_at = ?
        WHERE id = ?
        """,
        (new_count, now, disconnected_at, session_id),
    )
    await conn.commit()
    return new_count


async def set_player_connection_status(
    conn: aiosqlite.Connection,
    player_id: str,
    connected: bool,
) -> None:
    now = now_ms()
    if connected:
        await conn.execute(
            "UPDATE players SET connection_status = ?, disconnected_at = ? WHERE id = ?",
            ("connected", None, player_id),
        )
    else:
        await conn.execute(
            "UPDATE players SET connection_status = ?, disconnected_at = ? WHERE id = ?",
            ("disconnected", now, player_id),
        )
    await conn.commit()


async def delete_player(conn: aiosqlite.Connection, player_id: str) -> None:
    await conn.execute("DELETE FROM players WHERE id = ?", (player_id,))
    await conn.execute("DELETE FROM player_sessions WHERE player_id = ?", (player_id,))
    await conn.commit()


async def transfer_host(
    conn: aiosqlite.Connection, room_id: str, new_host_id: str | None
) -> None:
    now = now_ms()
    await conn.execute(
        "UPDATE rooms SET host_player_id = ?, updated_at = ? WHERE id = ?",
        (new_host_id, now, room_id),
    )
    await conn.commit()


async def add_word_history(
    conn: aiosqlite.Connection, room_id: str, entry: WordEntry
) -> None:
    now = now_ms()
    await conn.execute(
        """
        INSERT INTO word_history (
            room_id, player_id, word, round, sequence, opened_chars_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            room_id,
            entry.playerId,
            entry.word,
            entry.round,
            entry.sequence,
            _dump(entry.openedChars),
            now,
        ),
    )
    await conn.commit()


async def sync_word_history(
    conn: aiosqlite.Connection, room_id: str, entries: list[WordEntry]
) -> None:
    """word_history をゲーム状態の wordHistory と一致させる。"""
    await conn.execute("DELETE FROM word_history WHERE room_id = ?", (room_id,))
    now = now_ms()
    for entry in entries:
        await conn.execute(
            """
            INSERT INTO word_history (
                room_id, player_id, word, round, sequence, opened_chars_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                room_id,
                entry.playerId,
                entry.word,
                entry.round,
                entry.sequence,
                _dump(entry.openedChars),
                now,
            ),
        )
    await conn.commit()


async def add_undo_snapshot(
    conn: aiosqlite.Connection, room_id: str, snapshot: UndoSnapshot
) -> None:
    now = now_ms()
    await conn.execute(
        """
        INSERT INTO undo_snapshots (room_id, snapshot_json, restored_turn_time_limit_ms, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            room_id,
            snapshot.gameStateBeforeAction.model_dump_json(),
            snapshot.restoredTurnTimeLimitMs,
            now,
        ),
    )
    await conn.commit()


async def pop_undo_snapshot(
    conn: aiosqlite.Connection, room_id: str
) -> UndoSnapshot | None:
    """最新の undo スナップショットを削除して返す。"""
    async with conn.execute(
        "SELECT * FROM undo_snapshots WHERE room_id = ? ORDER BY id DESC LIMIT 1",
        (room_id,),
    ) as cursor:
        row = await cursor.fetchone()
    if row is None:
        return None
    await conn.execute("DELETE FROM undo_snapshots WHERE id = ?", (row["id"],))
    await conn.commit()
    return UndoSnapshot.model_validate(
        {
            "gameStateBeforeAction": _load(row["snapshot_json"]),
            "restoredTurnTimeLimitMs": row["restored_turn_time_limit_ms"],
        }
    )


async def load_undo_snapshots(
    conn: aiosqlite.Connection, room_id: str
) -> list[UndoSnapshot]:
    async with conn.execute(
        "SELECT * FROM undo_snapshots WHERE room_id = ? ORDER BY id",
        (room_id,),
    ) as cursor:
        rows = await cursor.fetchall()
    snapshots: list[UndoSnapshot] = []
    for row in rows:
        snapshots.append(
            UndoSnapshot.model_validate(
                {
                    "gameStateBeforeAction": _load(row["snapshot_json"]),
                    "restoredTurnTimeLimitMs": row["restored_turn_time_limit_ms"],
                }
            )
        )
    return snapshots


async def delete_word_history_for_room(
    conn: aiosqlite.Connection, room_id: str
) -> None:
    await conn.execute("DELETE FROM word_history WHERE room_id = ?", (room_id,))
    await conn.commit()


async def delete_undo_snapshots_for_room(
    conn: aiosqlite.Connection, room_id: str
) -> None:
    await conn.execute("DELETE FROM undo_snapshots WHERE room_id = ?", (room_id,))
    await conn.commit()


async def list_rooms_updated_before(
    conn: aiosqlite.Connection, timestamp_ms: int
) -> list[str]:
    async with conn.execute(
        "SELECT id FROM rooms WHERE updated_at < ?", (timestamp_ms,)
    ) as cursor:
        rows = await cursor.fetchall()
    return [row["id"] for row in rows]


async def list_disconnected_players_to_remove(
    conn: aiosqlite.Connection, phase: str, before_ms: int
) -> list[tuple[str, str]]:
    """削除対象の (room_id, player_id) 一覧を返す。"""
    async with conn.execute(
        """
        SELECT p.room_id, p.id
        FROM players p
        JOIN rooms r ON p.room_id = r.id
        WHERE r.phase = ?
          AND p.connection_status = 'disconnected'
          AND p.disconnected_at < ?
        """,
        (phase, before_ms),
    ) as cursor:
        rows = await cursor.fetchall()
    return [(row["room_id"], row["id"]) for row in rows]


async def list_empty_rooms(
    conn: aiosqlite.Connection, before_ms: int
) -> list[str]:
    """プレイヤーが0人かつ before_ms より前に更新されたルームID一覧を返す。"""
    async with conn.execute(
        """
        SELECT r.id
        FROM rooms r
        LEFT JOIN players p ON r.id = p.room_id
        WHERE p.id IS NULL
          AND r.updated_at < ?
        """,
        (before_ms,),
    ) as cursor:
        rows = await cursor.fetchall()
    return [row["id"] for row in rows]
