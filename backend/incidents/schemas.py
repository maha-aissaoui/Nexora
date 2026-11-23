
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# Données reçues par le Backend
class IncidentCreate(BaseModel):

    source: str = "fixops-agent"

    host_id: str

    service: str

    type: str

    observed_status: str

    observed_at: datetime

    details: dict = Field(default_factory=dict)


# Données retournées par le Backend
class IncidentResponse(BaseModel):

    id: str

    host_id: str

    service: str

    type: str

    status: str

    created_at: datetime

    last_seen_at: datetime
