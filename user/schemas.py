from pydantic import BaseModel, ConfigDict, Field


class UserInput(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid"
    )
class SendCodeRequest(UserInput):
    phone:str=Field(
        pattern=r"^1[3-9]\d{9}$",
        description="手机号"
    )
class LoginRequest(SendCodeRequest):
    code:str=Field(
        pattern=r"^[0-9]{6}$",
        description="6位数字验证码"
    )

class UserResponse(BaseModel):
    id:int
    nickname:str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse

