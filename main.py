from fastapi import FastAPI
from shop.router import router as shop_router
from user.router import router as user_router
from product.router import router as product_router
from orders.router import router as orders_router
app = FastAPI(title="黑马python版")
app.include_router(shop_router)
app.include_router(user_router)
app.include_router(product_router)
app.include_router(orders_router)
@app.get("/health")
def health_check():
    return {"status": "ok"}
@app.get("/hello")
def hello():
    return {"message": "学计算机，要有耐心!"}

