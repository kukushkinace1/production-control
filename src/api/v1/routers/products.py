from typing import Annotated

from fastapi import APIRouter, Depends, status

from src.api.v1.schemas.product import ProductCreateRequest, ProductResponse
from src.core.dependencies import get_product_service
from src.domain.services import ProductService

router = APIRouter(prefix="/products", tags=["products"])
ProductServiceDep = Annotated[ProductService, Depends(get_product_service)]


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreateRequest,
    service: ProductServiceDep,
) -> ProductResponse:
    product = await service.create_product(payload)
    return ProductResponse.model_validate(product)
