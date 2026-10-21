import os

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, Response

from orders import service
from orders.schemas import OrderCreate, OrderPageResponse, OrderResponse
from user.dependencies import get_current_user


router = APIRouter(prefix="/orders", tags=["订单"])


def _run(operation, *args):
    try:
        return operation(*args)
    except service.OrderNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except service.OrderConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("", response_model=OrderResponse, status_code=201)
def place_order(
    data: OrderCreate,
    response: Response,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=8,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="同一次下单及其重试使用同一键；新的购买使用新键",
    ),
    current_user: dict = Depends(get_current_user),
):
    order, created = _run(service.place_order, current_user["id"], data, idempotency_key)
    response.status_code = 201 if created else 200
    return order


@router.get("", response_model=OrderPageResponse)
def list_my_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    return service.list_my_orders(current_user["id"], page, page_size)


@router.get("/{order_id}", response_model=OrderResponse)
def get_my_order(
    order_id: int = Path(..., gt=0),
    current_user: dict = Depends(get_current_user),
):
    return _run(service.get_my_order, order_id, current_user["id"])


@router.post("/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(
    order_id: int = Path(..., gt=0),
    current_user: dict = Depends(get_current_user),
):
    return _run(service.cancel_order, order_id, current_user["id"])


@router.post(
    "/{order_id}/mock-pay",
    response_model=OrderResponse,
    summary="本地模拟支付（不发生真实扣款）",
    description="仅在 ENABLE_MOCK_PAYMENT=true 时启用；真实支付必须另行实现服务端验签和金额核对。",
)
def mock_pay_order(
    order_id: int = Path(..., gt=0),
    current_user: dict = Depends(get_current_user),
):
    if os.environ.get("ENABLE_MOCK_PAYMENT", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="本地模拟支付未启用")
    return _run(service.mock_pay_order, order_id, current_user["id"])
