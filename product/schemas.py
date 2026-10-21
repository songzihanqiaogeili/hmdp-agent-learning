from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProductInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2, allow_inf_nan=False)


class ProductCreate(ProductInput):
    stock: int = Field(ge=0, le=2147483647, strict=True)


class ProductUpdate(ProductInput):
    # 库存和上下架状态不能通过这个接口覆盖。
    pass


class ProductStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal[0, 1]


class ProductResponse(BaseModel):
    id: int
    shop_id: int
    name: str
    description: str
    price: Decimal
    stock: int
    status: int
    created_at: datetime


class ProductPageResponse(BaseModel):
    total: int
    total_pages: int
    page: int
    page_size: int
    items: list[ProductResponse]
