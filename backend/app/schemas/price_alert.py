from datetime import datetime
from pydantic import BaseModel


class PriceAlertBase(BaseModel):
    product_id: int
    store_id: int | None = None
    target_price: float


class PriceAlertCreate(PriceAlertBase):
    pass


class PriceAlertUpdate(BaseModel):
    target_price: float | None = None
    is_active: bool | None = None


class PriceAlertRead(PriceAlertBase):
    id: int
    user_id: int
    is_active: bool
    triggered_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
