import os

from slowapi import Limiter
from starlette.requests import Request

rate_limit_enabled = os.environ.get("RATE_LIMIT_ENABLED", "true").lower() in (
    "true",
    "1",
    "yes",
)


def get_client_ip(request: Request) -> str:
    """クライアントのIPアドレスを取得する。

    Cloudflare を使用する場合は CF-Connecting-IP を優先して使用する。
    """
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip().split(",")[0]

    if request.client and request.client.host:
        return request.client.host

    return "127.0.0.1"


limiter = Limiter(
    key_func=get_client_ip,
    default_limits=["300/minute"],
    enabled=rate_limit_enabled,
)
