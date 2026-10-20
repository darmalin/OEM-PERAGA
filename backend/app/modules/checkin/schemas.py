import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints

from app.core.pagination import PageParams
from app.modules.checkin.rules import DeviceStatus, ScanMode, ScanResult

TokenHash = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
# Normalised before the pattern check, so "main" and " Main " both become MAIN.
GateCode = Annotated[
    str,
    BeforeValidator(lambda v: v.strip().upper() if isinstance(v, str) else v),
    StringConstraints(pattern=r"^[A-Z0-9_-]{1,30}$"),
]

MAX_SYNC_ITEMS = 500


# --- gates ---------------------------------------------------------------------------------


class GateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edition_id: uuid.UUID
    code: GateCode
    name: str = Field(min_length=1, max_length=200)


class GateUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    name: str | None = Field(default=None, min_length=1, max_length=200)
    is_active: bool | None = None


class GateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    edition_id: uuid.UUID
    code: str
    name: str
    is_active: bool
    version: int


class GateListParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edition_id: uuid.UUID


# --- devices -------------------------------------------------------------------------------


class DeviceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gate_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    edition_id: uuid.UUID
    gate_id: uuid.UUID
    name: str
    status: DeviceStatus
    activation_expires_at: datetime | None
    activated_at: datetime | None
    last_seen_at: datetime | None
    revoked_at: datetime | None
    revoke_reason: str | None
    version: int


class DeviceCreatedOut(DeviceOut):
    # Shown once; only its hash is stored.
    activation_code: str


class DeviceListParams(PageParams):
    edition_id: uuid.UUID
    gate_id: uuid.UUID | None = None
    status: DeviceStatus | None = None


class DeviceRevokeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)


class ActivateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activation_code: str = Field(min_length=6, max_length=20)


class DeviceContext(BaseModel):
    device_id: uuid.UUID
    device_name: str
    status: DeviceStatus
    edition_id: uuid.UUID
    edition_code: str
    edition_timezone: str
    gate_id: uuid.UUID
    gate_code: str
    gate_name: str


class ActivatedOut(DeviceContext):
    # "<device_id>.<secret>", sent as X-Device-Token. Shown once.
    device_token: str


# --- scanning ------------------------------------------------------------------------------


class ScanIn(BaseModel):
    """Online scan. The device hashes the QR token, so the raw token never leaves it."""

    model_config = ConfigDict(extra="forbid")

    scan_event_id: uuid.UUID
    token_hash: TokenHash


class SyncItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_event_id: uuid.UUID
    token_hash: TokenHash
    scanned_at: datetime
    provisional_result: ScanResult | None = None


class SyncIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[SyncItem] = Field(min_length=1, max_length=MAX_SYNC_ITEMS)


class ScanResultOut(BaseModel):
    scan_event_id: uuid.UUID
    result: ScanResult
    registration_code: str | None = None
    first_name: str | None = None
    scanned_at: datetime
    local_date: date
    # Offline only: the device showed something else; it should update its record.
    changed_from_provisional: bool = False


class SyncOut(BaseModel):
    results: list[ScanResultOut]


class CacheEntry(BaseModel):
    token_hash: str
    status: str  # ACTIVE, REVOKED, CANCELLED
    registration_code: str
    first_name: str


class CacheOut(BaseModel):
    """Offline cache (spec 8.3): only what the gate screen shows, nothing else."""

    edition_id: uuid.UUID
    gate_id: uuid.UUID
    generated_at: datetime
    expires_at: datetime
    local_date: date
    credentials: list[CacheEntry]
    # Token hashes that already have a first entry today, for a better offline guess.
    entered_today: list[str]


# --- history / override --------------------------------------------------------------------


class ScanListParams(PageParams):
    edition_id: uuid.UUID
    gate_id: uuid.UUID | None = None
    device_id: uuid.UUID | None = None
    local_date: date | None = None
    result: ScanResult | None = None
    mode: ScanMode | None = None


class ScanOut(BaseModel):
    id: uuid.UUID
    scan_event_id: uuid.UUID
    gate_id: uuid.UUID
    device_id: uuid.UUID | None
    registration_id: uuid.UUID | None
    registration_code: str | None
    first_name: str | None
    mode: ScanMode
    result: ScanResult
    provisional_result: ScanResult | None
    scanned_at: datetime
    received_at: datetime
    local_date: date
    recorded_by: uuid.UUID | None
    reason: str | None


class ReconciliationParams(PageParams):
    edition_id: uuid.UUID


class OverrideIn(BaseModel):
    """gate.override: admit a registered visitor whose QR cannot be read."""

    model_config = ConfigDict(extra="forbid")

    scan_event_id: uuid.UUID
    gate_id: uuid.UUID
    registration_id: uuid.UUID
    reason: str = Field(min_length=1, max_length=500)
