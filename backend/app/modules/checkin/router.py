import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuthContext, require
from app.core.db import get_session
from app.core.pagination import Page
from app.modules.checkin import service
from app.modules.checkin.schemas import (
    ActivatedOut,
    ActivateIn,
    CacheOut,
    DeviceContext,
    DeviceCreatedOut,
    DeviceIn,
    DeviceListParams,
    DeviceOut,
    DeviceRevokeIn,
    GateIn,
    GateListParams,
    GateOut,
    GateUpdateIn,
    OverrideIn,
    ReconciliationParams,
    ScanIn,
    ScanListParams,
    ScanOut,
    ScanResultOut,
    SyncIn,
    SyncOut,
)
from app.modules.checkin.service import DeviceAuth, require_device
from app.modules.identity.router import client_ip

router = APIRouter(tags=["gate"])
# Scanner PWA: authenticated by the device token (X-Device-Token), not a user session,
# so an offline queue can still sync after the staff session expired.
device_router = APIRouter(prefix="/gate/device", tags=["gate device"])
Session = Annotated[AsyncSession, Depends(get_session)]
Device = Annotated[DeviceAuth, Depends(require_device)]


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


# --- desk: gates and devices -----------------------------------------------------------------


@router.get("/gates", response_model=list[GateOut])
async def list_gates(
    session: Session,
    params: Annotated[GateListParams, Query()],
    ctx: AuthContext = Depends(require("gate.manage_devices", "gate.view_history", "gate.scan")),
) -> list[GateOut]:
    return await service.list_gates(session, ctx, params.edition_id)


@router.post("/gates", response_model=GateOut, status_code=status.HTTP_201_CREATED)
async def create_gate(
    data: GateIn, session: Session, ctx: AuthContext = Depends(require("gate.manage_devices"))
) -> GateOut:
    return await service.create_gate(session, ctx, data)


@router.patch("/gates/{gate_id}", response_model=GateOut)
async def update_gate(
    gate_id: uuid.UUID,
    data: GateUpdateIn,
    session: Session,
    ctx: AuthContext = Depends(require("gate.manage_devices")),
) -> GateOut:
    return await service.update_gate(session, ctx, gate_id, data)


@router.get("/gate/devices", response_model=Page[DeviceOut])
async def list_devices(
    session: Session,
    params: Annotated[DeviceListParams, Query()],
    ctx: AuthContext = Depends(require("gate.manage_devices")),
) -> Page[DeviceOut]:
    return await service.list_devices(session, ctx, params)


@router.post("/gate/devices", response_model=DeviceCreatedOut, status_code=status.HTTP_201_CREATED)
async def create_device(
    data: DeviceIn,
    session: Session,
    response: Response,
    ctx: AuthContext = Depends(require("gate.manage_devices")),
) -> DeviceCreatedOut:
    _no_store(response)
    return await service.create_device(session, ctx, data)


@router.post("/gate/devices/{device_id}/activation-code", response_model=DeviceCreatedOut)
async def new_activation_code(
    device_id: uuid.UUID,
    session: Session,
    response: Response,
    ctx: AuthContext = Depends(require("gate.manage_devices")),
) -> DeviceCreatedOut:
    _no_store(response)
    return await service.new_activation(session, ctx, device_id)


@router.post("/gate/devices/{device_id}/revoke", response_model=DeviceOut)
async def revoke_device(
    device_id: uuid.UUID,
    data: DeviceRevokeIn,
    session: Session,
    ctx: AuthContext = Depends(require("gate.manage_devices")),
) -> DeviceOut:
    return await service.revoke_device(session, ctx, device_id, data)


# --- desk: history, reconciliation, override -------------------------------------------------


@router.get("/gate/scans", response_model=Page[ScanOut])
async def list_scans(
    session: Session,
    params: Annotated[ScanListParams, Query()],
    ctx: AuthContext = Depends(require("gate.view_history")),
) -> Page[ScanOut]:
    return await service.list_scans(session, ctx, params)


@router.get("/gate/reconciliation", response_model=Page[ScanOut])
async def reconciliation(
    session: Session,
    params: Annotated[ReconciliationParams, Query()],
    ctx: AuthContext = Depends(require("gate.view_history")),
) -> Page[ScanOut]:
    return await service.reconciliation(session, ctx, params)


@router.post("/gate/overrides", response_model=ScanOut, status_code=status.HTTP_201_CREATED)
async def override(
    data: OverrideIn, session: Session, ctx: AuthContext = Depends(require("gate.override"))
) -> ScanOut:
    return await service.override(session, ctx, data)


# --- scanner device --------------------------------------------------------------------------


@device_router.post("/activate", response_model=ActivatedOut)
async def activate(
    data: ActivateIn, request: Request, response: Response, session: Session
) -> ActivatedOut:
    """The one-time activation code is the credential here."""
    _no_store(response)
    return await service.activate_device(session, data, client_ip(request))


@device_router.get("/me", response_model=DeviceContext)
async def device_me(device: Device) -> DeviceContext:
    return device.context()


@device_router.get("/cache", response_model=CacheOut)
async def device_cache(device: Device, session: Session, response: Response) -> CacheOut:
    _no_store(response)
    return await service.device_cache(session, device)


@device_router.post("/scans", response_model=ScanResultOut)
async def scan(data: ScanIn, device: Device, session: Session) -> ScanResultOut:
    return await service.scan_online(session, device, data)


@device_router.post("/scans/sync", response_model=SyncOut)
async def sync(data: SyncIn, device: Device, session: Session) -> SyncOut:
    return await service.sync_scans(session, device, data)
