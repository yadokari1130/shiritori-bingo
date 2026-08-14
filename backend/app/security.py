import asyncio
import hashlib
import os
import secrets

import bcrypt

SESSION_COOKIE_NAME = "shiritori_session"


def is_cookie_secure() -> bool:
    """環境変数 COOKIE_SECURE または FRONTEND_ORIGIN から secure 属性を判定する。"""
    raw = os.environ.get("COOKIE_SECURE")
    if raw is not None:
        return raw.lower() in ("true", "1", "yes")
    # FRONTEND_ORIGIN が https で始まっている場合はデフォルトで secure=True
    frontend_origin = os.environ.get("FRONTEND_ORIGIN", "")
    return frontend_origin.startswith("https://")


def get_cookie_samesite() -> str:
    """環境変数 COOKIE_SAMESITE またはデフォルト（同一ドメイン用の lax）を返す。"""
    raw = os.environ.get("COOKIE_SAMESITE")
    if raw:
        return raw.lower()
    return "lax"


def generate_session_token() -> str:
    """再接続用の不透明なトークンを生成する。"""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """トークンのハッシュ（SHA-256）を返す。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    """bcryptでパスワードをハッシュ化する（同期版）。"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """bcryptでパスワードを検証する（同期版）。"""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


async def hash_password_async(password: str) -> str:
    """bcryptでパスワードを非同期スレッドプールでハッシュ化する。"""
    return await asyncio.to_thread(hash_password, password)


async def verify_password_async(password: str, hashed: str) -> bool:
    """bcryptでパスワードを非同期スレッドプールで検証する。"""
    return await asyncio.to_thread(verify_password, password, hashed)


def set_session_cookie(response, token: str) -> None:
    """HttpOnlyのセッションCookieを設定する。"""
    secure = is_cookie_secure()
    samesite = get_cookie_samesite()
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=secure,
        samesite=samesite,
        path="/",
    )


def clear_session_cookie(response) -> None:
    """セッションCookieを削除する。"""
    secure = is_cookie_secure()
    samesite = get_cookie_samesite()
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=secure,
        samesite=samesite,
    )


CREATOR_COOKIE_NAME = "shiritori_creator_token"


def set_creator_cookie(response, token: str) -> None:
    """部屋作成者の一時Cookieを設定する。"""
    secure = is_cookie_secure()
    samesite = get_cookie_samesite()
    response.set_cookie(
        key=CREATOR_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=secure,
        samesite=samesite,
        path="/",
    )


def clear_creator_cookie(response) -> None:
    """部屋作成者の一時Cookieを削除する。"""
    secure = is_cookie_secure()
    samesite = get_cookie_samesite()
    response.delete_cookie(
        key=CREATOR_COOKIE_NAME,
        path="/",
        secure=secure,
        samesite=samesite,
    )


