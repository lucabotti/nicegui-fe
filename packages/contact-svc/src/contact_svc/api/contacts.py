from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db import get_db
from ..models.contact import Contact, Email, PhoneNumber
from ..schemas.contact import ContactCreate, ContactRead, ContactUpdate
from ..services.org_client import get_org_name

router = APIRouter()


@router.post("/", response_model=ContactRead)
async def create_contact(
    contact_data: ContactCreate, db: AsyncSession = Depends(get_db)
):
    db_contact = Contact(
        first_name=contact_data.first_name,
        last_name=contact_data.last_name,
        role=contact_data.role,
        organization_id=contact_data.organization_id,
        tags=contact_data.tags,
    )
    db.add(db_contact)
    await db.flush()  # Get ID

    for email in contact_data.emails:
        db.add(Email(address=email.address, contact_id=db_contact.id))

    for phone in contact_data.phone_numbers:
        db.add(PhoneNumber(number=phone.number, contact_id=db_contact.id))

    await db.commit()
    await db.refresh(db_contact, attribute_names=["emails", "phone_numbers"])

    res = ContactRead.from_orm(db_contact)
    res.organization_name = await get_org_name(db_contact.organization_id)
    return res


@router.get("/", response_model=list[ContactRead])
async def list_contacts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Contact).options(
            selectinload(Contact.emails), selectinload(Contact.phone_numbers)
        )
    )
    contacts = result.scalars().all()

    res_list = []
    for c in contacts:
        read = ContactRead.from_orm(c)
        read.organization_name = await get_org_name(c.organization_id)
        res_list.append(read)
    return res_list


@router.get("/{contact_id}", response_model=ContactRead)
async def get_contact(contact_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Contact)
        .where(Contact.id == contact_id)
        .options(selectinload(Contact.emails), selectinload(Contact.phone_numbers))
    )
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    res = ContactRead.from_orm(contact)
    res.organization_name = await get_org_name(contact.organization_id)
    return res


@router.patch("/{contact_id}", response_model=ContactRead)
async def patch_contact(
    contact_id: int, contact_update: ContactUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Contact)
        .where(Contact.id == contact_id)
        .options(selectinload(Contact.emails), selectinload(Contact.phone_numbers))
    )
    db_contact = result.scalar_one_or_none()
    if not db_contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    # Update basic fields
    if contact_update.first_name is not None:
        db_contact.first_name = contact_update.first_name
    if contact_update.last_name is not None:
        db_contact.last_name = contact_update.last_name
    if contact_update.role is not None:
        db_contact.role = contact_update.role
    if contact_update.organization_id is not None:
        db_contact.organization_id = contact_update.organization_id
    if contact_update.tags is not None:
        db_contact.tags = contact_update.tags

    # Update nested fields (replace strategy for simplicity)
    if contact_update.emails is not None:
        # Delete old emails
        for email in db_contact.emails:
            await db.delete(email)
        # Add new emails
        for email in contact_update.emails:
            db.add(Email(address=email.address, contact_id=contact_id))

    if contact_update.phone_numbers is not None:
        # Delete old phone numbers
        for phone in db_contact.phone_numbers:
            await db.delete(phone)
        # Add new phone numbers
        for phone in contact_update.phone_numbers:
            db.add(PhoneNumber(number=phone.number, contact_id=contact_id))

    await db.commit()
    await db.refresh(db_contact, attribute_names=["emails", "phone_numbers"])

    res = ContactRead.from_orm(db_contact)
    res.organization_name = await get_org_name(db_contact.organization_id)
    return res


@router.delete("/{contact_id}")
async def delete_contact(contact_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Contact).where(Contact.id == contact_id))
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    await db.delete(contact)
    await db.commit()
    return {"status": "success"}
