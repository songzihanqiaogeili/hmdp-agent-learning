import os
from pathlib import Path

from dotenv import load_dotenv
from redis import Redis


env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(env_path)

redis_client = Redis(
    host=os.environ["REDIS_HOST"],
    port=int(os.environ["REDIS_PORT"]),
    db=int(os.environ["REDIS_DB"]),
    decode_responses=True,
    socket_connect_timeout=3,
    socket_timeout=3,
)