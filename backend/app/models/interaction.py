from sqlalchemy import Column, Integer, String, Text, Date, Time, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Interaction(Base):
    __tablename__ = "interaction"

    id = Column(Integer, primary_key=True, index=True)

    hcp_id = Column(Integer, ForeignKey("hcp.id"), nullable=False)

    interaction_type = Column(String(50))
    interaction_date = Column(Date)
    interaction_time = Column(Time)
    meeting_location = Column(String(150))
    attendees = Column(Text)
    topics_discussed = Column(Text)
    ai_summary = Column(Text)
    sentiment = Column(String(30))
    outcomes = Column(Text)
    follow_up_actions = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    hcp = relationship("HCP", back_populates="interactions")
    materials = relationship("Material", back_populates="interaction")
    samples = relationship("Sample", back_populates="interaction")
    ai_suggestions = relationship("AISuggestion", back_populates="interaction")