from datetime import datetime
from pydantic import BaseModel
from .category import CategoryRead


class ProductBase(BaseModel):
    name: str
    slug: str
    barcode: str | None = None
    brand: str | None = None
    description: str | None = None
    image_url: str | None = None
    unit: str | None = None
    unit_size: str | None = None
    category_id: int | None = None


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: str | None = None
    barcode: str | None = None
    brand: str | None = None
    description: str | None = None
    image_url: str | None = None
    unit: str | None = None
    unit_size: str | None = None
    category_id: int | None = None
    is_active: bool | None = None


class ProductRead(ProductBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    category: CategoryRead | None = None
    # Infos nutritionnelles (pour 100g)
    calories: float | None = None
    proteins: float | None = None
    lipids: float | None = None
    carbs: float | None = None
    fibers: float | None = None
    nutriscore: str | None = None

    model_config = {"from_attributes": True}
