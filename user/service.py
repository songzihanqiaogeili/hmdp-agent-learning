import secrets
from redis_client import redis_client
from user.repository import insert_user, find_user_by_phone

def send_login_code(phone: str) -> bool:
  cooldown_key = f"hmdp:login:cooldown:{phone}"

  allowed=redis_client.set(cooldown_key, "1", ex=60, nx=True)
  if not allowed:
    return False
  code=f"{secrets.randbelow(1000000):06d}"
  code_key=f"hmdp:login:code:{phone}"
  attempts_key = f"{code_key}:attempts"

  with redis_client.pipeline(transaction=True) as pipe:
    pipe.set(code_key, code, ex=300)
    pipe.delete(attempts_key)
    pipe.execute()
  return True

def get_or_create_user(phone: str) -> dict:
    user = find_user_by_phone(phone)

    if user is not None:
        return user

    nickname = f"用户{phone[-4:]}"

    try:
        insert_user(
            phone=phone,
            nickname=nickname,
        )
    except IntegrityError as error:
        if error.orig.args[0] != 1062:
            raise

    user = find_user_by_phone(phone)

    if user is None:
        raise RuntimeError("创建用户后未能查询到")

    return user


VERIFY_CODE_SCRIPT = """
local saved_code = redis.call('GET', KEYS[1])

if not saved_code then
    return 0
end

if saved_code == ARGV[1] then
    redis.call('DEL', KEYS[1], KEYS[2])
    return 1
end

local attempts = redis.call('INCR', KEYS[2])
local ttl = redis.call('PTTL', KEYS[1])

if ttl > 0 then
    redis.call('PEXPIRE', KEYS[2], ttl)
else
    redis.call('DEL', KEYS[1], KEYS[2])
    return 0
end

if attempts >= 5 then
    redis.call('DEL', KEYS[1], KEYS[2])
end

return 0
"""


def verify_login_code(phone: str, code: str) -> bool:
    code_key = f"hmdp:login:code:{phone}"
    attempts_key = f"{code_key}:attempts"

    result = redis_client.eval(
        VERIFY_CODE_SCRIPT,
        2,
        code_key,
        attempts_key,
        code,
    )

    return result == 1


TOKEN_TTL_SECONDS = 2 * 60 * 60


class InvalidCodeError(Exception):
    pass


class UserDisabledError(Exception):
    pass


def login(phone: str, code: str) -> dict:
    if not verify_login_code(phone, code):
        raise InvalidCodeError()

    user = get_or_create_user(phone)

    if user["status"] != 1:
        raise UserDisabledError()

    token = secrets.token_urlsafe(32)

    redis_client.set(
        f"hmdp:login:token:{token}",
        str(user["id"]),
        ex=TOKEN_TTL_SECONDS,
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": TOKEN_TTL_SECONDS,
        "user": {
            "id": user["id"],
            "nickname": user["nickname"],
        },
    }

def logout(token: str) -> None:
    redis_client.delete(
        f"hmdp:login:token:{token}"
    )