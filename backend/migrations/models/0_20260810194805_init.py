from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "rooms" (
    "id" VARCHAR(255) NOT NULL PRIMARY KEY,
    "password_hash" TEXT,
    "creator_token_hash" TEXT,
    "settings_json" TEXT NOT NULL,
    "phase" VARCHAR(20) NOT NULL,
    "free_char" TEXT,
    "current_player_id" VARCHAR(255),
    "current_team_id" VARCHAR(255),
    "required_start_char" TEXT,
    "round" INT NOT NULL DEFAULT 0,
    "order_index" INT NOT NULL DEFAULT 0,
    "remaining_time_ms" BIGINT NOT NULL DEFAULT 0,
    "current_turn_time_limit_ms" BIGINT NOT NULL DEFAULT 0,
    "turn_started_at" BIGINT,
    "result_json" TEXT,
    "state_json" TEXT NOT NULL,
    "created_at" BIGINT NOT NULL,
    "updated_at" BIGINT NOT NULL,
    "host_player_id" VARCHAR(255),
    "round_roster_json" TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS "players" (
    "id" VARCHAR(255) NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "status" VARCHAR(30),
    "card_json" TEXT,
    "bingo_line_ids_json" TEXT,
    "opened_cell_count" INT,
    "sort_order" INT NOT NULL DEFAULT 0,
    "team_id" VARCHAR(255),
    "connection_status" VARCHAR(30) NOT NULL DEFAULT 'connected',
    "disconnected_at" BIGINT,
    "room_id" VARCHAR(255) NOT NULL REFERENCES "rooms" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "player_sessions" (
    "id" VARCHAR(255) NOT NULL PRIMARY KEY,
    "token_hash" VARCHAR(255) NOT NULL UNIQUE,
    "active_connections" INT NOT NULL DEFAULT 0,
    "last_seen_at" BIGINT NOT NULL,
    "disconnected_at" BIGINT,
    "player_id" VARCHAR(255) NOT NULL REFERENCES "players" ("id") ON DELETE CASCADE,
    "room_id" VARCHAR(255) NOT NULL REFERENCES "rooms" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "teams" (
    "id" VARCHAR(255) NOT NULL PRIMARY KEY,
    "sort_order" INT NOT NULL DEFAULT 0,
    "status" VARCHAR(30) NOT NULL DEFAULT 'active',
    "card_json" TEXT,
    "bingo_line_ids_json" TEXT,
    "opened_cell_count" INT NOT NULL DEFAULT 0,
    "room_id" VARCHAR(255) NOT NULL REFERENCES "rooms" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "undo_snapshots" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "snapshot_json" TEXT NOT NULL,
    "restored_turn_time_limit_ms" BIGINT NOT NULL,
    "created_at" BIGINT NOT NULL,
    "room_id" VARCHAR(255) NOT NULL REFERENCES "rooms" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "word_history" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "player_id" VARCHAR(255) NOT NULL,
    "word" TEXT NOT NULL,
    "round" INT NOT NULL,
    "sequence" INT NOT NULL,
    "opened_chars_json" TEXT NOT NULL,
    "created_at" BIGINT NOT NULL,
    "room_id" VARCHAR(255) NOT NULL REFERENCES "rooms" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSON NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """


MODELS_STATE = (
    "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"
    "OdaNRDl+wviUqlZUAx0Tpze/sTz9D6/ai9I="
)
