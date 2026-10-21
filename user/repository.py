from sqlalchemy import text
from database import engine

def find_user_by_phone(phone: str) -> dict | None:
    statement=text(
        """
        SELECT * FROM users WHERE phone = :phone
        """)
    with engine.connect() as connection:
        row=connection.execute(statement, {"phone": phone}).mappings().first()
        if row is None:
            return None
        return dict(row)
def insert_user(phone: str, nickname  : str) -> None:
    statement=text(
        """
        INSERT INTO users (phone, nickname) VALUES (:phone, :nickname)
        """)  
    with engine.begin() as connection:
      connection.execute(statement, {"phone": phone, "nickname": nickname})

def find_user_by_id(id: int) -> dict | None:
    statement=text(
        """
        SELECT * FROM users WHERE id = :id
        """)
    with engine.connect() as connection:
        row=connection.execute(statement, {"id": id}).mappings().first()
        if row is None:
            return None
        return dict(row)
