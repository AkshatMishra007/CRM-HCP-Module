from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class HCPBase(BaseModel):
    name: str
    hospital: str
    specialization: Optional[str] = None
    city: Optional[str] = None


class HCPCreate(HCPBase):
    pass

class HCPUpdate(BaseModel):
    name: str | None = None
    hospital: str | None = None
    specialization: str | None = None
    city: str | None = None

class HCP(HCPBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )