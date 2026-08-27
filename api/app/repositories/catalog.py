import uuid
from typing import Protocol

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import PriceHistory, Product


class CatalogRepository(Protocol):
    def get_products(self, merchant_id: uuid.UUID) -> list[Product]: ...
    def get_product(self, product_id: uuid.UUID) -> Product | None: ...
    def search(self, query: str) -> list[Product]: ...
    def create_product(self, **fields) -> Product: ...
    def update_product(self, product_id: uuid.UUID, **fields) -> Product: ...
    def delete_product(self, product_id: uuid.UUID) -> None: ...


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

    def create_product(
        self,
        *,
        merchant_id: uuid.UUID,
        name: str,
        description: str | None,
        category: str | None,
        price: int,
        stock: int | None,
        tags: list[str] | None = None,
    ) -> Product:
        """First write path this repository has ever had (CLAUDE.md §13 /
        SCRUM-44) — every product before this was inserted only by the
        standalone seed script. Also seeds price_history, same as the seed
        script does, so the price-rise re-confirmation rule works for
        merchant-created products too."""
        product = Product(
            merchant_id=merchant_id,
            name=name,
            description=description,
            category=category,
            price=price,
            stock=stock,
            tags=tags or [],
        )
        self.db.add(product)
        self.db.flush()
        self.db.add(PriceHistory(product_id=product.id, price=product.price))
        self.db.commit()
        self.db.refresh(product)
        return product

    def update_product(self, product_id: uuid.UUID, **fields) -> Product:
        product = self.db.get(Product, product_id)
        if product is None:
            raise LookupError(f"product {product_id} not found")

        new_price = fields.pop("price", None)
        for key, value in fields.items():
            setattr(product, key, value)

        if new_price is not None and new_price != product.price:
            product.price = new_price
            self.db.add(PriceHistory(product_id=product.id, price=new_price))

        self.db.commit()
        self.db.refresh(product)
        return product

    def delete_product(self, product_id: uuid.UUID) -> None:
        product = self.db.get(Product, product_id)
        if product is None:
            raise LookupError(f"product {product_id} not found")
        self.db.query(PriceHistory).filter(PriceHistory.product_id == product_id).delete()
        self.db.delete(product)
        self.db.commit()
