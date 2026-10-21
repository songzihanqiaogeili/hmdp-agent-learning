from pydantic import BaseModel,Field,ConfigDict
from typing import Literal

class ShopResponse(BaseModel):
    id:int
    name:str
    address:str
    phone:str
    status:int=Field(default=1,description="商铺状态，1为营业中，0为打烊")

class ShopPageResponse(BaseModel):
    total:int
    total_pages: int
    page:int
    page_size:int
    items:list[ShopResponse]
class ShopInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True,extra="forbid")
    name:str=Field(min_length=1,max_length=100,description="商铺名称",)
    address:str=Field(min_length=1,max_length=200,description="商铺地址",)
    phone:str=Field(min_length=1,max_length=30,description="联系电话",)

class ShopCreate(ShopInput):
    pass
class ShopUpdate(ShopInput):
    pass

class ShopStatusUpdate(BaseModel):
    status: Literal[0, 1] = Field(..., description="商铺状态，1为营业中，0为打烊")
