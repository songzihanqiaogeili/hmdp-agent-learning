from fastapi import APIRouter,HTTPException,Path,Query
from shop.schemas import ShopResponse,ShopPageResponse,ShopCreate
from shop.service import get_shop_by_id,get_shops,create_shop as create_shop_service
router = APIRouter(
  prefix="/shops",
  tags=["商铺"],
)
@router.get("/{shop_id}", response_model=ShopResponse)
def get_shop(shop_id: int = Path(..., description="商铺ID", gt=0)):
  shop = get_shop_by_id(shop_id)
  if shop is None:
    raise HTTPException(status_code=404, detail="商铺不存在")
  return ShopResponse(**shop)
@router.get("/", response_model=ShopPageResponse)
def get_shop_list(
    page: int = Query(1, description="页码", ge=1),
    page_size: int = Query(10, description="每页数量", ge=1, le=100),
    keyword: str | None = Query(None, description="搜索关键字")
):
    result = get_shops(page=page, page_size=page_size, keyword=keyword)
    return ShopPageResponse(**result)
@router.post("/", response_model=ShopResponse, status_code=201)
def create_shop(shop_data: ShopCreate):
    shop = create_shop_service(name=shop_data.name, address=shop_data.address, phone=shop_data.phone)
    return ShopResponse(**shop)

