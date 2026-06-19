from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from src.database.database import get_db
from src.database.models import PBX, Tenant
from src.api.auth import verify_token, require_admin_role
from typing import List

router = APIRouter(prefix="/api/v1/admin", tags=["pbxs"])


class PBXCreate(BaseModel):
    name: str = Field(..., max_length=128)
    host: str = Field(..., max_length=128)
    port: int = Field(default=5060, ge=1, le=65535)


class PBXResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    host: str
    port: int
    created_at: str

    model_config = {"from_attributes": True}


@router.post("/pbxs", status_code=status.HTTP_201_CREATED, response_model=PBXResponse)
async def create_pbx(
    data: PBXCreate,
    payload: dict = Depends(require_admin_role),
    db: AsyncSession = Depends(get_db),
):
    tenant_id = payload.get("tenant_id", "")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Tenant ID não encontrado no token")

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Inquilino não encontrado")

    pbx = PBX(tenant_id=tenant.id, name=data.name, host=data.host, port=data.port)
    db.add(pbx)
    await db.commit()
    await db.refresh(pbx)

    return PBXResponse(
        id=str(pbx.id),
        tenant_id=str(pbx.tenant_id),
        name=pbx.name,
        host=pbx.host,
        port=pbx.port,
        created_at=pbx.created_at.isoformat() if pbx.created_at else "",
    )


@router.get("/pbxs", response_model=List[PBXResponse])
async def list_pbxs(
    payload: dict = Depends(require_admin_role),
    db: AsyncSession = Depends(get_db),
):
    tenant_id = payload.get("tenant_id", "")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Tenant ID não encontrado no token")

    result = await db.execute(select(PBX).where(PBX.tenant_id == tenant_id))
    pbxs = result.scalars().all()

    return [
        PBXResponse(
            id=str(pbx.id),
            tenant_id=str(pbx.tenant_id),
            name=pbx.name,
            host=pbx.host,
            port=pbx.port,
            created_at=pbx.created_at.isoformat() if pbx.created_at else "",
        )
        for pbx in pbxs
    ]
