from datetime import datetime
from pydantic import BaseModel


class ShoppingListItemBase(BaseModel):
    product_id: int | None = None
    custom_name: str | None = None
    quantity: int = 1
    unit: str | None = None
    note: str | None = None


class ShoppingListItemCreate(ShoppingListItemBase):
    pass


class ShoppingListItemUpdate(BaseModel):
    quantity: int | None = None
    is_checked: bool | None = None
    note: str | None = None


class ShoppingListItemRead(ShoppingListItemBase):
    id: int
    list_id: int
    is_checked: bool

    model_config = {"from_attributes": True}


class ShoppingListBase(BaseModel):
    name: str
    description: str | None = None
    is_shared: bool = False


class ShoppingListCreate(ShoppingListBase):
    pass


class ShoppingListUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_shared: bool | None = None


class ShoppingListRead(ShoppingListBase):
    id: int
    user_id: int
    share_token: str | None = None
    created_at: datetime
    updated_at: datetime
    items: list[ShoppingListItemRead] = []

    model_config = {"from_attributes": True}
