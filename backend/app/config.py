import os
from pathlib import Path
from typing import Any

DEFAULT_DATABASE_PATH = Path(__file__).resolve().parent.parent / "data" / "shiritori-bingo.db"


def get_tortoise_config(database_path: Path | str | None = None) -> dict[str, Any]:
    """指定したSQLiteファイルを使うTortoise設定を返す。"""
    path = Path(database_path or os.environ.get("DATABASE_PATH", DEFAULT_DATABASE_PATH))
    return {
        "connections": {"default": f"sqlite://{path}"},
        "apps": {
            "models": {
                "models": ["app.orm_models", "aerich.models"],
                "default_connection": "default",
            }
        },
    }


TORTOISE_ORM = get_tortoise_config()
