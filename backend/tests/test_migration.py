import pytest
import aiosqlite
from app.db import _migrate_schema, init_db


@pytest.mark.anyio
async def test_db_migration(tmp_path, monkeypatch):
    test_db = tmp_path / "test_migration.db"
    monkeypatch.setattr("app.db.DB_PATH", test_db)

    # 1. 古いスキーマ（password_hash や creator_token_hash がない rooms テーブル）を手動作成
    async with aiosqlite.connect(test_db) as conn:
        await conn.execute(
            """
            CREATE TABLE rooms (
                id TEXT PRIMARY KEY,
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
                updated_at INTEGER NOT NULL
            );
            """
        )
        await conn.commit()

    # 2. init_db を実行
    await init_db()

    # 3. カラムが追加されているか確認
    async with aiosqlite.connect(test_db) as conn:
        async with conn.execute("PRAGMA table_info(rooms)") as cursor:
            columns = {row[1] for row in await cursor.fetchall()}

    assert "password_hash" in columns
    assert "creator_token_hash" in columns
    assert "host_player_id" in columns
    assert "round_roster_json" in columns
