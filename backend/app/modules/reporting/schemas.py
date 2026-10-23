import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from app.modules.visitors.rules import Attend, BuyerType, TelemarketingStatus
from app.modules.visitors.schemas import LeadFilters


class ReportType(StrEnum):
    LEADS = "LEADS"
    TELEMARKETING = "TELEMARKETING"
    VERIFICATION = "VERIFICATION"
    REGISTRATION = "REGISTRATION"
    ATTENDANCE = "ATTENDANCE"
    GATES = "GATES"
    AGENTS = "AGENTS"
    IMPORTS = "IMPORTS"
    EMAILS = "EMAILS"


# Lead filters drive the lead-based reports; gate reports use gate_id + the date range.
LEAD_REPORTS = frozenset(
    {
        ReportType.LEADS,
        ReportType.TELEMARKETING,
        ReportType.VERIFICATION,
        ReportType.REGISTRATION,
        ReportType.AGENTS,
    }
)
GATE_REPORTS = frozenset({ReportType.ATTENDANCE, ReportType.GATES})
# Edition-wide operations data: needs edition scope.
EDITION_REPORTS = frozenset({ReportType.IMPORTS, ReportType.EMAILS})


class ReportParams(LeadFilters):
    edition_id: uuid.UUID
    report: ReportType
    # Event-local dates (edition timezone), inclusive. Calls, scans, imports, emails.
    date_from: date | None = None
    date_to: date | None = None
    gate_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _range(self) -> "ReportParams":
        if self.date_from and self.date_to and self.date_to < self.date_from:
            raise ValueError("date_to must not be before date_from")
        return self


class Count(BaseModel):
    key: str | None
    count: int


class _Base(BaseModel):
    edition_id: uuid.UUID
    generated_at: datetime


class LeadsReport(_Base):
    report: Literal["LEADS"] = "LEADS"
    total: int
    new: int
    assigned: int
    unassigned: int
    by_source: list[Count]
    by_country: list[Count]


class TelemarketingReport(_Base):
    report: Literal["TELEMARKETING"] = "TELEMARKETING"
    attempts: int
    answered: int
    # None when there were no attempts (no rate to report).
    answer_rate: float | None
    leads_by_status: list[Count]
    followups_open: int
    followups_due_today: int
    followups_overdue: int


class VerificationReport(_Base):
    report: Literal["VERIFICATION"] = "VERIFICATION"
    valid: int
    invalid: int
    undecided: int
    by_attend: list[Count]
    by_buyer_type: list[Count]
    b2b_matching: int


class RegistrationReport(_Base):
    report: Literal["REGISTRATION"] = "REGISTRATION"
    registered: int
    not_registered: int
    by_channel: list[Count]
    qr_active: int
    qr_revoked: int
    emails_by_status: list[Count]


class AttendanceDay(BaseModel):
    local_date: date
    unique_visitors: int
    first_entries: int
    repeat_entries: int
    total_scans: int
    rejected: int


class AttendanceReport(_Base):
    report: Literal["ATTENDANCE"] = "ATTENDANCE"
    unique_event_visitors: int
    total_scans: int
    valid_entries: int
    first_entries: int
    repeat_entries: int
    rejected: int
    by_day: list[AttendanceDay]


class GateRow(BaseModel):
    gate_id: uuid.UUID
    gate_code: str
    gate_name: str
    total_scans: int
    valid_entries: int
    rejected: int


class HourRow(BaseModel):
    local_date: date
    hour: int = Field(ge=0, le=23)
    total_scans: int
    valid_entries: int


class GatesReport(_Base):
    report: Literal["GATES"] = "GATES"
    by_gate: list[GateRow]
    by_hour: list[HourRow]


class AgentRow(BaseModel):
    agent_id: uuid.UUID
    full_name: str
    leads_owned: int
    attempts: int
    answered: int
    followups_total: int
    followups_done: int
    followup_completion: float | None


class AgentsReport(_Base):
    report: Literal["AGENTS"] = "AGENTS"
    agents: list[AgentRow]


class ImportsReport(_Base):
    report: Literal["IMPORTS"] = "IMPORTS"
    jobs: int
    by_status: list[Count]
    processed: int
    created: int
    duplicate: int
    invalid: int


class EmailsReport(_Base):
    report: Literal["EMAILS"] = "EMAILS"
    total: int
    by_status: list[Count]


Report = Annotated[
    LeadsReport
    | TelemarketingReport
    | VerificationReport
    | RegistrationReport
    | AttendanceReport
    | GatesReport
    | AgentsReport
    | ImportsReport
    | EmailsReport,
    Field(discriminator="report"),
]


# --- dashboard (per call, like the old system's dashboard; FEATURES/10 "Dashboard") ---------

DashboardGroup = Literal["total", "day", "day_edition", "day_source", "day_user"]
MAX_DASHBOARD_DAYS = 366


class DashboardParams(BaseModel):
    """Filters of every dashboard tab. Lead filters narrow leads; verification filters narrow
    calls by the verification sent with them (and leads by their current values)."""

    model_config = {"extra": "forbid"}

    date_from: date
    date_to: date
    group_by: DashboardGroup = "total"
    edition_id: uuid.UUID | None = None
    country: str | None = Field(default=None, min_length=2, max_length=2)
    user_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None
    lead_source_id: uuid.UUID | None = None
    telemarketing_status: TelemarketingStatus | None = None
    lead_quality: Literal["VALID", "INVALID", "UNDECIDED"] | None = None
    buyer_type: BuyerType | None = None
    attend: Attend | None = None
    b2b_matching: bool | None = None

    @model_validator(mode="after")
    def _range(self) -> "DashboardParams":
        if self.date_to < self.date_from:
            raise ValueError("date_to must not be before date_from")
        if (self.date_to - self.date_from).days >= MAX_DASHBOARD_DAYS:
            raise ValueError(f"Choose at most {MAX_DASHBOARD_DAYS} days.")
        return self


class DashboardRow(BaseModel):
    """Counts for one day and/or key (edition, source, or user), or for the whole range.

    Call counts: Answer / Non Answer = first call answered / not; Recontacted / Retry No Answer =
    later calls answered / not; Total = all calls. Pending = leads never called by the end of
    the day (of the range for the total row).
    """

    day: date | None = None
    key: str | None = None
    added: int = 0
    pending: int = 0
    total: int = 0
    answer: int = 0
    non_answer: int = 0
    recontacted: int = 0
    retry_no_answer: int = 0
    valid: int = 0
    no_valid: int = 0
    attend: int = 0
    attend_sourcing: int = 0
    under_consideration: int = 0
    not_attend: int = 0
    hang_up_immediately: int = 0
    b2b_matching: int = 0
    b_side: int = 0
    c_side: int = 0


class DashboardKey(BaseModel):
    id: str | None
    label: str
    # Recap By User: the user's teams and the editions they work in.
    group: str | None = None
    editions: str | None = None


class DashboardOut(BaseModel):
    timezone: str
    today: date
    date_from: date
    date_to: date
    group_by: DashboardGroup
    rows: list[DashboardRow]
    keys: list[DashboardKey] = []


class DashboardOption(BaseModel):
    id: str
    label: str


class DashboardOptions(BaseModel):
    """Filter choices limited to what the caller can see: countries present in the leads."""

    countries: list[str]
    users: list[DashboardOption]
    teams: list[DashboardOption]
