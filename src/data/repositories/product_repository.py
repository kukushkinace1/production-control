from sqlalchemy import select

from src.data.models import Product
from src.data.repositories.base_repository import BaseRepository


class ProductRepository(BaseRepository):
    async def create(self, product: Product) -> Product:
        self.session.add(product)
        await self.session.flush()
        return product

    async def get_by_unique_code(self, unique_code: str) -> Product | None:
        stmt = select(Product).where(Product.unique_code == unique_code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_unique_codes(self, unique_codes: list[str]) -> list[Product]:
        stmt = select(Product).where(Product.unique_code.in_(unique_codes))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
