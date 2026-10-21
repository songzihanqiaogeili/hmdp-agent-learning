from redis_client import redis_client


if __name__ == "__main__":
    print("连接成功：", redis_client.ping())

    redis_client.set(
        "hmdp:test",
        "hello",
        ex=30,
    )

    value = redis_client.get("hmdp:test")
    ttl = redis_client.ttl("hmdp:test")

    print("读取结果：", value)
    print("剩余有效期：", ttl)