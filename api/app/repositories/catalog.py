import uuid
from typing import Protocol

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import Product


class CatalogRepository(Protocol):
    def get_products(self, merchant_id: uuid.UUID) -> list[Product]: ...
    def get_product(self, product_id: uuid.UUID) -> Product | None: ...
    def search(self, query: str) -> list[Product]: ...


class SqlAlchemyCatalogRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_products(self, merchant_id: uuid.UUID) -> list[Product]:
        return list(
            self.db.query(Product).filter(Product.merchant_id == merchant_id).order_by(Product.name).all()
        )

    def get_product(self, product_id: uuid.UUID) -> Product | None:
        return self.db.get(Product, product_id)

    def search(self, query: str) -> list[Product]:
        pattern = f"%{query}%"
        return list(
            self.db.query(Product)
            .filter(or_(Product.name.ilike(pattern), Product.description.ilike(pattern)))
            .order_by(Product.name)
            .all()
        )
