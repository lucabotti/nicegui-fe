from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_db
from .models.organization import Organization
from .schemas.organization import (
    OrganizationCreate,
    OrganizationRead,
    OrganizationUpdate,
)

app = FastAPI(title="Organization Service")


@app.get("/orgs", response_model=list[OrganizationRead])
async def get_orgs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Organization))
    return result.scalars().all()


@app.get("/orgs/{org_id}", response_model=OrganizationRead)
async def get_org(org_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@app.post("/orgs", response_model=OrganizationRead)
async def create_org(org: OrganizationCreate, db: AsyncSession = Depends(get_db)):
    new_org = Organization(name=org.name)
    db.add(new_org)
    await db.commit()
    await db.refresh(new_org)
    return new_org


@app.put("/orgs/{org_id}", response_model=OrganizationRead)
async def update_org(
    org_id: int, org_update: OrganizationUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    if org_update.name is not None:
        org.name = org_update.name

    await db.commit()
    await db.refresh(org)
    return org


@app.delete("/orgs/{org_id}")
async def delete_org(org_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    await db.delete(org)
    await db.commit()
    return {"message": "Organization deleted"}


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import os

    import uvicorn

    port = int(os.getenv("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
