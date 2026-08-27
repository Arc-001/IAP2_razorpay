import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import require_role
from app.models import Product, User
from app.repositories.catalog import SqlAlchemyCatalogRepository
from app.schemas.catalog import ProductOut
from app.schemas.merchant import ProductCreate, ProductUpdate
from app.services.tag_generation import generate_tags_for_product

router = APIRouter(prefix="/api/merchant", tags=["merchant"])


def _owned_product(repo: SqlAlchemyCatalogRepository, product_id: uuid.UUID, merchant_id: uuid.UUID) -> Product:
    product = repo.get_product(product_id)
    if product is None or product.merchant_id != merchant_id:
        # 404, not 403 — don't confirm another merchant's product even exists.
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get("/products", response_model=list[ProductOut])
def list_my_products(db: Session = Depends(get_db), current_user: User = Depends(require_role("merchant"))):
    return SqlAlchemyCatalogRepository(db).get_products(current_user.merchant_id)


@router.post("/products", response_model=ProductOut)
def create_my_product(
    request: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("merchant")),
):
    tags = generate_tags_for_product(request.name, request.description, request.category)
    return SqlAlchemyCatalogRepository(db).create_product(
        merchant_id=current_user.merchant_id,
        name=request.name,
        description=request.description,
        category=request.category,
        price=request.price,
        stock=request.stock,
        tags=tags,
    )


@router.patch("/products/{product_id}", response_model=ProductOut)
def update_my_product(
    product_id: uuid.UUID,
    request: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("merchant")),
):
    repo = SqlAlchemyCatalogRepository(db)
    product = _owned_product(repo, product_id, current_user.merchant_id)

    fields = request.model_dump(exclude_unset=True)
    if "description" in fields:
        # Description changed — re-tag using the fields as they'll be after
        # this update, not the stale pre-update values.
        name = fields.get("name", product.name)
        category = fields.get("category", product.category)
        fields["tags"] = generate_tags_for_product(name, fields["description"], category)

    return repo.update_product(product.id, **fields)


@router.delete("/products/{product_id}", status_code=204)
def delete_my_product(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("merchant")),
):
    repo = SqlAlchemyCatalogRepository(db)
    _owned_product(repo, product_id, current_user.merchant_id)
    repo.delete_product(product_id)
