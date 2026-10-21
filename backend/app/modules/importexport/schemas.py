import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.pagination import PageParams
from app.modules.importexport.rules import (
    ExportKind,
    ExportStatus,
    ImportErrorReason,
    ImportStatus,
    ImportType,
)
from app.modules.reporting.schemas import ReportParams
from app.modules.visitors.schemas import LeadFilters


class JobAccepted(BaseModel):
    job_id: uuid.UUID
    status: str


class ImportJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    edition_id: uuid.UUID
    status: ImportStatus
    import_type: ImportType
    file_name: str
    file_size: int
    column_mapping: dict[str, str]
    total_rows: int | None
    processed_count: int
    created_count: int
    duplicate_count: int
    invalid_count: int
    registered_count: int
    error_summary: str | None
    has_error_report: bool = False
    started_at: datetime | None
    finished_at: datetime | None
    created_by: uuid.UUID | None
    created_at: datetime


class ImportErrorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    row_number: int
    reason_code: ImportErrorReason
    message: str
    fields: dict[str, str]
    row_preview: dict[str, Any]


class ImportListParams(PageParams):
    edition_id: uuid.UUID


class ImportErrorParams(PageParams):
    reason_code: ImportErrorReason | None = None


class EditionParam(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edition_id: uuid.UUID


class MappingTarget(BaseModel):
    target: str
    label: str
    required: bool = False


class PreviewOut(BaseModel):
    headers: list[str]
    suggested_mapping: dict[str, str]
    targets: list[MappingTarget]
    sample_rows: int = Field(description="Data rows detected (up to the configured limit).")


class DownloadOut(BaseModel):
    url: str
    expires_in: int


class VisitorExportIn(LeadFilters):
    edition_id: uuid.UUID


class ReportExportIn(ReportParams):
    pass


class ExportListParams(PageParams):
    edition_id: uuid.UUID


class ExportJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    edition_id: uuid.UUID
    kind: ExportKind
    status: ExportStatus
    row_count: int | None
    file_name: str | None
    file_size: int | None
    error_summary: str | None
    created_at: datetime
    finished_at: datetime | None
    expires_at: datetime | None
    # Short-lived signed link, only while the file exists.
    download_url: str | None = None
