from fastapi import FastAPI
from shop.router import router as shop_router
app = FastAPI(title="黑马python版")
app.include_router(shop_router)
@app.get("/health")
def health_check():
    return {"status": "ok"}
@app.get("/hello")
def hello():
    return {"message": "学计算机，要有耐心!"}

