from user.service import verify_login_code


if __name__ == "__main__":
    phone = input("手机号：").strip()
    code = input("验证码：").strip()

    success = verify_login_code(phone, code)
    print("校验是否成功：", success)