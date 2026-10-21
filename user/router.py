from fastapi import APIRouter,HTTPException,Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from user.dependencies import get_current_user, bearer_scheme
from user.schemas import UserResponse
from user.service import send_login_code
from user.schemas import SendCodeRequest
from user.schemas import LoginRequest, LoginResponse
from user.service import (
    InvalidCodeError,
    UserDisabledError,
    login as login_service,
    logout as logout_service,
)

router = APIRouter(
  prefix="/user",
  tags=["用户"],
)

@router.post("/code")
def send_code(request: SendCodeRequest):
  allowed=send_login_code(request.phone)
  if not allowed:
    raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
  return {"message": "验证码发送成功，请注意查收"}


@router.post("/login", response_model=LoginResponse)
def login(data: LoginRequest):
    try:
        result = login_service(
            phone=data.phone,
            code=data.code,
        )
    except InvalidCodeError:
        raise HTTPException(
            status_code=400,
            detail="验证码错误或已失效",
        )
    except UserDisabledError:
        raise HTTPException(
            status_code=403,
            detail="账号已禁用",
        )

    return LoginResponse(**result)


@router.get("/me", response_model=UserResponse)
def get_me(
    current_user: dict = Depends(get_current_user),
):
    return UserResponse(
        id=current_user["id"],
        nickname=current_user["nickname"],
    )


@router.post("/logout",status_code=204)
def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(
       bearer_scheme,
    ),
  ):
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="请先登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    logout_service(credentials.credentials)
