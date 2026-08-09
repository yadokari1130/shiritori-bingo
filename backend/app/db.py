import asyncio
import sqlite3
from pathlib import Path

import aiosqlite

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "shiritori-bingo.db"

_connection: aiosqlite.Connection | None = None
_write_lock = asyncio.Lock()


async def get_db() -> aiosqlite.Connection:
    """SQLite接続を返す。シングルトンとして管理する。"""
    global _connection
    if _connection is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _connection = await aiosqlite.connect(DB_PATH)
        _connection.row_factory = aiosqlite.Row
        await _connection.execute("PRAGMA foreign_keys = ON;")
        await _connection.execute("PRAGMA journal_mode = WAL;")
    return _connection


async def close_db() -> None:
    """SQLite接続を閉じる。"""
    global _connection
    if _connection is not None:
        await _connection.close()
        _connection = None


async def _tables_exist(conn: aiosqlite.Connection) -> bool:
    """roomsテーブルが存在するか確認する。"""
    async with conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='rooms'"
    ) as cursor:
        row = await cursor.fetchone()
        return row is not None


async def _schema_is_current(conn: aiosqlite.Connection) -> bool:
    """roomsテーブルにphaseカラムが存在するか確認する。"""
    try:
        async with conn.execute("SELECT phase FROM rooms LIMIT 1") as cursor:
            await cursor.fetchone()
        return True
    except sqlite3.OperationalError:
        return False


async def _drop_all_tables(conn: aiosqlite.Connection) -> None:
    """開発用: 既存のすべてのテーブルを削除する。"""
    await conn.executescript(
        """
        DROP TABLE IF EXISTS undo_snapshots;
        DROP TABLE IF EXISTS word_history;
        DROP TABLE IF EXISTS player_sessions;
        DROP TABLE IF EXISTS teams;
        DROP TABLE IF EXISTS players;
        DROP TABLE IF EXISTS rooms;
        """
    )


async def init_db() -> None:
    """テーブルを作成する。スキーマが古い場合は再作成する。"""
    conn = await get_db()
    async with _write_lock:
        if await _tables_exist(conn) and not await _schema_is_current(conn):
            # 開発中のスキーマ変更に伴い、古いテーブルを再作成する。
            # 本番環境では適切なマイグレーションを行うこと。
            await _drop_all_tables(conn)
        await conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS rooms (
                id TEXT PRIMARY KEY,
                password_hash TEXT,
                settings_json TEXT NOT NULL,
                phase TEXT NOT NULL,
                free_char TEXT,
                current_player_id TEXT,
                current_team_id TEXT,
                required_start_char TEXT,
                round INTEGER NOT NULL DEFAULT 0,
                order_index INTEGER NOT NULL DEFAULT 0,
                remaining_time_ms INTEGER NOT NULL DEFAULT 0,
                current_turn_time_limit_ms INTEGER NOT NULL DEFAULT 0,
                turn_started_at INTEGER,
                result_json TEXT,
                state_json TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                host_player_id TEXT,
                round_roster_json TEXT NOT NULL DEFAULT '[]'
            );

            CREATE TABLE IF NOT EXISTS players (
                id TEXT PRIMARY KEY,
                room_id TEXT NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                status TEXT,
                card_json TEXT,
                bingo_line_ids_json TEXT,
                opened_cell_count INTEGER,
                sort_order INTEGER NOT NULL DEFAULT 0,
                team_id TEXT,
                connection_status TEXT NOT NULL DEFAULT 'connected',
                disconnected_at INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_players_room ON players(room_id);

            CREATE TABLE IF NOT EXISTS teams (
                id TEXT PRIMARY KEY,
                room_id TEXT NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
                sort_order INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'active',
                card_json TEXT,
                bingo_line_ids_json TEXT,
                opened_cell_count INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_teams_room ON teams(room_id);

            CREATE TABLE IF NOT EXISTS player_sessions (
                id TEXT PRIMARY KEY,
                room_id TEXT NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
                player_id TEXT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
                token_hash TEXT NOT NULL UNIQUE,
                active_connections INTEGER NOT NULL DEFAULT 0,
                last_seen_at INTEGER NOT NULL,
                disconnected_at INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_token ON player_sessions(token_hash);
            CREATE INDEX IF NOT EXISTS idx_sessions_room_player ON player_sessions(room_id, player_id);

            CREATE TABLE IF NOT EXISTS word_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id TEXT NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
                player_id TEXT NOT NULL,
                word TEXT NOT NULL,
                round INTEGER NOT NULL,
                sequence INTEGER NOT NULL,
                opened_chars_json TEXT NOT NULL,
                created_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_word_history_room ON word_history(room_id);

            CREATE TABLE IF NOT EXISTS undo_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id TEXT NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
                snapshot_json TEXT NOT NULL,
                restored_turn_time_limit_ms INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_undo_snapshots_room ON undo_snapshots(room_id);
            """
        )
        await conn.commit()
