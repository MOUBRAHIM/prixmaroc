from pydantic import BaseModel


class CategoryBase(BaseModel):
    name: str
    slug: str
    icon: str | None = None
    parent_id: int | None = None


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: str | None = None
    icon: str | None = None
    parent_id: int | None = None


class CategoryRead(CategoryBase):
    id: int
    children: list["CategoryRead"] = []

    model_config = {"from_attributes": True}


CategoryRead.model_rebuild()
