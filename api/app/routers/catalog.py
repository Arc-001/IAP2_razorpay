import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Merchant
from app.repositories.catalog import SqlAlchemyCatalogRepository
from app.schemas.catalog import ProductOut

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


def _default_merchant_id(db: Session) -> uuid.UUID:
    """Phase 1 is single-merchant (CLAUDE.md §11 P1.1) — fall back to the only
    seeded merchant when the caller doesn't pass one. Multi-merchant (§11 P3.3)
    will require callers to pass merchant_id explicitly instead."""
    merchant = db.query(Merchant).first()
    if merchant is None:
        raise HTTPException(status_code=404, detail="No merchant seeded")
    return merchant.id


@router.get("/products", response_model=list[ProductOut])
def list_products(merchant_id: uuid.UUID | None = None, db: Session = Depends(get_db)):
    repo = SqlAlchemyCatalogRepository(db)
    return repo.get_products(merchant_id or _default_merchant_id(db))


@router.get("/products/{product_id}", response_model=ProductOut)
def get_product(product_id: uuid.UUID, db: Session = Depends(get_db)):
    repo = SqlAlchemyCatalogRepository(db)
    product = repo.get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get("/search", response_model=list[ProductOut])
def search_products(q: str, db: Session = Depends(get_db)):
    repo = SqlAlchemyCatalogRepository(db)
    return repo.search(q)
