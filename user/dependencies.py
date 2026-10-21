from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from redis_client import redis_client
from user.repository import find_user_by_id


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
) -> dict:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="请先登录",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    user_id = redis_client.get(
        f"hmdp:login:token:{token}"
    )

    if user_id is None:
        raise HTTPException(
            status_code=401,
            detail="登录已失效，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = find_user_by_id(int(user_id))

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="登录用户不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user["status"] != 1:
        raise HTTPException(
            status_code=403,
            detail="账号已禁用",
        )

    return user