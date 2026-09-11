from pydantic import BaseModel, Field


class DashboardSummary(BaseModel):
    total_incidents: int = Field(..., ge=0)
    active_incidents: int = Field(..., ge=0)
    recovered_incidents: int = Field(..., ge=0)
    failed_incidents: int = Field(..., ge=0)
    pending_approval: int = Field(..., ge=0)
    severity_distribution: dict[str, int] = Field(default_factory=dict)
    lifecycle_distribution: dict[str, int] = Field(default_factory=dict)


class DashboardSummaryResponse(BaseModel):
    success: bool
    summary: DashboardSummary


class IncidentTrendPoint(BaseModel):
    date: str
    count: int = Field(..., ge=0)


class IncidentTrend(BaseModel):
    days: int = Field(..., ge=1)
    trend: list[IncidentTrendPoint] = Field(default_factory=list)


class IncidentTrendResponse(BaseModel):
    success: bool
    trend: IncidentTrend
