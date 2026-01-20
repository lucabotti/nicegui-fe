from pydantic import BaseModel, ConfigDict, EmailStr, Field


class EmailBase(BaseModel):
    address: EmailStr


class EmailCreate(EmailBase):
    pass


class EmailRead(EmailBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class PhoneNumberBase(BaseModel):
    number: str


class PhoneNumberCreate(PhoneNumberBase):
    pass


class PhoneNumberRead(PhoneNumberBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class ContactBase(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    role: str
    organization_id: str | None = None
    tags: list[str] = Field(default_factory=list)


class ContactCreate(ContactBase):
    emails: list[EmailCreate]
    phone_numbers: list[PhoneNumberCreate]


class ContactRead(ContactBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    emails: list[EmailRead]
    phone_numbers: list[PhoneNumberRead]

    # We might want to include org name if available
    organization_name: str | None = None


class ContactUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    role: str | None = None
    organization_id: str | None = None
    tags: list[str] | None = None
    emails: list[EmailCreate] | None = None
    phone_numbers: list[PhoneNumberCreate] | None = None
