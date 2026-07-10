from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import date, time, datetime
from .hcp import HCP as HCPSchema


class InteractionBase(BaseModel):
    hcp_id: int
    interaction_type: Optional[str] = None
    interaction_date: Optional[date] = None
    interaction_time: Optional[time] = None
    meeting_location: Optional[str] = None
    attendees: Optional[str] = None
    topics_discussed: Optional[str] = None
    ai_summary: Optional[str] = None
    sentiment: Optional[str] = None
    outcomes: Optional[str] = None
    follow_up_actions: Optional[str] = None


class InteractionCreate(InteractionBase):
    materials_shared: Optional[list[str]] = []
    samples_distributed: Optional[list[str]] = []
    ai_suggestions: Optional[list[str]] = []
    ai_meeting_location: Optional[str] = None


class MaterialSchema(BaseModel):
    id: int
    material_name: str
    
    model_config = ConfigDict(from_attributes=True)


class SampleSchema(BaseModel):
    id: int
    sample_name: str
    quantity: int

    model_config = ConfigDict(from_attributes=True)


class AISuggestionSchema(BaseModel):
    id: int
    suggestion: str

    model_config = ConfigDict(from_attributes=True)


class Interaction(InteractionBase):
    id: int
    created_at: datetime
    materials: list[MaterialSchema] = []
    samples: list[SampleSchema] = []
    ai_suggestions: list[AISuggestionSchema] = []
    hcp: Optional[HCPSchema] = None

    model_config = ConfigDict(from_attributes=True)