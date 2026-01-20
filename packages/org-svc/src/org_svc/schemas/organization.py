from pydantic import BaseModel, ConfigDict


class OrganizationBase(BaseModel):
    name: str


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationUpdate(BaseModel):
    name: str | None = None


class OrganizationRead(OrganizationBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
