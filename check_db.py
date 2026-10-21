from sqlalchemy import text
from database import engine
with engine.connect() as connection:
    result = connection.execute(text("SELECT id, name, address, phone FROM shops ORDER BY id"))
    for row in result.mappings():
        print(dict(row))
        
