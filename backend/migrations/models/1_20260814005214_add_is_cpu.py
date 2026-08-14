from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "players" ADD "is_cpu" INT NOT NULL DEFAULT 0;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "players" DROP COLUMN "is_cpu";"""


MODELS_STATE = (
    "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"
    "jbLce6kZiMn3IxZqoV1UDHxOnlbywv/wMZSfYR"
)
