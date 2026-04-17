from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.product import ProductCreateRequest
from src.data.models import Product
from src.data.repositories import BatchRepository, ProductRepository
from src.domain.exceptions import ConflictError, NotFoundError


class ProductService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.product_repository = ProductRepository(session)
        self.batch_repository = BatchRepository(session)

    async def create_product(self, payload: ProductCreateRequest) -> Product:
        existing_product = await self.product_repository.get_by_unique_code(payload.unique_code)
        if existing_product is not None:
            raise ConflictError(f"Product with unique code {payload.unique_code} already exists.")

        batch = await self.batch_repository.get_by_id(payload.batch_id)
        if batch is None:
            raise NotFoundError(f"Batch {payload.batch_id} not found.")

        product = Product(unique_code=payload.unique_code, batch_id=payload.batch_id)
        await self.product_repository.create(product)

        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("Product creation conflicts with existing data.") from exc

        refreshed_product = await self.product_repository.get_by_unique_code(payload.unique_code)
        if refreshed_product is None:
            raise NotFoundError(f"Product {payload.unique_code} not found after creation.")
        return refreshed_product
