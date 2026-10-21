from fastapi import APIRouter, Depends, HTTPException, Path, Query

from product import service
from product.schemas import ProductCreate, ProductPageResponse, ProductResponse, ProductStatusUpdate, ProductUpdate
from user.dependencies import get_current_user


router = APIRouter(tags=["套餐商品"])


def _run(operation, *args):
    try:
        return operation(*args)
    except service.ProductNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except service.ProductForbiddenError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error


@router.post("/shops/{shop_id}/products", response_model=ProductResponse, status_code=201)
def create_product(
    data: ProductCreate,
    shop_id: int = Path(..., gt=0),
    current_user: dict = Depends(get_current_user),
):
    return _run(service.create_product, shop_id, data, current_user["id"])


@router.get("/shops/{shop_id}/products", response_model=ProductPageResponse)
def list_products(
    shop_id: int = Path(..., gt=0),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    return _run(service.list_products, shop_id, page, page_size)


@router.get("/products/{product_id}", response_model=ProductResponse)
def get_product(product_id: int = Path(..., gt=0)):
    return _run(service.get_product, product_id)


@router.put("/products/{product_id}", response_model=ProductResponse)
def update_product(
    data: ProductUpdate,
    product_id: int = Path(..., gt=0),
    current_user: dict = Depends(get_current_user),
):
    return _run(service.update_product, product_id, data, current_user["id"])


@router.patch("/products/{product_id}/status", response_model=ProductResponse)
def change_product_status(
    data: ProductStatusUpdate,
    product_id: int = Path(..., gt=0),
    current_user: dict = Depends(get_current_user),
):
    return _run(service.change_product_status, product_id, data.status, current_user["id"])
