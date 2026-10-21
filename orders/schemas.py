from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class OrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: int = Field(gt=0, strict=True)
    quantity: int = Field(ge=1, le=99, strict=True)


class OrderResponse(BaseModel):
    id: int
    product_id: int
    shop_id: int
    product_name: str
    unit_price: Decimal
    quantity: int
    total_amount: Decimal
    status: Literal["pending", "cancelled", "paid", "expired"]
    created_at: datetime
    expires_at: datetime


class OrderPageResponse(BaseModel):
    total: int
    total_pages: int
    page: int
    page_size: int
    items: list[OrderResponse]
