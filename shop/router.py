from fastapi import APIRouter,HTTPException,Path,Query,Depends
from shop.schemas import ShopResponse,ShopPageResponse,ShopCreate
<<<<<<< HEAD
from shop.service import get_shop_by_id,get_shops
from shop.service import create_shop as create_shop_service
from shop.service import update_shop as update_shop_service
from shop.schemas import ShopUpdate
from shop.schemas import ShopStatusUpdate
from shop.service import change_shop_status
from user.dependencies import get_current_user
=======
from shop.service import get_shop_by_id,get_shops,create_shop as create_shop_service
>>>>>>> 9d74fbab0a7fa26d958a6b99851270e3417c5ee0
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
<<<<<<< HEAD
def create_shop(shop_data: ShopCreate, current_user: dict = Depends(get_current_user)):
    shop = create_shop_service(
        name=shop_data.name,
        address=shop_data.address,
        phone=shop_data.phone,
        user_id=current_user["id"],
    )
    return ShopResponse(**shop)

@router.put("/{shop_id}", response_model=ShopResponse)
def update_shop(
    shop_data: ShopUpdate,
    shop_id: int = Path(..., description="商铺ID", gt=0),
    current_user: dict = Depends(get_current_user),
):
    try:
        shop = update_shop_service(
            shop_id=shop_id,
            name=shop_data.name,
            address=shop_data.address,
            phone=shop_data.phone,
            user_id=current_user["id"],
        )
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    if shop is None:
        raise HTTPException(status_code=404, detail="商铺不存在")
    return ShopResponse(**shop)

@router.patch("/{shop_id}/status", response_model=ShopResponse)
def update_shop_status(
    status_data: ShopStatusUpdate,
    shop_id: int = Path(..., description="商铺ID", gt=0),
    current_user: dict = Depends(get_current_user),
):
    try:
        shop = change_shop_status(
            shop_id=shop_id,
            status=status_data.status,
            user_id=current_user["id"],
        )
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    if shop is None:
        raise HTTPException(status_code=404, detail="商铺不存在")
    return ShopResponse(**shop)
=======
def create_shop(shop_data: ShopCreate):
    shop = create_shop_service(name=shop_data.name, address=shop_data.address, phone=shop_data.phone)
    return ShopResponse(**shop)

>>>>>>> 9d74fbab0a7fa26d958a6b99851270e3417c5ee0
