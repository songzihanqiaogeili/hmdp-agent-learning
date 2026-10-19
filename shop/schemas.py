from pydantic import BaseModel,Field
class ShopResponse(BaseModel):
    id:int
    name:str
    address:str
    phone:str

class ShopPageResponse(BaseModel):
    total:int
    total_pages: int
    page:int
    page_size:int
    items:list[ShopResponse]

class ShopCreate(BaseModel):
    name:str=Field(min_length=1,max_length=100,description="商铺名称",)
    address:str=Field(min_length=1,max_length=200,description="商铺地址",)
    phone:str=Field(min_length=1,max_length=30,description="联系电话",)